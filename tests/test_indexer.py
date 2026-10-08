"""
Test Suite for Core Indexer Engine (tools/kb_indexer.py).
Covers Tiers 1-4: Parser archetypes, edge cases, schema integrity, mtime caching, and live cold benchmark.
"""

import os
import sys
import time
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

# Ensure odoo-knowledge repo root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    from tools import kb_indexer
except ImportError:
    kb_indexer = None


def _get_val(rec, key):
    """Helper to access parsed record either as dict or object."""
    if isinstance(rec, dict):
        return rec.get(key)
    return getattr(rec, key, None)


@unittest.skipIf(kb_indexer is None, "tools.kb_indexer is not yet implemented (Milestone 1)")
class TestMarkdownParserFeatures(unittest.TestCase):
    """Tier 1: Feature Coverage for Markdown Document Parser."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="kb_test_parser_")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_parse_markdown_table_metadata(self):
        """Tier 1: Standard markdown pipe table metadata extraction."""
        doc = (
            "# Fixing Odoo Model Lock Timeout\n\n"
            "| Field         | Value                                      |\n"
            "|---------------|--------------------------------------------|\n"
            "| Category      | orm                                        |\n"
            "| Odoo Versions | 16, 17, 18, 19                             |\n"
            "| Severity      | 🔴 Critical                                 |\n"
            "| Last Verified | 2026-08-15                                 |\n"
            "| Author        | ENG/Gamal Mansour                          |\n\n"
            "**Tags:** `postgres`, `locking`, `concurrency`\n\n"
            "## Problem\n"
            "Concurrent workers acquire table locks and freeze the database.\n\n"
            "## Solution ✅\n"
            "Use SELECT FOR UPDATE NOWAIT or advisory locks.\n\n"
            "## ⚠️ Pitfalls\n"
            "- Never hold locks across external HTTP requests.\n"
        )
        file_path = Path(self.test_dir) / "lock_timeout.md"
        file_path.write_text(doc, encoding="utf-8")

        rec = kb_indexer.parse_markdown_file(file_path)
        self.assertEqual(_get_val(rec, "title"), "Fixing Odoo Model Lock Timeout")
        self.assertEqual(_get_val(rec, "category"), "orm")
        self.assertEqual(_get_val(rec, "versions"), "16, 17, 18, 19")
        self.assertIn("Critical", _get_val(rec, "severity"))
        self.assertEqual(_get_val(rec, "author"), "ENG/Gamal Mansour")
        self.assertEqual(_get_val(rec, "last_verified"), "2026-08-15")
        self.assertIn("locking", _get_val(rec, "tags"))
        self.assertIn("freeze the database", _get_val(rec, "problem"))
        self.assertIn("advisory locks", _get_val(rec, "solution"))
        self.assertIn("Never hold locks", _get_val(rec, "pitfalls"))

    def test_parse_yaml_frontmatter_metadata(self):
        """Tier 1: YAML frontmatter metadata extraction."""
        doc = (
            "---\n"
            "title: 'Portal JS TypeError: Cannot set properties of null'\n"
            "category: 'frontend'\n"
            "version: '16.0+'\n"
            "severity: '🟡 Medium'\n"
            "last_verified: '2026-07-06'\n"
            "author: 'ENG/Gamal Mansour'\n"
            "tags: [frontend, javascript, owl]\n"
            "---\n\n"
            "# Portal JS TypeError: Cannot set properties of null\n\n"
            "## Problem\n"
            "DOM element not found when mounting portal widget.\n\n"
            "## Solution ✅\n"
            "Check if widget container exists before mounting.\n"
        )
        file_path = Path(self.test_dir) / "portal_error.md"
        file_path.write_text(doc, encoding="utf-8")

        rec = kb_indexer.parse_markdown_file(file_path)
        self.assertEqual(_get_val(rec, "title"), "Portal JS TypeError: Cannot set properties of null")
        self.assertEqual(_get_val(rec, "category"), "frontend")
        self.assertEqual(_get_val(rec, "versions"), "16.0+")
        self.assertIn("DOM element not found", _get_val(rec, "problem"))
        self.assertIn("widget container exists", _get_val(rec, "solution"))

    def test_parse_inline_bold_kv_metadata(self):
        """Tier 1: Top key-value bold list metadata extraction."""
        doc = (
            "# Hierarchical BOQ Calculation Performance\n\n"
            "**Category:** backend\n"
            "**Odoo Versions:** 17.0, 18.0, 19.0+\n"
            "**Severity:** 🔴 Critical\n"
            "**Last Verified:** 2026-07-01\n"
            "**Tags:** `compute`, `progress`, `boq`\n\n"
            "## Problem\n"
            "O(N^2) recursive parent computes cause 10s delay on 500 lines.\n\n"
            "## Solution ✅\n"
            "Use pre-cached dict accumulator pattern.\n"
        )
        file_path = Path(self.test_dir) / "boq.md"
        file_path.write_text(doc, encoding="utf-8")

        rec = kb_indexer.parse_markdown_file(file_path)
        self.assertEqual(_get_val(rec, "title"), "Hierarchical BOQ Calculation Performance")
        self.assertEqual(_get_val(rec, "category"), "backend")
        self.assertIn("19.0+", _get_val(rec, "versions"))
        self.assertIn("compute", _get_val(rec, "tags"))
        self.assertIn("recursive parent computes", _get_val(rec, "problem"))
        self.assertIn("dict accumulator", _get_val(rec, "solution"))

    def test_parse_numbered_cookbook_sections(self):
        """Tier 1: Architectural cookbook with numbered headings (e.g. Odoo 20 migration)."""
        doc = (
            "# Odoo 19 to Odoo 20 Migration Cookbook: Code Replacements\n\n"
            "| Field | Value |\n"
            "|---|---|\n"
            "| Category | upgrade |\n"
            "| Odoo Versions | 19, 20 |\n"
            "| Severity | 🔴 Critical |\n\n"
            "**Tags:** `odoo20`, `upgrade`, `ir.access.csv`, `constraints`\n\n"
            "## Overview\n"
            "Essential API shifts from Odoo 19 to Odoo 20.\n\n"
            "## 1. Security & Access Rules Revolution\n"
            "ir.model.access.csv and ir.rule XML are removed in Odoo 20. Use unified security/ir.access.csv.\n\n"
            "## 2. ORM & Python API Replacements\n"
            "Replace _sql_constraints with models.Constraint class attributes.\n\n"
            "## ⚠️ Checklist for 19 → 20 Migration\n"
            "- Update all manifests\n"
            "- Migrate models.Constraint\n"
        )
        file_path = Path(self.test_dir) / "cookbook.md"
        file_path.write_text(doc, encoding="utf-8")

        rec = kb_indexer.parse_markdown_file(file_path)
        self.assertEqual(_get_val(rec, "title"), "Odoo 19 to Odoo 20 Migration Cookbook: Code Replacements")
        self.assertEqual(_get_val(rec, "category"), "upgrade")
        self.assertEqual(_get_val(rec, "versions"), "19, 20")
        raw_content = _get_val(rec, "raw_content") or ""
        solution = _get_val(rec, "solution") or ""
        self.assertTrue(
            "ir.access.csv" in raw_content or "ir.access.csv" in solution,
            "Cookbook content must be indexed in raw_content or solution",
        )
        self.assertTrue(
            "models.Constraint" in raw_content or "models.Constraint" in solution,
            "models.Constraint must be present in cookbook content",
        )

    def test_parse_dedicated_metadata_section(self):
        """Tier 1: Dedicated ## Metadata section extraction."""
        doc = (
            "# Advanced Data Import\n\n"
            "## Metadata\n"
            "- **Category:** data_migration\n"
            "- **Severity:** 🟡 Medium\n"
            "- **Odoo Versions:** 18, 19, 20\n"
            "- **Tags:** `pandas`, `etl`, `excel`\n"
            "- **Author:** ENG/Gamal Mansour\n\n"
            "## Problem\n"
            "Excel rows timeout on standard create().\n\n"
            "## Solution ✅\n"
            "Batch records in chunks of 1000.\n"
        )
        file_path = Path(self.test_dir) / "import.md"
        file_path.write_text(doc, encoding="utf-8")

        rec = kb_indexer.parse_markdown_file(file_path)
        self.assertEqual(_get_val(rec, "category"), "data_migration")
        self.assertEqual(_get_val(rec, "versions"), "18, 19, 20")
        self.assertIn("pandas", _get_val(rec, "tags"))


