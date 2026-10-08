#!/usr/bin/env python3
"""
Version-Aware Local Search & Query Engine for odoo-knowledge.

Zero external dependencies: Python standard library only (sqlite3, pathlib, re, json, argparse, sys, typing, os).
Provides strict Odoo version ontology filtering, SQLite FTS5 BM25 ranking,
two-tier version prioritization (ensuring Odoo 20 migration cookbook ranks #1),
and high-signal snippet formatting across text, markdown, compact, and json.
"""

import argparse
import json
import os
from pathlib import Path
import re
import sqlite3
import sys
import time
from typing import Any, Dict, List, Optional, Set, Union

# Default repository paths
DEFAULT_REPO_ROOT: Path = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH: Path = DEFAULT_REPO_ROOT / ".kb_cache.db"


class VersionRule:
    """Structured representation of an entry's version compatibility."""

    def __init__(
        self,
        raw: str,
        is_all: bool = False,
        exact_versions: Optional[Set[float]] = None,
        min_version: Optional[float] = None,
        max_version: Optional[float] = None,
    ):
        self.raw = raw
        self.is_all = is_all
        self.exact_versions: Set[float] = exact_versions or set()
        self.min_version = min_version
        self.max_version = max_version

    def __repr__(self) -> str:
        return (
            f"VersionRule(raw={self.raw!r}, is_all={self.is_all}, "
            f"exact={self.exact_versions}, min={self.min_version}, max={self.max_version})"
        )


def parse_version_rule(spec_str: str) -> VersionRule:
    """
    Parses a raw version string into a structured VersionRule.
    Handles universal wildcards, discrete versions, open/closed ranges,
    and legacy boundaries.
    """
    if not spec_str or spec_str.strip() in ("[NONE/SECTION]", ""):
        return VersionRule(raw=spec_str or "", is_all=True)

    s = spec_str.strip().lower()

    # Non-Odoo or universal documentation (e.g. Unity, general client/game engine)
    if "unity" in s or s.startswith("n/a"):
        return VersionRule(raw=spec_str, is_all=True)

    # Upper bound (<18, <=19)
    lt_m = re.search(r"(<=|<)\s*(\d+(?:\.\d+)?)", spec_str)
    if lt_m:
        op, val = lt_m.group(1), float(lt_m.group(2))
        max_v = val if op == "<=" else val - 0.1
        return VersionRule(raw=spec_str, is_all=False, max_version=max_v)

    # Closed ranges (14..19, 19.0 - 20.0, 16 to 18)
    range_m = re.search(r"(\d+(?:\.\d+)?)\s*(?:-|to|\.\.)\s*(\d+(?:\.\d+)?)", spec_str)
    if range_m:
        v1, v2 = float(range_m.group(1)), float(range_m.group(2))
        return VersionRule(
            raw=spec_str,
            is_all=False,
            min_version=min(v1, v2),
            max_version=max(v1, v2),
        )

    # Universal wildcard ("All", "All Versions", "All (14, 15, 16, 17, 18, 19)")
    if "all" in s or "any" in s:
        return VersionRule(raw=spec_str, is_all=True)

    # Open upper bounds (17.0+, >=18.0)
    plus_m = re.search(r"(\d+(?:\.\d+)?)\s*\+", spec_str)
    gte_m = re.search(r">=\s*(\d+(?:\.\d+)?)", spec_str)
    if plus_m:
        return VersionRule(raw=spec_str, is_all=False, min_version=float(plus_m.group(1)))
    if gte_m:
        return VersionRule(raw=spec_str, is_all=False, min_version=float(gte_m.group(1)))

    # Clean V/v prefixes from numbers (e.g. V16, V17)
    clean_str = re.sub(r"(?i)\bv?(\d+)", r"\1", spec_str)

    # Single version with parenthetical comment (e.g. "19 (several points apply to 17/18)")
    primary_m = re.match(r"^\s*(\d{1,2}(?:\.\d+)?)\s*\(", clean_str)
    if primary_m:
        return VersionRule(raw=spec_str, is_all=False, exact_versions={float(primary_m.group(1))})

    # Discrete version list (e.g. "16, 17, 18, 19", "19, 20", "20", "16.0 only")
    nums = re.findall(r"\b(?:\d{1,2}(?:\.\d+)?)\b", clean_str)
    if nums:
        return VersionRule(raw=spec_str, is_all=False, exact_versions={float(n) for n in nums})

    # Default fallback: universally applicable
    return VersionRule(raw=spec_str, is_all=True)


