#!/usr/bin/env python3
"""
High-Performance SQLite FTS5 Local Indexer for odoo-knowledge.

Zero external dependencies: Python standard library only.
Provides fast state-machine markdown parsing, metadata extraction,
incremental mtime-based caching, external content FTS5 virtual table,
and BM25 full-text indexing.
"""

import argparse
import hashlib
import os
from pathlib import Path
import re
import sqlite3
import sys
import time
from typing import Any, Dict, List, Optional, Set, Tuple

# Meta documents in repository root to ignore from searchable index
META_FILES: Set[str] = {"README.md", "CONTRIBUTING.md", "TEMPLATE.md"}

# Default repo root and DB cache path
DEFAULT_REPO_ROOT: Path = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH: Path = DEFAULT_REPO_ROOT / ".kb_cache.db"


def normalize_category(cat_raw: str, fallback_dir: str) -> str:
    """
    Normalizes category names:
    - Strips leading/trailing whitespace.
    - If empty or template placeholder, falls back to directory name.
    - Takes primary category before slash '/'.
    - Replaces spaces with underscores.
    - Normalizes plural 'upgrades' to 'upgrade'.
    """
    if not cat_raw or cat_raw.strip().startswith("setup / orm"):
        cat = fallback_dir if fallback_dir != "_root" else "misc"
    else:
        cat = cat_raw.split("/")[0].strip().lower()

    cat = cat.replace(" ", "_")
    if cat == "upgrades":
        cat = "upgrade"
    return cat


def classify_heading(htext: str) -> str:
    """
    Classifies a markdown section heading into one of the canonical sections:
    'problem', 'solution', 'pitfalls', 'root_cause', 'verification', or 'body'.
    """
    # Strip markdown formatting, emojis, and punctuation
    hclean = re.sub(r"[^\w\s]", "", htext).strip().lower()
    hclean = " ".join(hclean.split())

    if not hclean:
        return "body"

    # Problem variations
    if any(
        w in hclean
        for w in (
            "problem",
            "problem statement",
            "problem definition",
            "the problem",
            "symptom",
            "symptoms",
            "context",
            "scenario",
            "overview",
            "lesson",
        )
    ) or hclean.startswith("problem"):
        return "problem"

    # Solution variations
    if any(
        w in hclean
        for w in (
            "solution",
            "the solution",
            "solution best practice",
            "fix",
            "the fix",
            "workaround",
            "resolution",
            "pattern",
            "rule of thumb",
            "recipe",
        )
    ) or hclean.startswith("solution") or hclean.startswith("fix"):
        return "solution"

    # Pitfalls variations
    if any(
        w in hclean
        for w in (
            "pitfall",
            "pitfalls",
            "pitfalls to avoid",
            "common pitfalls",
            "gotcha",
            "gotchas",
            "warning",
            "warnings",
            "trap",
            "traps",
            "checklist",
            "caution",
        )
    ) or "pitfall" in hclean or "warning" in hclean or "trap" in hclean:
        return "pitfalls"

    # Root cause
    if "root cause" in hclean or hclean == "cause" or "cause analysis" in hclean:
        return "root_cause"

    # Verification
    if "verification" in hclean or "verify" in hclean or "test" in hclean:
        return "verification"

    # Other topic or numbered heading (e.g. '1. Security & Access Rules Revolution')
    return "body"