@unittest.skipIf(kb_indexer is None, "tools.kb_indexer is not yet implemented (Milestone 1)")
class TestMarkdownParserEdgeCases(unittest.TestCase):
    """Tier 2: Boundary and Corner Cases for Parser."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="kb_test_parser_edge_")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_parse_code_blocks_with_hash_comments(self):
        """Tier 2: Code blocks with '#' comments must NOT break sections."""
        doc = (
            "# Python Method Override\n\n"
            "| Field | Value |\n"
            "|---|---|\n"
            "| Category | orm |\n"
            "| Odoo Versions | All |\n\n"
            "## Problem\n"
            "Overriding write without super() causes missing updates.\n\n"
            "## Solution ✅\n"
            "Always call super:\n"
            "```python\n"
            "# Problem: Missing super write\n"
            "# Solution: Call super like below\n"
            "def write(self, vals):\n"
            "    # ## ⚠️ Pitfall: forgetting super\n"
            "    res = super().write(vals)\n"
            "    return res\n"
            "```\n\n"
            "## ⚠️ Pitfalls\n"
            "- Forgetting to return res\n"
        )
        file_path = Path(self.test_dir) / "code_comments.md"
        file_path.write_text(doc, encoding="utf-8")

        rec = kb_indexer.parse_markdown_file(file_path)
        self.assertIn("Overriding write without super()", _get_val(rec, "problem"))
        self.assertIn("Always call super", _get_val(rec, "solution"))
        self.assertIn("def write(self, vals):", _get_val(rec, "solution"))
        self.assertIn("Forgetting to return res", _get_val(rec, "pitfalls"))

    def test_parse_subsections_under_solution(self):
        """Tier 2: H3 subsections under ## Solution must remain in solution."""
        doc = (
            "# Complex Multi-Step Fix\n\n"
            "| Field | Value |\n"
            "|---|---|\n"
            "| Category | security |\n"
            "| Odoo Versions | 19, 20 |\n\n"
            "## Problem\n"
            "Portal users lack permissions.\n\n"
            "## Solution ✅\n"
            "### 1. Link Portal User to Employee\n"
            "Execute SQL mapping between user and employee.\n\n"
            "### 2. Configure ReBAC Rule\n"
            "Create record rule referencing user_id.\n\n"
            "## ⚠️ Pitfalls\n"
            "- Circular reference risk\n"
        )
        file_path = Path(self.test_dir) / "subsections.md"
        file_path.write_text(doc, encoding="utf-8")

        rec = kb_indexer.parse_markdown_file(file_path)
        sol = _get_val(rec, "solution")
        self.assertIn("Link Portal User to Employee", sol)
        self.assertIn("Configure ReBAC Rule", sol)
        self.assertIn("Circular reference risk", _get_val(rec, "pitfalls"))

    def test_parse_emoji_prefixed_headings(self):
        """Tier 2: Headings with varied emoji placements."""
        doc = (
            "# 🚨 Parse Error on Custom Field\n\n"
            "| Field | Value |\n"
            "|---|---|\n"
            "| Category | views |\n"
            "| Odoo Versions | All |\n\n"
            "# 📝 Problem\n"
            "Field not found in model.\n\n"
            "# ✅ Solution\n"
            "Add model dependency in manifest.\n\n"
            "# ⚠️ Pitfalls\n"
            "- Forgetting to restart server.\n"
        )
        file_path = Path(self.test_dir) / "emojis.md"
        file_path.write_text(doc, encoding="utf-8")

        rec = kb_indexer.parse_markdown_file(file_path)
        self.assertIn("Field not found in model", _get_val(rec, "problem"))
        self.assertIn("Add model dependency in manifest", _get_val(rec, "solution"))
        self.assertIn("Forgetting to restart server", _get_val(rec, "pitfalls"))

    def test_parse_empty_and_whitespace_only_files(self):
        """Tier 2: Empty or whitespace markdown files must not crash."""
        p_empty = Path(self.test_dir) / "empty.md"
        p_empty.write_text("", encoding="utf-8")
        rec1 = kb_indexer.parse_markdown_file(p_empty)
        self.assertIsNotNone(rec1)

        p_white = Path(self.test_dir) / "white.md"
        p_white.write_text("   \n\n   \t  \n", encoding="utf-8")
        rec2 = kb_indexer.parse_markdown_file(p_white)
        self.assertIsNotNone(rec2)

    def test_parse_missing_metadata_defaults(self):
        """Tier 2: Missing metadata fields fall back cleanly to folder/filename."""
        subdir = Path(self.test_dir) / "security"
        subdir.mkdir()
        file_path = subdir / "custom-auth-guide.md"
        file_path.write_text("# Custom Auth Guide\n\nSimple content.", encoding="utf-8")

        rec = kb_indexer.parse_markdown_file(file_path)
        self.assertEqual(_get_val(rec, "title"), "Custom Auth Guide")
        self.assertEqual(_get_val(rec, "category"), "security")
        # Default version should be 'All' when unconstrained
        self.assertTrue(
            _get_val(rec, "versions") in ("All", "") or _get_val(rec, "versions") is not None
        )

    def test_category_normalization(self):
        """Tier 2: Plural directory 'upgrades' and compound categories normalized."""
        doc = (
            "# Stock Valuation Migration\n\n"
            "| Field | Value |\n"
            "|---|---|\n"
            "| Category | upgrades |\n"
            "| Odoo Versions | 19 |\n\n"
            "## Problem\n"
            "Valuation layers missing.\n"
        )
        file_path = Path(self.test_dir) / "valuation.md"
        file_path.write_text(doc, encoding="utf-8")

        rec = kb_indexer.parse_markdown_file(file_path)
        cat = _get_val(rec, "category").lower()
        self.assertTrue(cat in ("upgrade", "upgrades"), f"Expected upgrade, got {cat}")

    def test_unclosed_code_fence_recovers(self):
        """Tier 2: Markdown with unclosed code fence should not raise uncaught exceptions."""
        doc = (
            "# Unclosed Fence\n\n"
            "| Category | orm |\n\n"
            "## Solution\n"
            "```python\n"
            "def foo():\n"
            "    pass\n"
            "# fence never closed\n"
        )
        file_path = Path(self.test_dir) / "unclosed.md"
        file_path.write_text(doc, encoding="utf-8")
        rec = kb_indexer.parse_markdown_file(file_path)
        self.assertIsNotNone(rec)
        self.assertEqual(_get_val(rec, "title"), "Unclosed Fence")

    def test_crlf_line_endings(self):
        """Tier 2: Files with Windows CRLF (\\r\\n) line endings parse correctly."""
        doc = (
            "# Windows CRLF Test\r\n\r\n"
            "| Field | Value |\r\n"
            "|---|---|\r\n"
            "| Category | backend |\r\n"
            "| Odoo Versions | 20 |\r\n\r\n"
            "## Problem\r\n"
            "CRLF issues.\r\n\r\n"
            "## Solution ✅\r\n"
            "Normalize newlines.\r\n"
        )
        file_path = Path(self.test_dir) / "crlf.md"
        file_path.write_bytes(doc.encode("utf-8"))
        rec = kb_indexer.parse_markdown_file(file_path)
        self.assertEqual(_get_val(rec, "title"), "Windows CRLF Test")
        self.assertEqual(_get_val(rec, "category"), "backend")
        self.assertEqual(_get_val(rec, "versions"), "20")
        self.assertIn("Normalize newlines", _get_val(rec, "solution"))