def matches_version(
    rule: Union[VersionRule, Dict[str, Any]], target_version: Optional[Union[float, int, str]]
) -> bool:
    """
    Evaluates whether a VersionRule matches the specified target_version.
    Returns True if target_version is None or compatibility is satisfied.
    """
    if target_version is None:
        return True

    try:
        target = float(target_version)
    except (ValueError, TypeError):
        return True

    # Support dictionary representation for flexibility
    if isinstance(rule, dict):
        if rule.get("is_all", False):
            return True
        exact = rule.get("exact") or rule.get("exact_versions") or set()
        if target in exact:
            return True
        min_v = rule.get("min") or rule.get("min_version")
        max_v = rule.get("max") or rule.get("max_version")
        if min_v is not None and max_v is not None:
            return min_v <= target <= max_v
        if min_v is not None and max_v is None:
            return target >= min_v
        if max_v is not None and min_v is None:
            return target <= max_v
        return False

    # VersionRule object
    if rule.is_all:
        return True
    if target in rule.exact_versions:
        return True
    if rule.min_version is not None and rule.max_version is not None:
        return rule.min_version <= target <= rule.max_version
    if rule.min_version is not None and rule.max_version is None:
        return target >= rule.min_version
    if rule.max_version is not None and rule.min_version is None:
        return target <= rule.max_version
    return False


def sanitize_fts5_query(query_str: str) -> str:
    """
    Sanitizes user input into valid SQLite FTS5 query syntax.
    Safely wraps dotted code symbols ('ir.access.csv', 'models.Constraint')
    and punctuation in double quotes to prevent FTS5 syntax errors.
    Preserves boolean operators (AND, OR, NOT) and explicit quoted phrases.
    """
    if not query_str or not query_str.strip():
        return ""

    # Preserve explicit quotes when splitting tokens
    raw_tokens = re.findall(r'"[^"]*"|\S+', query_str.strip())
    processed: List[str] = []

    for token in raw_tokens:
        # Preserve boolean operators
        if token.upper() in ("AND", "OR", "NOT"):
            processed.append(token.upper())
            continue

        # Preserve explicitly quoted phrase
        if token.startswith('"') and token.endswith('"') and len(token) >= 2:
            clean_phrase = token[1:-1].replace('"', '""')
            processed.append(f'"{clean_phrase}"')
            continue

        clean = token.replace('"', '""')

        # Check if token contains code symbols or punctuation
        if any(c in clean for c in ".:_-/\\*?@$#`()[]^'~;"):
            processed.append(f'"{clean}"')
        else:
            # Standard word: support prefix search
            processed.append(f'"{clean}"*')

    return " ".join(processed)


def get_db_connection(db_path: Path, repo_root: Path) -> sqlite3.Connection:
    """
    Connects to the SQLite database.
    If the database file does not exist, transparently invokes kb_indexer.index_all().
    Registers the custom matches_version() SQLite user-defined function.
    """
    db_path = db_path.resolve()
    repo_root = repo_root.resolve()

    if not db_path.exists():
        try:
            from tools import kb_indexer
            kb_indexer.index_all(repo_root=repo_root, db_path=db_path, quiet=True)
        except ImportError:
            # Fallback path if tools is not in sys.path
            sys.path.insert(0, str(repo_root))
            from tools import kb_indexer
            kb_indexer.index_all(repo_root=repo_root, db_path=db_path, quiet=True)

    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row

    # Register matches_version UDF for in-engine SQL execution
    def py_matches_version(ver_str: str, target_ver: Any) -> int:
        if target_ver is None or str(target_ver).strip() in ("", "None"):
            return 1
        try:
            tv = float(target_ver)
        except (ValueError, TypeError):
            return 1
        rule = parse_version_rule(ver_str)
        return 1 if matches_version(rule, tv) else 0

    con.create_function("matches_version", 2, py_matches_version)
    return con


