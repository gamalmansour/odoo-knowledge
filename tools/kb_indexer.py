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
    Normalizes category names into canonical categories:
    - Strips leading/trailing whitespace and parenthetical/compound qualifiers.
    - If empty or template placeholder, falls back to directory name.
    - Takes primary category before slash '/'.
    - Replaces spaces with underscores and lowercases.
    - Maps legacy/synonym categories ('upgrades', 'models', 'architecture', etc.)
      to their canonical equivalents.
    """
    if not cat_raw or cat_raw.strip().startswith("setup / orm"):
        cat = fallback_dir if fallback_dir != "_root" else "misc"
    else:
        cat = cat_raw.split("/")[0].strip()

    cat = cat.split("(")[0].split("&")[0].strip().lower()
    cat = re.sub(r"[\s-]+", "_", cat).strip("_")

    synonyms = {
        "upgrades": "upgrade",
        "models": "orm",
        "accounting": "orm",
        "sale": "orm",
        "architecture": "best_practices",
        "portal": "views",
        "point_of_sale": "views",
    }
    return synonyms.get(cat, cat or "misc")


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
            # Remove leading emojis / decorative symbols while preserving ASCII punctuation and Arabic text
            cand = re.sub(r"^[^\x20-\x7E\u0600-\u06FF]+\s*", "", cand).strip()
            # Only unwrap balanced outer wrappers (**...**, "...", '...', `...`, [...])
            for open_w, close_w in (("**", "**"), ("\"", "\""), ("'", "'"), ("`", "`"), ("[", "]")):
                if cand.startswith(open_w) and cand.endswith(close_w) and len(cand) > len(open_w) + len(close_w):
                    inner = cand[len(open_w):-len(close_w)].strip()
                    if open_w not in inner:
                        cand = inner
            title = cand

        # Table rows (| Key | Value | or | **Key** | Value |)
        if "|" in line:
            parts = [p.strip() for p in line.split("|") if p.strip()]
            if len(parts) >= 2:
                k_clean = parts[0].strip("*_` ").lower().replace(":", "").strip()
                v_clean = parts[1].strip("*_` ").strip()
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
                    tags = parts[1].replace("`", "").strip()

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
        m_tags = re.search(r"\*\*Tags:?\*\*:?\s*(.+)", raw_content, re.IGNORECASE)
        if m_tags:
            tags = m_tags.group(1).strip().replace("`", "")

    # Normalize #hashtag style tags (e.g. '#addons #collision' -> 'addons, collision')
    if tags and "#" in tags and "," not in tags:
        hash_tokens = [t.lstrip("#").strip() for t in tags.split() if t.lstrip("#").strip()]
        if hash_tokens:
            tags = ", ".join(hash_tokens)

    # Normalization & fallbacks
    category = normalize_category(category_raw, parent_dir)

    if not title:
        title = path.stem.replace("-", " ").replace("_", " ").title()

    if not tags:
        stop_words = {"and", "the", "for", "with", "from", "into", "when", "not", "all", "via", "how", "use", "using"}
        stem_tokens = [
            w for w in re.split(r"[-_]+", path.stem.lower())
            if len(w) >= 3 and w not in stop_words
        ]
        tags = ", ".join(stem_tokens[:5]) if stem_tokens else category

    if not severity:
        crit_keywords = ("crash", "error", "deadlock", "violation", "loss", "security", "wipes", "blocks", "500", "critical")
        if any(k in f"{title} {path.stem}".lower() for k in crit_keywords):
            severity = "🔴 Critical"
        else:
            severity = "🟡 Medium"

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

    con = init_db(db_path)
    cur = con.cursor()

    to_index: List[str] = []
    to_delete: List[str] = []

    if force:
        # Re-index all files
        to_index = list(disk_map.keys())
        to_delete = []
    else:
        # Incremental check
        cur.execute("SELECT file_path, mtime FROM kb_entries")
        db_records = dict(cur.fetchall())

        for rel_p, mt in disk_mtimes.items():
            if rel_p not in db_records or mt != db_records[rel_p]:
                to_index.append(rel_p)

        for rel_p in db_records:
            if rel_p not in disk_map:
                to_delete.append(rel_p)

    indexed_count = 0
    deleted_count = len(to_delete)

    # Perform updates in a single batch transaction
    if to_index or to_delete or force:
        con.execute("BEGIN IMMEDIATE")

        # When force rebuilding, safely truncate tables within transaction
        # rather than unlinking DB files from disk, preserving open readers
        # and WAL shared-memory mapping.
        if force:
            cur.execute("DELETE FROM kb_entries")
            cur.execute("DELETE FROM kb_metadata")

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


def generate_readme(repo_root: Optional[Path] = None) -> Path:
    """
    Generates a clean, sequentially numbered, and fully synchronized README.md
    from all markdown documents on disk, grouped into Part I (Odoo ERP Core)
    and Part II (Cross-Platform, Mobile & Game Engine R&D).
    """
    if repo_root is None:
        repo_root = DEFAULT_REPO_ROOT
    repo_root = repo_root.resolve()

    odoo_sections = [
        ("setup", "Setup & Environment", "setup/", "Installation, environment configuration, OS dependencies, multi-instance setups, and pre-sales seeding"),
        ("database", "Database & PostgreSQL", "database/", "PostgreSQL administration, ownership (`datdba`), schema privileges, safe truncation, and DB lifecycle"),
        ("orm", "ORM, Models & Business Logic", "orm/", "Models, fields, `@api.depends`, `@api.constrains`, CRUD overrides, and accounting/stock/HR domain logic"),
        ("views", "Views, QWeb Reports & Actions", "views/", "XML views (Form, List, Kanban, Search, Gantt), QWeb PDF layouts, window actions, and XPath"),
        ("frontend", "Frontend, OWL & POS UI", "frontend/", "OWL 2/3 components, JavaScript widgets, POS screens, Portal JS, and WebGL/Canvas client actions"),
        ("backend", "Backend, Controllers, APIs & Testing", "backend/", "HTTP/JSON-RPC controllers, REST auth, `TransactionCase`/`HttpCase` testing, server actions, and hardware bridges"),
        ("security", "Security, ACLs & Multi-Company", "security/", "Access rights (`ir.model.access.csv` / `ir.access.csv`), record rules (`ir.rule`), groups, and multi-company isolation"),
        ("performance", "Performance & Query Optimization", "performance/", "SQL profiling, N+1 prevention, batch engines, PostgreSQL window functions, and caching"),
        ("upgrade", "Upgrades & Version Migrations", "upgrade/", "Version migrations (Odoo 15 → 20), breaking API changes, and code replacement cookbooks"),
        ("data_migration", "Data Migration & ETL Imports", "data_migration/", "Complex Excel/CSV imports, header auto-mapping, relational resolution, and barcode/product ETL"),
        ("deployment", "Deployment & Production DevOps", "deployment/", "Ubuntu production provisioning, Nginx, Systemd, SSL, and zero-downtime upgrade safety"),
        ("Best Practices", "Enterprise Best Practices & Compliance", "Best Practices/", "ERP architecture, Saudi (ZATCA, Etimad, GTPL, SBC, Wafi, Nitaqat) & Egyptian compliance, and audit protocols"),
        ("misc", "Localization, Integrations & Misc", "misc/", "Arabic `i18n`/`.po` mechanics, ZATCA/SdI e-invoicing, Salla webhooks, SEO sitemaps, and Odoo Apps Store standards"),
    ]

    cp_sections = [
        ("cross_platform", "Cross-Platform, Unity 6, Mobile & Media R&D", "cross_platform/", "Unity 6 (URP, IL2CPP, Mecanim, Action-RPG), Flutter iOS physical device deployment, Mobile Arabic BiDi, and media pipelines"),
    ]

    files = get_valid_markdown_files(repo_root)
    by_folder: Dict[str, List[Dict[str, Any]]] = {}
    for f in files:
        rel = f.relative_to(repo_root)
        folder = rel.parts[0] if len(rel.parts) > 1 else "misc"
        rec = parse_markdown_file(f, repo_root)
        rec["_rel_path"] = str(rel)
        rec["_file_name"] = f.name
        by_folder.setdefault(folder, []).append(rec)

    for folder in by_folder:
        by_folder[folder].sort(key=lambda r: r["_file_name"].lower())

    total_entries = len(files)
    odoo_count = sum(len(by_folder.get(k, [])) for k, _, _, _ in odoo_sections)
    cp_count = sum(len(by_folder.get(k, [])) for k, _, _, _ in cp_sections)
    today_str = time.strftime("%Y-%m-%d", time.gmtime())

    lines: List[str] = [
        "# 🧠 Odoo & Enterprise Engineering Knowledge Base",
        "",
        "> A production-grade, version-aware institutional memory for solving recurring **Odoo ERP (v14 → v20)**, **DevOps**, and **Cross-Platform** engineering challenges.",
        "> Maintained by **ENG/Gamal Mansour** and team — built for both **Senior Engineers** and **AI Agents** (Antigravity / Gemini / Claude).",
        "",
        "---",
        "",
        "## ⚡ Fast Local Search Engine (`./kb`) — Start Here",
        "",
        "**Do NOT read this entire `README.md` into an AI Agent's context window.**",
        "This repository includes a zero-dependency, sub-20ms **SQLite FTS5 BM25** query CLI (`./kb`) with strict **Odoo Version Ontology** filtering:",
        "",
        "```bash",
        "# 1. Search by model, field, error message, or keyword filtered to your target Odoo version:",
        "./kb \"account.move\" -v 18",
        "./kb \"models.Constraint\" -v 20 -c upgrade",
        "./kb \"ir.rule\" -v 19 -f compact",
        "",
        "# 2. View index statistics or rebuild the SQLite FTS5 cache + README index:",
        "./kb --info",
        "./kb --reindex",
        "```",
        "",
        "- **For AI Agents:** Always query `./kb \"<keyword>\" -v <detected_odoo_version>` first (see [CONTRIBUTING.md](CONTRIBUTING.md)).",
        "- **For Developers:** Use `./kb` in your terminal or browse the categorized tables below.",
        "",
        "---",
        "",
        "## 📂 Repository Architecture & Categories",
        "",
        f"### Part I — Odoo ERP Core & Enterprise Architecture ({odoo_count} Entries)",
        "",
        "| Category | Folder | Entries | Scope |",
        "|---|---|---:|---|",
    ]

    for folder_key, title, folder_disp, desc in odoo_sections:
        cnt = len(by_folder.get(folder_key, []))
        anchor = title.lower().replace("&", "").replace(",", "").replace("/", "").replace("(", "").replace(")", "")
        anchor = "-".join(anchor.split())
        lines.append(f"| **[{title}](#{anchor})** | `{folder_disp}` | **{cnt}** | {desc} |")

    lines.extend([
        "",
        f"### Part II — Cross-Platform, Mobile & Game Engine R&D ({cp_count} Entries)",
        "",
        "| Category | Folder | Entries | Scope |",
        "|---|---|---:|---|",
    ])

    for folder_key, title, folder_disp, desc in cp_sections:
        cnt = len(by_folder.get(folder_key, []))
        lines.append(f"| **[{title}](#cross-platform-unity-6-mobile--media-rd)** | `{folder_disp}` | **{cnt}** | {desc} |")

    lines.extend([
        "",
        "---",
        "",
        "## 📋 Part I — Odoo ERP Knowledge Index",
        "",
    ])

    def _render_table(entries: List[Dict[str, Any]]) -> List[str]:
        t_lines = [
            "| # | File | Severity | Versions | Tags | Summary |",
            "|---:|---|---|---|---|---|",
        ]
        for idx, r in enumerate(entries, 1):
            fname = r["_file_name"]
            rel_link = r["_rel_path"].replace(" ", "%20")
            sev = (r.get("severity") or "🟡 Medium").replace("|", "/").strip()
            vers = (r.get("versions") or "All").replace("|", "/").strip()
            if len(vers) > 28:
                vers = vers[:25].rstrip(", ") + "..."

            raw_tags = [t.strip() for t in (r.get("tags") or "").split(",") if t.strip()][:5]
            tags_fmt = ", ".join(f"`{t}`" for t in raw_tags) if raw_tags else "`odoo`"

            title_clean = (r.get("title") or fname).replace("|", "-").replace("\n", " ").strip()
            if len(title_clean) > 130:
                title_clean = title_clean[:127] + "..."

            t_lines.append(
                f"| {idx} | [{fname}]({rel_link}) | {sev} | {vers} | {tags_fmt} | {title_clean} |"
            )
        return t_lines

    for folder_key, title, folder_disp, desc in odoo_sections:
        entries = by_folder.get(folder_key, [])
        lines.append(f"### {title}")
        lines.append("")
        lines.append(f"> **Folder:** `{folder_disp}` · **Entries:** {len(entries)} · {desc}")
        lines.append("")
        lines.extend(_render_table(entries))
        lines.append("")

    lines.extend([
        "---",
        "",
        "## 🎮 Part II — Cross-Platform, Mobile & Game Engine R&D Index",
        "",
        "> Isolated in `cross_platform/` so non-Odoo R&D (Unity 6, Flutter iOS, Mobile BiDi, and Media pipelines) never pollutes Odoo ERP categories.",
        "",
    ])

    for folder_key, title, folder_disp, desc in cp_sections:
        entries = by_folder.get(folder_key, [])
        lines.append(f"### {title}")
        lines.append("")
        lines.append(f"> **Folder:** `{folder_disp}` · **Entries:** {len(entries)} · {desc}")
        lines.append("")
        lines.extend(_render_table(entries))
        lines.append("")

    lines.extend([
        "---",
        "",
        "## 🔧 Quick Reference & Repository Stats",
        "",
        "```text",
        "odoo-knowledge/",
        "├── kb                      ← Sub-20ms CLI search launcher (SQLite FTS5 + BM25)",
        "├── tools/                  ← Indexer (kb_indexer.py) & Query Engine (kb_query.py)",
        "├── tests/                  ← Automated 66-test verification suite (run_tests.py)",
        "├── README.md               ← Auto-generated categorized index",
        "├── CONTRIBUTING.md         ← Workflow for Engineers & AI Agents",
        "├── TEMPLATE.md             ← Standard entry template",
    ])

    all_sections = odoo_sections + cp_sections
    for i, (folder_key, _, folder_disp, _) in enumerate(all_sections):
        cnt = len(by_folder.get(folder_key, []))
        branch = "└──" if i == len(all_sections) - 1 else "├──"
        pad = " " * max(1, 24 - len(folder_disp))
        lines.append(f"{branch} {folder_disp}{pad}← {cnt} entries")

    lines.extend([
        "```",
        "",
        f"- **Total Indexed Entries:** {total_entries} ({odoo_count} Odoo ERP + {cp_count} Cross-Platform R&D)",
        f"- **Last Synchronized:** {today_str}",
        "- **Lead Author & Maintainer:** ENG/Gamal Mansour",
        "- **Contributors:** ENG/Gamal Mansour, ENG/Mohamed Saber, ENG/Mohamed Hamdy",
        "",
        "---",
        "",
        "## 🤝 Contributing",
        "",
        "See [CONTRIBUTING.md](CONTRIBUTING.md) for the complete contribution workflow.",
        "",
        "1. Copy `TEMPLATE.md` into the appropriate category folder.",
        "2. Fill in all metadata fields (`Category`, `Odoo Versions`, `Severity`, `Last Verified`, `Author`, `Tags`).",
        "3. Run `python3 tools/kb_indexer.py --force --update-readme` (or `./kb --reindex`) to rebuild the FTS5 cache and regenerate `README.md`.",
        "4. Commit and push to `origin main`.",
        "",
    ])

    readme_path = repo_root / "README.md"
    readme_path.write_text("\n".join(lines), encoding="utf-8")
    return readme_path


def main():
    parser = argparse.ArgumentParser(
        description="High-Performance SQLite FTS5 Indexer for odoo-knowledge."
    )
    parser.add_argument(
        "--force", "-f", action="store_true", help="Force complete re-indexing of all documents"
    )
    parser.add_argument(
        "--update-readme", "-u", action="store_true", help="Regenerate README.md from all indexed files"
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
        for cat, cnt in list(stats["categories"].items())[:15]:
            print(f"  - {cat:20s}: {cnt}")
        sys.exit(0)

    index_all(repo_root=repo_root, db_path=db_path, force=args.force, quiet=args.quiet)
    if args.update_readme:
        readme_p = generate_readme(repo_root=repo_root)
        if not args.quiet:
            print(f"[README updated] Regenerated {readme_p}")


if __name__ == "__main__":
    main()
