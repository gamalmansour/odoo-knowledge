"""
Test Suite for FTS5 Query Engine, BM25 Ranking & Snippet Formatter.
Tests query token sanitizer, FTS5 execution, Top-1 rank guarantee for Odoo 20 cookbook,
and output formatting across text, markdown, compact, and json.
"""

import json
import os
import sys
import sqlite3
import tempfile
import unittest
from pathlib import Path

# Ensure repo root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    from tools import kb_query
    sanitize_fts5_query = getattr(kb_query, "sanitize_fts5_query", None)
    search = getattr(kb_query, "search", None)
    format_results = getattr(kb_query, "format_results", None)
except ImportError:
    kb_query = None
    sanitize_fts5_query = None
    search = None
    format_results = None

try:
    from tools import kb_indexer
except ImportError:
    kb_indexer = None


@unittest.skipIf(sanitize_fts5_query is None, "tools.kb_query is not yet implemented (Milestone 2)")
class TestQuerySanitizerFeatures(unittest.TestCase):
    """Tier 1: Feature Coverage for FTS5 Query Token Sanitizer."""

    def test_sanitize_dotted_code_symbols(self):
        """Tier 1: Dotted identifiers must be quoted to prevent FTS5 syntax errors."""
        q1 = sanitize_fts5_query("ir.access.csv")
        self.assertIn('"ir.access.csv"', q1)

        q2 = sanitize_fts5_query("models.Constraint")
        self.assertIn('"models.Constraint"', q2)

        q3 = sanitize_fts5_query("res.partner.category")
        self.assertIn('"res.partner.category"', q3)

    def test_sanitize_plain_words_and_prefixes(self):
        """Tier 1: Word tokens receive prefix wildcard or clean token form."""
        q = sanitize_fts5_query("migration")
        self.assertTrue("migration" in q)

    def test_sanitize_preserves_boolean_operators(self):
        """Tier 1: AND, OR, NOT operators are preserved."""
        q = sanitize_fts5_query("locking AND postgres")
        self.assertIn("AND", q)

    def test_sanitize_preserves_explicit_phrases(self):
        """Tier 1: Double-quoted phrases preserved."""
        q = sanitize_fts5_query('"breaking changes"')
        self.assertIn('"breaking changes"', q)

    def test_sanitize_empty_and_whitespace(self):
        """Tier 1: Empty queries produce safe FTS5 string."""
        self.assertIn(sanitize_fts5_query(""), ('""', ''))
        self.assertIn(sanitize_fts5_query("   "), ('""', ''))


@unittest.skipIf(sanitize_fts5_query is None, "tools.kb_query is not yet implemented (Milestone 2)")
class TestQuerySanitizerBoundaryCases(unittest.TestCase):
    """Tier 2: Boundary & Corner Cases for Sanitizer."""

    def test_sanitize_special_characters_no_syntax_error(self):
        """Tier 2: Punctuation characters must not produce FTS5 syntax errors."""
        test_inputs = [
            "field:id",
            "table_name.field_name",
            "_sql_constraints",
            "key/value",
            "code()",
            "list[0]",
            "tag*?",
            "price$",
            "email@domain",
            "c:\\path\\to\\file",
            "...",
            ":::",
            "---",
            "ir.access.csv\"",
            "\"models.Constraint",
            "' OR 1=1 --",
            '"; DROP TABLE kb_entries; --',
        ]
        # Create an in-memory FTS5 table to verify syntax safety
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE VIRTUAL TABLE t USING fts5(c);")
        cur = conn.cursor()

        for inp in test_inputs:
            with self.subTest(raw_input=inp):
                sanitized = sanitize_fts5_query(inp)
                self.assertIsInstance(sanitized, str)
                if sanitized.strip() and sanitized != '""':
                    try:
                        cur.execute("SELECT * FROM t WHERE t MATCH ?", (sanitized,))
                    except sqlite3.OperationalError as e:
                        self.fail(f"FTS5 syntax error on input '{inp}' -> sanitized '{sanitized}': {e}")
        conn.close()


@unittest.skipIf(search is None, "tools.kb_query is not yet implemented (Milestone 2)")
class TestSearchEngineFeatures(unittest.TestCase):
    """Tier 1 & 3: Search Execution, Filters, and Cross-Feature Interactions."""

    @classmethod
    def setUpClass(cls):
        # Create a temporary indexed test database
        cls.tmp_db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        cls.db_path = Path(cls.tmp_db_file.name)
        if kb_indexer:
            kb_indexer.index_all(REPO_ROOT, db_path=cls.db_path, force=False)

    @classmethod
    def tearDownClass(cls):
        if cls.db_path.exists():
            cls.db_path.unlink()
        for s in ("-wal", "-shm"):
            p = Path(str(cls.db_path) + s)
            if p.exists():
                p.unlink()

    def test_search_basic_execution(self):
        """Tier 1: Basic search returns results with standard keys."""
        results = search("locking", limit=5, db_path=self.db_path)
        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0)
        top = results[0]
        for key in ("title", "file_path", "category", "versions"):
            self.assertIn(key, top)

    def test_search_with_category_filter(self):
        """Tier 1: Category filter limits results to target category."""
        results = search("model", category="orm", limit=5, db_path=self.db_path)
        for r in results:
            self.assertEqual(r.get("category"), "orm")

    def test_search_with_limit_control(self):
        """Tier 1: Limit argument strictly bounds number of results."""
        r1 = search("model", limit=2, db_path=self.db_path)
        self.assertLessEqual(len(r1), 2)
        r2 = search("model", limit=7, db_path=self.db_path)
        self.assertLessEqual(len(r2), 7)

    def test_search_with_version_filter(self):
        """Tier 1 & 3: Version 20 excludes legacy entries."""
        results = search("constraint", target_version=20.0, limit=10, db_path=self.db_path)
        for r in results:
            v_str = r.get("versions", "")
            # Must not be legacy single version (16, 17, 18)
            self.assertNotIn("16.0 only", v_str)
            self.assertNotIn("17.0 only", v_str)

    def test_search_cross_feature_filters(self):
        """Tier 3: Version + Category + Limit interaction."""
        results = search(
            "migration",
            target_version=20.0,
            category="upgrade",
            limit=3,
            db_path=self.db_path,
        )
        self.assertLessEqual(len(results), 3)
        for r in results:
            self.assertEqual(r.get("category"), "upgrade")