def extract_high_signal_summary(problem: str, raw_content: str) -> str:
    """Extracts a concise, high-signal problem summary."""
    if problem and problem.strip():
        # First 1-2 paragraphs
        paras = [p.strip() for p in problem.strip().split("\n\n") if p.strip()]
        if paras:
            summary = paras[0].replace("\n", " ")
            return summary[:300] + ("..." if len(summary) > 300 else "")

    # Fallback: scan overview or intro
    m_over = re.search(r"##\s+(?:Overview|Problem|Summary)\s*\n+(.*?)(?=\n##|\Z)", raw_content, re.DOTALL)
    if m_over:
        summary = m_over.group(1).strip().split("\n\n")[0].replace("\n", " ")
        return summary[:300] + ("..." if len(summary) > 300 else "")

    return "No explicit problem statement documented."


def extract_actionable_solution(solution: str, raw_content: str) -> str:
    """Extracts the most actionable solution snippet, preferring code blocks."""
    if solution and solution.strip():
        # Look for first code block in solution
        m_code = re.search(r"(```[\w]*\n.*?\n```)", solution, re.DOTALL)
        if m_code:
            code = m_code.group(1).strip()
            if len(code) <= 500:
                return code
            return code[:500] + "\n```"

        # Otherwise first paragraph
        paras = [p.strip() for p in solution.strip().split("\n\n") if p.strip()]
        if paras:
            snippet = paras[0].strip()
            return snippet[:400] + ("..." if len(snippet) > 400 else "")

    # Fallback to raw content code block
    m_code = re.search(r"(```(?:python|csv|xml|javascript|bash|sql)[\w]*\n.*?\n```)", raw_content, re.DOTALL)
    if m_code:
        return m_code.group(1).strip()[:500]

    return "Refer to full document for complete solution details."


def extract_pitfalls_list(pitfalls: str) -> List[str]:
    """Extracts critical pitfalls as clean bullet items."""
    if not pitfalls or not pitfalls.strip():
        return []
    lines = pitfalls.strip().splitlines()
    items: List[str] = []
    for line in lines:
        sline = line.strip()
        if sline.startswith("-") or sline.startswith("*"):
            clean_item = sline.lstrip("-* ").strip()
            if clean_item:
                items.append(clean_item)
        elif sline and not sline.startswith("#"):
            if len(items) == 0:
                items.append(sline)
    return items[:4]