def parse_markdown_file(path: Path, repo_root: Optional[Path] = None) -> Dict[str, Any]:
    """
    Parses a markdown document into a structured record:
    {
        'file_path': str,
        'mtime': float,
        'file_hash': str,
        'title': str,
        'category': str,
        'versions': str,
        'severity': str,
        'tags': str,
        'author': str,
        'last_verified': str,
        'problem': str,
        'solution': str,
        'pitfalls': str,
        'raw_content': str,
    }
    """
    path = path.resolve()
    if repo_root is None:
        repo_root = DEFAULT_REPO_ROOT
    repo_root = repo_root.resolve()

    try:
        rel_path = str(path.relative_to(repo_root))
    except ValueError:
        # Fallback if path is outside repo_root
        parts = path.parts
        if "odoo-knowledge" in parts:
            idx = parts.index("odoo-knowledge")
            rel_path = str(Path(*parts[idx + 1:]))
        else:
            rel_path = path.name

    raw_bytes = path.read_bytes()
    raw_content = raw_bytes.decode("utf-8", errors="ignore")
    mtime = path.stat().st_mtime
    file_hash = hashlib.sha256(raw_bytes).hexdigest()[:16]

    parent_dir = path.parent.name if path.parent != repo_root else "_root"

    title = ""
    category_raw = ""
    versions = ""
    severity = ""
    tags = ""
    author = ""
    last_verified = ""

    lines = raw_content.splitlines()

    # 1. Check YAML frontmatter at file start
    frontmatter_lines: List[str] = []
    if lines and lines[0].strip() == "---":
        for i, line in enumerate(lines[1:], 1):
            if line.strip() == "---":
                frontmatter_lines = lines[1:i]
                lines = lines[i + 1:]
                break

    if frontmatter_lines:
        fm_text = "\n".join(frontmatter_lines)
        for fm_line in frontmatter_lines:
            if ":" in fm_line:
                k, v = fm_line.split(":", 1)
                k_clean = k.strip().lower()
                v_clean = v.strip().strip("\"'").strip()
                if k_clean in ("title", "name") and not title:
                    title = v_clean
                elif k_clean == "category" and not category_raw:
                    category_raw = v_clean
                elif k_clean in ("odoo_version", "odoo_versions", "version", "versions") and not versions:
                    versions = v_clean.strip("[]")
                elif k_clean == "severity" and not severity:
                    severity = v_clean
                elif k_clean == "author" and not author:
                    author = v_clean
                elif k_clean in ("last_verified", "date") and not last_verified:
                    last_verified = v_clean

        # Extract tags from frontmatter
        m_tags = re.search(r"tags:\s*\[(.*?)\]", fm_text, re.DOTALL)
        if m_tags:
            tags = ", ".join(t.strip().strip("\"'") for t in m_tags.group(1).split(",") if t.strip())
        elif "tags:" in fm_text:
            t_list = []
            capture = False
            for f_line in frontmatter_lines:
                if f_line.strip().startswith("tags:"):
                    capture = True
                    continue
                if capture:
                    if f_line.strip().startswith("-"):
                        t_list.append(f_line.strip().lstrip("-").strip().strip("\"'"))
                    elif f_line and not f_line.startswith(" "):
                        break
            if t_list:
                tags = ", ".join(t_list)

    # 2. Extract Metadata (Table format, Inline Bold KV, H1 Title)
    # Using state machine tracking in_code_block so code comments are skipped
    in_code_block = False
    for line in lines:
        sline = line.strip()
        if sline.startswith("```") or sline.startswith("~~~"):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue

        # H1 title
        if not title and re.match(r"^#\s+[^#]", line):
            cand = re.sub(r"^#\s+", "", line).strip()
            # Clean possible markdown bold/quotes
            cand = cand.strip("*_`\"'").strip()
            # Remove leading emojis if present
            cleaned_cand = re.sub(r"^[^\w\s]+\s*", "", cand).strip()
            title = cleaned_cand if cleaned_cand else cand

        # Table rows (| Key | Value |)
        if "|" in line:
            parts = [p.strip() for p in line.split("|") if p.strip()]
            if len(parts) >= 2:
                k_clean = parts[0].lower().replace(":", "").strip()
                v_clean = parts[1].strip()
                if k_clean == "category" and not category_raw:
                    category_raw = v_clean
                elif k_clean in ("odoo versions", "versions") and not versions:
                    versions = v_clean
                elif k_clean == "severity" and not severity:
                    severity = v_clean
                elif k_clean == "author" and not author:
                    author = v_clean
                elif k_clean in ("last verified", "last_verified") and not last_verified:
                    last_verified = v_clean

        # Bold KV lines (- **Key:** Value or **Key**: Value)
        kv_m = re.match(r"^\s*[-*]?\s*\*\*([^*]+)\*\*:?\s*(.+)$", line)
        if kv_m:
            k_clean = kv_m.group(1).rstrip(":").lower().strip()
            v_clean = kv_m.group(2).strip()
            if k_clean == "category" and not category_raw:
                category_raw = v_clean
            elif k_clean in ("odoo versions", "versions", "version") and not versions:
                versions = v_clean
            elif k_clean == "severity" and not severity:
                severity = v_clean
            elif k_clean == "author" and not author:
                author = v_clean
            elif k_clean in ("last verified", "last_verified", "date") and not last_verified:
                last_verified = v_clean
            elif k_clean == "tags" and not tags:
                tags = v_clean.replace("`", "")

    # Fallback for tags if not found
    if not tags:
        m_tags = re.search(r"\*\*Tags:\*\*\s*(.+)", raw_content, re.IGNORECASE)
        if m_tags:
            tags = m_tags.group(1).strip().replace("`", "")

    # Normalization & fallbacks
    category = normalize_category(category_raw, parent_dir)

    if not title:
        title = path.stem.replace("-", " ").replace("_", " ").title()

    if not versions:
        # Fallback: scan relative path and title for version hints (e.g. odoo19, v20)
        v_hints = re.findall(r"(?:odoo|v|version)\s*(\d{2})", f"{rel_path} {title}", re.IGNORECASE)
        if v_hints:
            versions = ", ".join(sorted(set(v_hints)))
        else:
            versions = "All"

    if not author:
        author = "ENG/Gamal Mansour"

    # 3. Section Classifier State Machine
    # Tracks sections: problem, solution, pitfalls, root_cause, verification, body
    # Subsections (### and ####) stay inside their active parent section.
    current_section = "intro"
    sections: Dict[str, List[str]] = {
        "intro": [],
        "problem": [],
        "solution": [],
        "pitfalls": [],
        "root_cause": [],
        "verification": [],
        "body": [],
    }

    in_code_block = False
    for line in lines:
        sline = line.strip()
        if sline.startswith("```") or sline.startswith("~~~"):
            in_code_block = not in_code_block
            if current_section in sections:
                sections[current_section].append(line)
            continue

        if in_code_block:
            if current_section in sections:
                sections[current_section].append(line)
            continue

        # Check for section headings outside code blocks
        # Only '#' and '##' trigger section transitions.
        # '###' and '####' are subheadings that belong to the active section.
        heading_match = re.match(r"^(#{1,2})\s+(.+)$", line)
        if heading_match:
            hashes, htext = heading_match.group(1), heading_match.group(2).strip()
            # If line is H1, check if it's a section or the document title
            if hashes == "#":
                h_sec = classify_heading(htext)
                # If H1 is a recognized section (e.g. '# 📝 Problem' or '# ✅ Solution')
                if h_sec in ("problem", "solution", "pitfalls", "root_cause", "verification"):
                    current_section = h_sec
                    continue
                # Otherwise, it is the title line, ignore it for section text
                continue

            # Level 2 heading '## ...'
            sec_classified = classify_heading(htext)
            current_section = sec_classified
            # If it's a body/topic heading (e.g. '## 1. Security Revolution'), also keep heading in body
            if sec_classified == "body":
                sections["body"].append(line)
            continue

        if current_section in sections:
            sections[current_section].append(line)

    problem_text = "\n".join(sections["problem"]).strip()
    solution_text = "\n".join(sections["solution"]).strip()
    pitfalls_text = "\n".join(sections["pitfalls"]).strip()
    root_cause_text = "\n".join(sections["root_cause"]).strip()
    body_text = "\n".join(sections["body"]).strip()

    # Fallback logic for cookbook/architectural documents lacking explicit '## Solution'
    if not solution_text and body_text:
        solution_text = body_text

    if not problem_text and root_cause_text:
        problem_text = root_cause_text

    if not problem_text and sections["intro"]:
        # Extract introductory text (ignoring table and bold KV lines)
        intro_paras = []
        for iline in sections["intro"]:
            s_iline = iline.strip()
            if not s_iline or s_iline.startswith("|") or s_iline.startswith("- **") or s_iline.startswith("**"):
                continue
            intro_paras.append(s_iline)
        if intro_paras:
            problem_text = "\n".join(intro_paras).strip()

    return {
        "file_path": rel_path,
        "mtime": mtime,
        "file_hash": file_hash,
        "title": title,
        "category": category,
        "versions": versions,
        "severity": severity,
        "tags": tags,
        "author": author,
        "last_verified": last_verified,
        "problem": problem_text,
        "solution": solution_text,
        "pitfalls": pitfalls_text,
        "raw_content": raw_content,
    }