@unittest.skipIf(search is None, "tools.kb_query is not yet implemented (Milestone 2)")
class TestTopOneRankAcceptanceScenario(unittest.TestCase):
    """Tier 4: Acceptance Scenario - Top 1 Rank Guarantee for Odoo 20 Breaking Changes."""

    @classmethod
    def setUpClass(cls):
        cls.tmp_db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        cls.db_path = Path(cls.tmp_db_file.name)
        if kb_indexer:
            kb_indexer.index_all(REPO_ROOT, db_path=cls.db_path, force=False)

    @classmethod
    def tearDownClass(cls):
        if cls.db_path.exists():
            cls.db_path.unlink()
        for s in ("-wal", "-shm"):
            p = Path(str(cls.db_path) + s)
            if p.exists():
                p.unlink()

    def test_top_one_rank_ir_access_csv(self):
        """
        Tier 4: Searching 'ir.access.csv' with --version 20 must return
        upgrade/odoo19-to-odoo20-migration-cookbook-code-replacements.md
        as the TOP 1 result.
        """
        results = search("ir.access.csv", target_version=20.0, limit=5, db_path=self.db_path)
        self.assertGreater(len(results), 0, "Query 'ir.access.csv' returned no results")
        top_hit = results[0]
        top_path = top_hit.get("file_path", "")
        self.assertIn(
            "odoo19-to-odoo20-migration-cookbook-code-replacements.md",
            top_path,
            f"Expected Odoo 20 migration cookbook at Rank 1 for 'ir.access.csv', got: {top_path}",
        )

    def test_top_one_rank_models_constraint(self):
        """
        Tier 4: Searching 'models.Constraint' with --version 20 must return
        upgrade/odoo19-to-odoo20-migration-cookbook-code-replacements.md
        as the TOP 1 result.
        """
        results = search("models.Constraint", target_version=20.0, limit=5, db_path=self.db_path)
        self.assertGreater(len(results), 0, "Query 'models.Constraint' returned no results")
        top_hit = results[0]
        top_path = top_hit.get("file_path", "")
        self.assertIn(
            "odoo19-to-odoo20-migration-cookbook-code-replacements.md",
            top_path,
            f"Expected Odoo 20 migration cookbook at Rank 1 for 'models.Constraint', got: {top_path}",
        )


@unittest.skipIf(format_results is None, "tools.kb_query is not yet implemented (Milestone 2)")
class TestSnippetFormatterFeatures(unittest.TestCase):
    """Tier 1 & 3: Snippet Formatter across text, markdown, compact, and json."""

    def setUp(self):
        self.sample_results = [
            {
                "rank": 1,
                "score": -14.25,
                "title": "Odoo 19 to Odoo 20 Migration Cookbook: Code Replacements",
                "file_path": "upgrade/odoo19-to-odoo20-migration-cookbook-code-replacements.md",
                "category": "upgrade",
                "severity": "🔴 Critical",
                "versions": "19, 20",
                "tags": "odoo20, upgrade, ir.access.csv, constraints",
                "last_verified": "2026-10-08",
                "problem": "ir.rule XML and ir.model.access.csv removed.",
                "solution": "Unify access rights in security/ir.access.csv.",
                "pitfalls": "[(1, '=', 1)] fails validation. Use empty domain string.",
            }
        ]

    def test_format_json_schema(self):
        """Tier 1: JSON format must produce valid JSON with expected schema."""
        output = format_results(self.sample_results, fmt="json")
        data = json.loads(output)
        self.assertIn("results", data)
        self.assertEqual(len(data["results"]), 1)
        r0 = data["results"][0]
        self.assertEqual(r0["title"], "Odoo 19 to Odoo 20 Migration Cookbook: Code Replacements")
        self.assertEqual(r0["category"], "upgrade")
        self.assertIn("ir.access.csv", r0.get("solution_snippet", r0.get("solution", "")))

    def test_format_markdown_code_blocks(self):
        """Tier 1: Markdown format includes headings, bullet points, and path."""
        output = format_results(self.sample_results, fmt="markdown")
        self.assertIn("###", output)
        self.assertIn("upgrade/odoo19-to-odoo20-migration-cookbook-code-replacements.md", output)
        self.assertIn("ir.access.csv", output)

    def test_format_text_readable(self):
        """Tier 1: Text format includes divider lines and key sections."""
        output = format_results(self.sample_results, fmt="text")
        self.assertIn("Odoo 19 to Odoo 20 Migration Cookbook", output)
        self.assertIn("upgrade", output)

    def test_format_compact_dense(self):
        """Tier 1: Compact format produces 1-2 lines per entry."""
        output = format_results(self.sample_results, fmt="compact")
        lines = [line for line in output.strip().splitlines() if line.strip()]
        self.assertLessEqual(len(lines), 3)


if __name__ == "__main__":
    unittest.main()