def search(
    query: str,
    target_version: Optional[Union[float, int, str]] = None,
    category: Optional[str] = None,
    tags: Optional[Union[List[str], str]] = None,
    limit: int = 5,
    db_path: Optional[Path] = None,
    repo_root: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """
    Executes version-aware full-text search against .kb_cache.db.
    Applies BM25 column weights, strict version ontology matching,
    and two-tier version ranking.
    """
    if repo_root is None:
        repo_root = DEFAULT_REPO_ROOT
    repo_root = repo_root.resolve()

    if db_path is None:
        db_path = DEFAULT_DB_PATH
    db_path = db_path.resolve()

    # Normalize target version
    norm_version: Optional[float] = None
    if target_version is not None:
        v_str = str(target_version).strip().lower()
        if v_str not in ("all", "any", "", "none"):
            v_clean = v_str.lstrip("v")
            try:
                norm_version = float(v_clean)
            except ValueError:
                norm_version = None

    con = get_db_connection(db_path, repo_root)
    cur = con.cursor()

    sanitized_q = sanitize_fts5_query(query)

    # Build SQL parameters
    target_v_param = norm_version
    cat_param = f"%{category.strip().lower()}%" if category and category.strip() else None

    # Version priority pattern for two-tier ranking (e.g. "%20%")
    v_int_str = str(int(norm_version)) if norm_version is not None and norm_version.is_integer() else str(norm_version)
    ver_pat = f"%{v_int_str}%" if norm_version is not None else None
    tag_pat = f"%odoo{v_int_str}%" if norm_version is not None else None

    if not sanitized_q.strip():
        # Empty query: return most recent documents matching version / category filter
        sql = """
        SELECT e.id, e.file_path, e.title, e.category, e.severity, e.versions,
               e.tags, e.author, e.last_verified, e.problem, e.solution, e.pitfalls,
               e.raw_content, 0.0 AS bm_rank
        FROM kb_entries e
        WHERE (:target_ver IS NULL OR matches_version(e.versions, :target_ver) = 1)
          AND (:cat_param IS NULL OR LOWER(e.category) LIKE :cat_param)
        ORDER BY
          (CASE WHEN :target_ver IS NOT NULL AND (e.versions LIKE :ver_pat OR e.tags LIKE :tag_pat) THEN 0 ELSE 1 END) ASC,
          e.id ASC
        LIMIT :limit
        """
        cur.execute(sql, {
            "target_ver": target_v_param,
            "cat_param": cat_param,
            "ver_pat": ver_pat,
            "tag_pat": tag_pat,
            "limit": limit,
        })
    else:
        # FTS5 search with BM25 scoring:
        # Columns in kb_fts: (title, category, tags, problem, solution, pitfalls, raw_content)
        # BM25 weights: title: 10.0, category: 2.0, tags: 5.0, problem: 1.5, solution: 2.5, pitfalls: 2.0, content: 1.0
        sql = """
        SELECT e.id, e.file_path, e.title, e.category, e.severity, e.versions,
               e.tags, e.author, e.last_verified, e.problem, e.solution, e.pitfalls,
               e.raw_content,
               bm25(kb_fts, 10.0, 2.0, 5.0, 1.5, 2.5, 2.0, 1.0) AS bm_rank
        FROM kb_fts
        JOIN kb_entries e ON e.id = kb_fts.rowid
        WHERE kb_fts MATCH :query
          AND (:target_ver IS NULL OR matches_version(e.versions, :target_ver) = 1)
          AND (:cat_param IS NULL OR LOWER(e.category) LIKE :cat_param)
        ORDER BY
          (CASE WHEN :target_ver IS NOT NULL AND (e.versions LIKE :ver_pat OR e.tags LIKE :tag_pat) THEN 0 ELSE 1 END) ASC,
          bm_rank ASC
        LIMIT :limit
        """
        cur.execute(sql, {
            "query": sanitized_q,
            "target_ver": target_v_param,
            "cat_param": cat_param,
            "ver_pat": ver_pat,
            "tag_pat": tag_pat,
            "limit": limit,
        })

    rows = cur.fetchall()
    results: List[Dict[str, Any]] = []

    # Tag filter in Python if tags provided
    tag_filter_set = set()
    if tags:
        if isinstance(tags, str):
            tag_filter_set = {t.strip().lower() for t in tags.split(",") if t.strip()}
        else:
            tag_filter_set = {t.strip().lower() for t in tags if t.strip()}

    rank = 1
    for r in rows:
        row_tags = (r["tags"] or "").lower()
        if tag_filter_set and not any(tf in row_tags for tf in tag_filter_set):
            continue

        rel_path = r["file_path"]
        abs_path = (repo_root / rel_path).resolve()
        file_url = f"file://{abs_path}"

        prob_summary = extract_high_signal_summary(r["problem"] or "", r["raw_content"] or "")
        sol_snippet = extract_actionable_solution(r["solution"] or "", r["raw_content"] or "")
        pit_list = extract_pitfalls_list(r["pitfalls"] or "")
        pit_text = (r["pitfalls"] or "").strip()

        rec: Dict[str, Any] = {
            "rank": rank,
            "score": round(float(r["bm_rank"]), 4),
            "id": r["id"],
            "title": r["title"],
            "file_path": rel_path,
            "path": rel_path,
            "file_url": file_url,
            "category": r["category"],
            "severity": r["severity"] or "Normal",
            "versions": r["versions"],
            "odoo_versions": r["versions"],
            "tags": r["tags"] or "",
            "author": r["author"] or "ENG/Gamal Mansour",
            "last_verified": r["last_verified"] or "",
            "problem": r["problem"] or "",
            "problem_summary": prob_summary,
            "solution": r["solution"] or "",
            "solution_snippet": sol_snippet,
            "pitfalls": pit_text,
            "pitfalls_list": pit_list,
        }
        results.append(rec)
        rank += 1
        if len(results) >= limit:
            break

    con.close()
    return results


def format_results(
    results: List[Dict[str, Any]],
    fmt: str = "text",
    query: str = "",
    target_version: Optional[Union[float, int, str]] = None,
    category: Optional[str] = None,
) -> str:
    """
    Formats search results into human-readable text, markdown, compact summary, or JSON.
    """
    fmt = fmt.lower().strip()

    if fmt == "json":
        data = {
            "query": query,
            "version": target_version,
            "category": category,
            "total_hits": len(results),
            "results": results,
        }
        return json.dumps(data, indent=2, ensure_ascii=False)

    if fmt == "markdown":
        if not results:
            return f"*No knowledge entries found matching '{query}'.*"

        md_parts: List[str] = []
        for r in results:
            rank = r.get("rank", 1)
            title = r.get("title", "")
            path = r.get("file_path", r.get("path", ""))
            file_url = r.get("file_url", "")
            cat = r.get("category", "")
            sev = r.get("severity", "Normal")
            vers = r.get("versions", "")

            sol = r.get("solution_snippet") or r.get("solution") or "See file for solution."
            prob = r.get("problem_summary") or r.get("problem") or "See file for details."
            pit = r.get("pitfalls") or ""

            part = [
                f"### [{rank}] {title}",
                f"- **Path**: `{path}`",
                f"- **Location**: {file_url}",
                f"- **Category**: {cat} | **Severity**: {sev} | **Versions**: {vers}",
                "",
                "**Problem**:",
                f"> {prob}",
                "",
                "**Solution**:",
                f"{sol}",
            ]
            if pit:
                part.extend(["", "**⚠️ Critical Pitfalls**:", pit])
            md_parts.append("\n".join(part))

        return "\n\n---\n\n".join(md_parts)

    if fmt == "compact":
        if not results:
            return f"[No results found for '{query}']"

        lines: List[str] = []
        for r in results:
            rank = r.get("rank", 1)
            path = r.get("file_path", r.get("path", ""))
            vers = r.get("versions", "")
            sev = r.get("severity", "")
            sev_tag = f" [{sev}]" if sev else ""
            title = r.get("title", "")
            lines.append(f"[{rank}] {path} (v{vers}){sev_tag} — {title}")
            sol_prev = (r.get("solution_snippet") or r.get("solution") or "").replace("\n", " ").strip()
            if sol_prev:
                lines.append(f"    Solution: {sol_prev[:120]}...")
        return "\n".join(lines)

    # Default: "text" (Human ANSI format)
    if not results:
        return f"\n⚠️  No knowledge entries found matching '{query}'.\n"

    blocks: List[str] = []
    width = 80
    border = "=" * width
    thin_border = "-" * width

    for r in results:
        rank = r.get("rank", 1)
        title = r.get("title", "")
        path = r.get("file_path", r.get("path", ""))
        file_url = r.get("file_url", "")
        cat = r.get("category", "")
        sev = r.get("severity", "Normal")
        vers = r.get("versions", "")
        score = r.get("score", 0.0)

        prob = r.get("problem_summary") or r.get("problem") or "No details available."
        sol = r.get("solution_snippet") or r.get("solution") or "Refer to document."
        pit = r.get("pitfalls") or ""

        block_lines = [
            border,
            f"[{rank}] {title}",
            thin_border,
            f"Category: {cat} | Severity: {sev} | Versions: {vers} | Score: {score}",
            f"File: {file_url}",
            "",
            "[PROBLEM / OVERVIEW]",
            prob,
            "",
            "[ACTIONABLE SOLUTION]",
            sol,
        ]
        if pit:
            block_lines.extend(["", "[CRITICAL PITFALLS]", pit])
        block_lines.append(border)
        blocks.append("\n".join(block_lines))

    return "\n\n".join(blocks)


def print_db_info(db_path: Path, repo_root: Path) -> None:
    """Prints comprehensive database index statistics and cache metrics."""
    db_path = db_path.resolve()
    repo_root = repo_root.resolve()

    if not db_path.exists():
        print(f"Index database does not exist at: {db_path}")
        print("Run with --reindex to build index.")
        return

    con = sqlite3.connect(str(db_path))
    cur = con.cursor()

    cur.execute("SELECT count(*) FROM kb_entries")
    doc_count = cur.fetchone()[0]

    cur.execute("SELECT count(*) FROM kb_fts")
    fts_count = cur.fetchone()[0]

    size_mb = db_path.stat().st_size / (1024 * 1024)

    cur.execute("SELECT value FROM kb_metadata WHERE key = 'last_indexed'")
    row_time = cur.fetchone()
    last_indexed = "Unknown"
    if row_time:
        try:
            ts = float(row_time[0])
            last_indexed = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(ts))
        except ValueError:
            last_indexed = row_time[0]

    cur.execute("SELECT category, count(*) FROM kb_entries GROUP BY category ORDER BY count(*) DESC LIMIT 10")
    cat_counts = cur.fetchall()

    cur.execute("SELECT versions, count(*) FROM kb_entries GROUP BY versions ORDER BY count(*) DESC LIMIT 8")
    ver_counts = cur.fetchall()

    con.close()

    print("=" * 70)
    print("  Odoo Knowledge Base Index Statistics")
    print("=" * 70)
    print(f"Database Path:        {db_path}")
    print(f"Database Size:        {size_mb:.2f} MB")
    print(f"Total Documents:      {doc_count}")
    print(f"FTS5 Indexed Rows:    {fts_count}")
    print(f"Last Indexed:         {last_indexed}")
    print("-" * 70)
    print("Top Categories:")
    for cat, cnt in cat_counts:
        print(f"  • {cat:<20}: {cnt}")
    print("-" * 70)
    print("Version Distribution (Top):")
    for ver, cnt in ver_counts:
        print(f"  • {ver:<25}: {cnt}")
    print("=" * 70)