@unittest.skipIf(kb_indexer is None, "tools.kb_indexer is not yet implemented (Milestone 1)")
class TestSQLiteStorageAndSchemaFeatures(unittest.TestCase):
    """Tier 1 & 2: SQLite FTS5 Storage Engine & Schema Integrity."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="kb_test_db_")
        self.db_path = Path(self.test_dir) / "test_kb.db"

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_init_db_schema_tables_and_pragmas(self):
        """Tier 1: Check tables, indexes, triggers, and WAL mode."""
        conn = kb_indexer.init_db(self.db_path)
        cur = conn.cursor()

        # Check WAL mode
        cur.execute("PRAGMA journal_mode")
        mode = cur.fetchone()[0]
        self.assertEqual(mode.lower(), "wal")

        # Check table existence
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cur.fetchall()}
        self.assertIn("kb_metadata", tables)
        self.assertIn("kb_entries", tables)
        self.assertIn("kb_fts", tables)

        # Check triggers
        cur.execute("SELECT name FROM sqlite_master WHERE type='trigger'")
        triggers = {row[0] for row in cur.fetchall()}
        self.assertTrue(any("ai" in t for t in triggers), "Missing AFTER INSERT trigger")
        self.assertTrue(any("ad" in t for t in triggers), "Missing AFTER DELETE trigger")
        self.assertTrue(any("au" in t for t in triggers), "Missing AFTER UPDATE trigger")

        conn.close()

    def test_fts5_triggers_synchronization(self):
        """Tier 1: Insertion, update, deletion in kb_entries syncs to kb_fts."""
        conn = kb_indexer.init_db(self.db_path)
        cur = conn.cursor()

        # Insert entry
        cur.execute("""
        INSERT INTO kb_entries (
            file_path, mtime, title, category, versions, severity, tags,
            author, last_verified, problem, solution, pitfalls, raw_content
        ) VALUES (
            'orm/test_doc.md', 1000.0, 'ORM Compute Field Test', 'orm', '19, 20', 'Low',
            'compute,test', 'Tester', '2026-10-08', 'Slow compute loop',
            'Vectorized compute with mapped', 'Pitfall avoid N+1', 'Full text content here'
        )
        """)
        conn.commit()

        # Check FTS index hit
        cur.execute("SELECT rowid FROM kb_fts WHERE kb_fts MATCH 'Vectorized'")
        hits = cur.fetchall()
        self.assertEqual(len(hits), 1)

        # Update entry
        cur.execute("""
        UPDATE kb_entries
        SET solution = 'Optimized mapped operation and cached'
        WHERE file_path = 'orm/test_doc.md'
        """)
        conn.commit()

        # Old term should no longer match
        cur.execute("SELECT rowid FROM kb_fts WHERE kb_fts MATCH 'Vectorized'")
        self.assertEqual(len(cur.fetchall()), 0)
        # New term should match
        cur.execute("SELECT rowid FROM kb_fts WHERE kb_fts MATCH 'Optimized'")
        self.assertEqual(len(cur.fetchall()), 1)

        # Delete entry
        cur.execute("DELETE FROM kb_entries WHERE file_path = 'orm/test_doc.md'")
        conn.commit()

        # FTS should now be empty
        cur.execute("SELECT rowid FROM kb_fts WHERE kb_fts MATCH 'Optimized'")
        self.assertEqual(len(cur.fetchall()), 0)

        conn.close()


@unittest.skipIf(kb_indexer is None, "tools.kb_indexer is not yet implemented (Milestone 1)")
class TestIncrementalIndexingCache(unittest.TestCase):
    """Tier 1 & 3: Fast Incremental Cache Invalidation & Invalidation Correctness."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="kb_test_inc_")
        self.repo_dir = Path(self.test_dir) / "repo"
        self.repo_dir.mkdir()
        self.db_path = Path(self.test_dir) / ".kb_cache.db"

        # Create dummy category folders
        (self.repo_dir / "orm").mkdir()
        (self.repo_dir / "views").mkdir()

        # Create 3 test files
        self.f1 = self.repo_dir / "orm" / "f1.md"
        self.f1.write_text("# Doc 1\n\n| Category | orm |\n| Odoo Versions | 20 |\n\n## Solution\nSol 1", encoding="utf-8")
        self.f2 = self.repo_dir / "orm" / "f2.md"
        self.f2.write_text("# Doc 2\n\n| Category | orm |\n| Odoo Versions | 20 |\n\n## Solution\nSol 2", encoding="utf-8")
        self.f3 = self.repo_dir / "views" / "f3.md"
        self.f3.write_text("# Doc 3\n\n| Category | views |\n| Odoo Versions | 20 |\n\n## Solution\nSol 3", encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_incremental_indexing_mtime_cache(self):
        """Tier 1 & 3: Second pass with no changes reindexes 0 files."""
        # Initial cold index
        stats1 = kb_indexer.index_all(self.repo_dir, db_path=self.db_path)
        self.assertEqual(stats1.get("indexed"), 3)

        # Second pass (steady state)
        stats2 = kb_indexer.index_all(self.repo_dir, db_path=self.db_path)
        self.assertEqual(stats2.get("indexed"), 0)
        self.assertEqual(stats2.get("deleted", 0), 0)

        # Update 1 file
        time.sleep(0.05)  # ensure filesystem mtime advances
        self.f1.write_text("# Doc 1 Modified\n\n| Category | orm |\n| Odoo Versions | 20 |\n\n## Solution\nUpdated Sol", encoding="utf-8")

        stats3 = kb_indexer.index_all(self.repo_dir, db_path=self.db_path)
        self.assertEqual(stats3.get("indexed"), 1)
        self.assertEqual(stats3.get("deleted", 0), 0)

        # Delete 1 file
        self.f2.unlink()
        stats4 = kb_indexer.index_all(self.repo_dir, db_path=self.db_path)
        self.assertEqual(stats4.get("deleted", 0), 1)

        # Verify DB has exactly 2 records remaining
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("SELECT count(*) FROM kb_entries")
        count = cur.fetchone()[0]
        conn.close()
        self.assertEqual(count, 2)

    def test_force_reindex_rebuilds_all(self):
        """Tier 3: force=True must reindex all files regardless of mtime."""
        kb_indexer.index_all(self.repo_dir, db_path=self.db_path)
        stats_force = kb_indexer.index_all(self.repo_dir, db_path=self.db_path, force=True)
        self.assertEqual(stats_force.get("indexed"), 3)

    def test_skips_binary_and_meta_files(self):
        """Tier 2 & 3: Binary files (.pdf) and meta files (README, TEMPLATE, CONTRIBUTING) are ignored."""
        # Add a binary dummy file and meta docs to repo
        (self.repo_dir / "cookbook.pdf").write_bytes(b"%PDF-1.4 dummy")
        (self.repo_dir / "README.md").write_text("# Knowledge Base Index\n\nNot an entry.", encoding="utf-8")
        (self.repo_dir / "TEMPLATE.md").write_text("# Template\n\nTemplate content.", encoding="utf-8")
        (self.repo_dir / "CONTRIBUTING.md").write_text("# Contributing\n\nGuidelines.", encoding="utf-8")

        stats = kb_indexer.index_all(self.repo_dir, db_path=self.db_path, force=True)
        # Still only the 3 real knowledge entries should be indexed
        self.assertEqual(stats.get("indexed"), 3)
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("SELECT file_path FROM kb_entries")
        paths = [r[0] for r in cur.fetchall()]
        conn.close()
        self.assertEqual(len(paths), 3)
        for p in paths:
            self.assertFalse(p.endswith(".pdf"))
            self.assertNotIn("README.md", p)
            self.assertNotIn("TEMPLATE.md", p)
            self.assertNotIn("CONTRIBUTING.md", p)


@unittest.skipIf(kb_indexer is None, "tools.kb_indexer is not yet implemented (Milestone 1)")
class TestRealWorldColdReindexBenchmark(unittest.TestCase):
    """Tier 4: Acceptance Scenario - Full Cold Reindex Benchmark (< 1.0s) on Live Corpus."""

    def test_cold_reindex_live_corpus_under_one_second(self):
        """Tier 4: Re-index all 440+ markdown files in odoo-knowledge in < 1.0s."""
        live_repo = REPO_ROOT
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            tmp_db = Path(tmp.name)

        try:
            t0 = time.perf_counter()
            stats = kb_indexer.index_all(live_repo, db_path=tmp_db, force=True)
            elapsed = time.perf_counter() - t0

            # Acceptance Criterion: Full reindex completes in < 1.0s
            self.assertLess(
                elapsed,
                1.0,
                f"Cold re-indexing took {elapsed:.3f}s, exceeding 1.0s threshold",
            )
            total = stats.get("total_files") or stats.get("indexed")
            self.assertGreaterEqual(
                total,
                440,
                f"Expected at least 440 markdown files indexed, got {total}",
            )

            # Check database row count
            conn = sqlite3.connect(tmp_db)
            cur = conn.cursor()
            cur.execute("SELECT count(*) FROM kb_entries")
            row_count = cur.fetchone()[0]
            conn.close()

            self.assertGreaterEqual(
                row_count,
                440,
                f"Expected at least 440 records in kb_entries, got {row_count}",
            )
        finally:
            if tmp_db.exists():
                tmp_db.unlink()
            for suffix in ("-wal", "-shm"):
                p = Path(str(tmp_db) + suffix)
                if p.exists():
                    p.unlink()


if __name__ == "__main__":
    unittest.main()