def init_db(db_path: Path) -> sqlite3.Connection:
    """
    Initializes SQLite connection, configures high-performance WAL pragmas,
    creates metadata table, entries table, FTS5 virtual table, and
    synchronization triggers.
    """
    db_path = db_path.resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row

    # Performance pragmas
    con.execute("PRAGMA journal_mode = WAL")
    con.execute("PRAGMA synchronous = NORMAL")
    con.execute("PRAGMA temp_store = MEMORY")
    con.execute("PRAGMA cache_size = -64000")
    con.execute("PRAGMA mmap_size = 268435456")

    cur = con.cursor()

    # 1. Metadata table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS kb_metadata (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    """)

    # 2. Entries table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS kb_entries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        file_path TEXT UNIQUE NOT NULL,
        mtime REAL NOT NULL,
        file_hash TEXT,
        title TEXT NOT NULL,
        category TEXT NOT NULL,
        versions TEXT NOT NULL,
        severity TEXT,
        tags TEXT,
        author TEXT,
        last_verified TEXT,
        problem TEXT,
        solution TEXT,
        pitfalls TEXT,
        raw_content TEXT NOT NULL
    )
    """)

    cur.execute("CREATE INDEX IF NOT EXISTS idx_kb_entries_path ON kb_entries(file_path)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_kb_entries_category ON kb_entries(category)")

    # 3. FTS5 Virtual Table (External Content Table referencing kb_entries)
    cur.execute("""
    CREATE VIRTUAL TABLE IF NOT EXISTS kb_fts USING fts5(
        title,
        category,
        tags,
        problem,
        solution,
        pitfalls,
        raw_content,
        content='kb_entries',
        content_rowid='id',
        tokenize='porter unicode61 remove_diacritics 2'
    )
    """)

    # 4. Synchronization Triggers
    cur.execute("""
    CREATE TRIGGER IF NOT EXISTS kb_entries_ai AFTER INSERT ON kb_entries BEGIN
        INSERT INTO kb_fts(rowid, title, category, tags, problem, solution, pitfalls, raw_content)
        VALUES (new.id, new.title, new.category, new.tags, new.problem, new.solution, new.pitfalls, new.raw_content);
    END;
    """)

    cur.execute("""
    CREATE TRIGGER IF NOT EXISTS kb_entries_ad AFTER DELETE ON kb_entries BEGIN
        INSERT INTO kb_fts(kb_fts, rowid, title, category, tags, problem, solution, pitfalls, raw_content)
        VALUES ('delete', old.id, old.title, old.category, old.tags, old.problem, old.solution, old.pitfalls, old.raw_content);
    END;
    """)

    cur.execute("""
    CREATE TRIGGER IF NOT EXISTS kb_entries_au AFTER UPDATE ON kb_entries BEGIN
        INSERT INTO kb_fts(kb_fts, rowid, title, category, tags, problem, solution, pitfalls, raw_content)
        VALUES ('delete', old.id, old.title, old.category, old.tags, old.problem, old.solution, old.pitfalls, old.raw_content);
        INSERT INTO kb_fts(rowid, title, category, tags, problem, solution, pitfalls, raw_content)
        VALUES (new.id, new.title, new.category, new.tags, new.problem, new.solution, new.pitfalls, new.raw_content);
    END;
    """)

    con.commit()
    return con


def get_valid_markdown_files(repo_root: Path) -> List[Path]:
    """
    Finds all indexable markdown files in repo_root:
    - Skips hidden directories (e.g. .git)
    - Skips repo meta files (README.md, CONTRIBUTING.md, TEMPLATE.md)
    - Skips non-markdown files (.pdf, etc.)
    """
    repo_root = repo_root.resolve()
    valid_files: List[Path] = []

    for root, dirs, files in os.walk(repo_root):
        # Exclude hidden directories
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for f in files:
            if not f.endswith(".md"):
                continue
            if f in META_FILES:
                continue
            valid_files.append(Path(root) / f)

    return sorted(valid_files)


def index_all(
    repo_root: Optional[Path] = None,
    db_path: Optional[Path] = None,
    force: bool = False,
    quiet: bool = False,
) -> Dict[str, Any]:
    """
    Scans repo_root for indexable markdown documents.
    Performs fast incremental mtime checking against SQLite database.
    Updates changed documents, removes deleted documents, inserts new documents.
    Returns stats dict: {'total_files': int, 'indexed': int, 'deleted': int, 'elapsed_sec': float, 'db_path': str}
    """
    t_start = time.perf_counter()

    if repo_root is None:
        repo_root = DEFAULT_REPO_ROOT
    repo_root = repo_root.resolve()

    if db_path is None:
        db_path = DEFAULT_DB_PATH
    db_path = db_path.resolve()

    # Discover files on disk
    disk_files = get_valid_markdown_files(repo_root)
    disk_map: Dict[str, Path] = {}
    disk_mtimes: Dict[str, float] = {}

    for p in disk_files:
        rel = str(p.relative_to(repo_root))
        disk_map[rel] = p
        disk_mtimes[rel] = p.stat().st_mtime

    total_files = len(disk_map)

    # If force rebuild, remove existing db file if present
    if force and db_path.exists():
        con_temp = None
        try:
            # Check if active connection before removing
            db_path.unlink()
            for ext in ("-wal", "-shm"):
                p_extra = db_path.parent / (db_path.name + ext)
                if p_extra.exists():
                    p_extra.unlink()
        except OSError:
            pass

    con = init_db(db_path)
    cur = con.cursor()

    cur.execute("SELECT file_path, mtime FROM kb_entries")
    db_records = dict(cur.fetchall())

    to_index: List[str] = []
    to_delete: List[str] = []

    if force:
        # Re-index all files
        to_index = list(disk_map.keys())
        to_delete = [p for p in db_records if p not in disk_map]
    else:
        # Incremental check
        for rel_p, mt in disk_mtimes.items():
            if rel_p not in db_records or mt != db_records[rel_p]:
                to_index.append(rel_p)

        for rel_p in db_records:
            if rel_p not in disk_map:
                to_delete.append(rel_p)

    indexed_count = 0
    deleted_count = len(to_delete)

    # Perform updates in a single batch transaction
    if to_index or to_delete:
        con.execute("BEGIN TRANSACTION")

        # Delete removed files
        for rel_p in to_delete:
            cur.execute("DELETE FROM kb_entries WHERE file_path = ?", (rel_p,))

        # Parse and insert/update
        parsed_batch: List[Dict[str, Any]] = []
        for rel_p in to_index:
            abs_p = disk_map[rel_p]
            rec = parse_markdown_file(abs_p, repo_root)
            parsed_batch.append(rec)

        for rec in parsed_batch:
            cur.execute("""
            INSERT INTO kb_entries (
                file_path, mtime, file_hash, title, category, versions, severity,
                tags, author, last_verified, problem, solution, pitfalls, raw_content
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(file_path) DO UPDATE SET
                mtime = excluded.mtime,
                file_hash = excluded.file_hash,
                title = excluded.title,
                category = excluded.category,
                versions = excluded.versions,
                severity = excluded.severity,
                tags = excluded.tags,
                author = excluded.author,
                last_verified = excluded.last_verified,
                problem = excluded.problem,
                solution = excluded.solution,
                pitfalls = excluded.pitfalls,
                raw_content = excluded.raw_content
            """, (
                rec["file_path"],
                rec["mtime"],
                rec["file_hash"],
                rec["title"],
                rec["category"],
                rec["versions"],
                rec["severity"],
                rec["tags"],
                rec["author"],
                rec["last_verified"],
                rec["problem"],
                rec["solution"],
                rec["pitfalls"],
                rec["raw_content"],
            ))

        indexed_count = len(parsed_batch)

        # Update metadata timestamp
        cur.execute("""
        INSERT INTO kb_metadata(key, value) VALUES('last_indexed', ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """, (str(time.time()),))

        cur.execute("""
        INSERT INTO kb_metadata(key, value) VALUES('total_indexed', ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """, (str(total_files),))

        con.commit()

    elapsed = time.perf_counter() - t_start

    stats = {
        "total_files": total_files,
        "indexed": indexed_count,
        "deleted": deleted_count,
        "elapsed_sec": round(elapsed, 4),
        "db_path": str(db_path),
    }

    if not quiet:
        mode_str = "Full re-index" if force else "Incremental sync"
        print(f"[{mode_str}] Scanned {total_files} files, indexed {indexed_count}, removed {deleted_count} in {elapsed*1000:.2f} ms")

    con.close()
    return stats


def get_db_stats(db_path: Path) -> Dict[str, Any]:
    """
    Returns statistical overview of the index database.
    """
    if not db_path.exists():
        return {"exists": False}

    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    cur.execute("SELECT COUNT(*) as cnt FROM kb_entries")
    total_docs = cur.fetchone()["cnt"]

    cur.execute("SELECT category, COUNT(*) as cnt FROM kb_entries GROUP BY category ORDER BY cnt DESC")
    cats = {row["category"]: row["cnt"] for row in cur.fetchall()}

    cur.execute("SELECT key, value FROM kb_metadata")
    meta = {row["key"]: row["value"] for row in cur.fetchall()}

    db_size = db_path.stat().st_size
    con.close()

    return {
        "exists": True,
        "total_documents": total_docs,
        "categories": cats,
        "db_size_bytes": db_size,
        "db_size_mb": round(db_size / (1024 * 1024), 2),
        "metadata": meta,
    }


def main():
    parser = argparse.ArgumentParser(
        description="High-Performance SQLite FTS5 Indexer for odoo-knowledge."
    )
    parser.add_argument(
        "--force", "-f", action="store_true", help="Force complete re-indexing of all documents"
    )
    parser.add_argument(
        "--db-path", type=str, default=str(DEFAULT_DB_PATH), help="Path to SQLite cache DB"
    )
    parser.add_argument(
        "--root", type=str, default=str(DEFAULT_REPO_ROOT), help="Path to odoo-knowledge repository root"
    )
    parser.add_argument(
        "--quiet", "-q", action="store_true", help="Suppress console progress output"
    )
    parser.add_argument(
        "--stats", "-s", action="store_true", help="Display index database statistics and exit"
    )

    args = parser.parse_args()

    repo_root = Path(args.root)
    db_path = Path(args.db_path)

    if args.stats:
        stats = get_db_stats(db_path)
        if not stats["exists"]:
            print(f"Database does not exist at: {db_path}")
            sys.exit(1)
        print("=" * 60)
        print("Odoo Knowledge Index Statistics")
        print("=" * 60)
        print(f"Database Path:   {db_path}")
        print(f"Total Documents: {stats['total_documents']}")
        print(f"Database Size:   {stats['db_size_mb']} MB ({stats['db_size_bytes']} bytes)")
        print(f"Last Indexed:    {stats['metadata'].get('last_indexed', 'N/A')}")
        print("\nTop Categories:")
        for cat, cnt in list(stats["categories"].items())[:10]:
            print(f"  - {cat:20s}: {cnt}")
        sys.exit(0)

    index_all(repo_root=repo_root, db_path=db_path, force=args.force, quiet=args.quiet)


if __name__ == "__main__":
    main()