def build_parser() -> argparse.ArgumentParser:
    """Builds the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="kb",
        description="Version-aware local query tool for odoo-knowledge.",
    )
    parser.add_argument(
        "query",
        nargs="*",
        default=[],
        help="Search query tokens (e.g. 'kb ir.access.csv' or 'kb models.Constraint').",
    )
    parser.add_argument(
        "-v",
        "--version",
        dest="version",
        type=str,
        default=None,
        help="Target Odoo version (e.g. 20, 20.0, 19, 18, 17, 16, all).",
    )
    parser.add_argument(
        "-c",
        "--category",
        dest="category",
        type=str,
        default=None,
        help="Filter by category (e.g. upgrade, orm, security, views).",
    )
    parser.add_argument(
        "-t",
        "--tags",
        dest="tags",
        type=str,
        default=None,
        help="Filter by required tags (comma-separated, e.g. 'odoo20,constraints').",
    )
    parser.add_argument(
        "-n",
        "--limit",
        dest="limit",
        type=int,
        default=5,
        help="Maximum results returned (default: 5).",
    )
    parser.add_argument(
        "-f",
        "--format",
        dest="format",
        choices=["text", "markdown", "compact", "json"],
        default="text",
        help="Output format: text, markdown, compact, json (default: text).",
    )
    parser.add_argument(
        "-r",
        "--reindex",
        dest="reindex",
        action="store_true",
        default=False,
        help="Force full re-indexing of all markdown documents.",
    )
    parser.add_argument(
        "-i",
        "--info",
        dest="info",
        action="store_true",
        default=False,
        help="Print database index statistics and exit.",
    )
    parser.add_argument(
        "--db-path",
        dest="db_path",
        type=str,
        default=None,
        help="Custom path to .kb_cache.db.",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    """CLI entrypoint."""
    if argv is None:
        argv = sys.argv[1:]

    parser = build_parser()
    args = parser.parse_args(argv)

    repo_root = DEFAULT_REPO_ROOT
    db_path = Path(args.db_path).resolve() if args.db_path else DEFAULT_DB_PATH

    # Force reindex if requested
    if args.reindex:
        try:
            from tools import kb_indexer
            res = kb_indexer.index_all(repo_root=repo_root, db_path=db_path, force=True, quiet=False)
            if not args.info and not args.query:
                return 0
        except ImportError:
            sys.path.insert(0, str(repo_root))
            from tools import kb_indexer
            kb_indexer.index_all(repo_root=repo_root, db_path=db_path, force=True, quiet=False)
            if not args.info and not args.query:
                return 0

    # Print database statistics if requested
    if args.info:
        print_db_info(db_path, repo_root)
        return 0

    # Join positional query arguments
    query_str = " ".join(args.query).strip()

    # Execute search
    results = search(
        query=query_str,
        target_version=args.version,
        category=args.category,
        tags=args.tags,
        limit=args.limit,
        db_path=db_path,
        repo_root=repo_root,
    )

    # Format and print results
    formatted = format_results(
        results=results,
        fmt=args.format,
        query=query_str,
        target_version=args.version,
        category=args.category,
    )
    print(formatted)
    return 0


if __name__ == "__main__":
    sys.exit(main())
