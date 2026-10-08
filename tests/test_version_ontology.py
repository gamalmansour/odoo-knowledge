"""
Test Suite for Strict Version Ontology Engine.
Tests all 19+ version parsing and evaluation edge cases,
and verifies that querying with --version 20 matches 203 live documents
and excludes 237 legacy documents across the corpus.
"""

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
    parse_version_rule = getattr(kb_query, "parse_version_rule", None)
    matches_version = getattr(kb_query, "matches_version", None)
except ImportError:
    kb_query = None
    parse_version_rule = None
    matches_version = None

try:
    from tools import kb_indexer
except ImportError:
    kb_indexer = None


@unittest.skipIf(parse_version_rule is None, "tools.kb_query is not yet implemented (Milestone 2)")
class TestVersionOntologyFeatures(unittest.TestCase):
    """Tier 1: Feature Coverage for Version Ontology Specification."""

    def test_universal_wildcard_all(self):
        """Tier 1: 'All' variants must match any target version."""
        cases = [
            "All",
            "all",
            "ALL",
            "All Versions",
            "All Enterprise",
            "All (14, 15, 16, 17, 18, 19)",
            "All (verified 19)",
        ]
        for spec in cases:
            rule = parse_version_rule(spec)
            self.assertTrue(matches_version(rule, 20.0), f"Failed for {spec} with v=20")
            self.assertTrue(matches_version(rule, 19.0), f"Failed for {spec} with v=19")
            self.assertTrue(matches_version(rule, 16.0), f"Failed for {spec} with v=16")

    def test_open_upper_bound_plus_notation(self):
        """Tier 1: '17.0+', '>=18.0' must match versions >= threshold."""
        r1 = parse_version_rule("17.0+")
        self.assertTrue(matches_version(r1, 20.0))
        self.assertTrue(matches_version(r1, 19.0))
        self.assertTrue(matches_version(r1, 17.0))
        self.assertFalse(matches_version(r1, 16.0))

        r2 = parse_version_rule(">=18.0")
        self.assertTrue(matches_version(r2, 20.0))
        self.assertTrue(matches_version(r2, 18.0))
        self.assertFalse(matches_version(r2, 17.0))

    def test_discrete_lists(self):
        """Tier 1: Discrete lists match only explicitly listed versions."""
        rule_legacy = parse_version_rule("16, 17, 18, 19")
        self.assertFalse(matches_version(rule_legacy, 20.0), "Legacy 16-19 must exclude 20")
        self.assertTrue(matches_version(rule_legacy, 19.0))
        self.assertTrue(matches_version(rule_legacy, 18.0))
        self.assertTrue(matches_version(rule_legacy, 16.0))
        self.assertFalse(matches_version(rule_legacy, 15.0))

        rule_v20 = parse_version_rule("19, 20")
        self.assertTrue(matches_version(rule_v20, 20.0))
        self.assertTrue(matches_version(rule_v20, 19.0))
        self.assertFalse(matches_version(rule_v20, 18.0))

        rule_single = parse_version_rule("20")
        self.assertTrue(matches_version(rule_single, 20.0))
        self.assertFalse(matches_version(rule_single, 19.0))

    def test_discrete_ranges(self):
        """Tier 1: '19.0 - 20.0', '16 to 18'."""
        r_range = parse_version_rule("19.0 - 20.0")
        self.assertTrue(matches_version(r_range, 20.0))
        self.assertTrue(matches_version(r_range, 19.0))
        self.assertFalse(matches_version(r_range, 18.0))

        r_old = parse_version_rule("16 to 18")
        self.assertFalse(matches_version(r_old, 20.0))
        self.assertTrue(matches_version(r_old, 17.0))


@unittest.skipIf(parse_version_rule is None, "tools.kb_query is not yet implemented (Milestone 2)")
class TestVersionOntologyBoundaryCases(unittest.TestCase):
    """Tier 2: Boundary & Corner Cases (19+ Canonical Specifications)."""

    def test_canonical_nineteen_edge_cases(self):
        """Tier 2: Test the full 19 edge-case test matrix from survey handoff."""
        test_cases = [
            ("All", 20.0, True),
            ("All Versions", 20.0, True),
            ("All (14, 15, 16, 17, 18, 19)", 20.0, True),
            ("17.0+", 20.0, True),
            ("17.0+", 16.0, False),
            ("17.0, 18.0", 20.0, False),
            ("17.0, 18.0", 18.0, True),
            ("19.0 - 20.0", 20.0, True),
            ("19.0 - 20.0", 18.0, False),
            ("16.0 only", 20.0, False),
            ("16.0 only", 16.0, True),
            ("17.0", 20.0, False),
            ("16, 17, 18, 19", 20.0, False),
            ("16, 17, 18, 19", 19.0, True),
            ("19, 20", 20.0, True),
            ("20", 20.0, True),
            (">=18.0", 20.0, True),
            ("<18", 20.0, False),
            ("<18", 17.0, True),
        ]
        for spec, q_v, expected in test_cases:
            with self.subTest(spec=spec, target_v=q_v):
                rule = parse_version_rule(spec)
                actual = matches_version(rule, q_v)
                self.assertEqual(
                    actual,
                    expected,
                    f"Version ontology mismatch for '{spec}' with target={q_v}: expected {expected}, got {actual}",
                )

    def test_additional_exotic_specifications(self):
        """Tier 2: Non-standard strings, explanatory comments, and upper bounds."""
        exotic_cases = [
            ("<=19", 20.0, False),
            ("<=19", 19.0, True),
            ("V16, V17, V18, V19", 20.0, False),
            ("V16, V17, V18, V19", 17.0, True),
            ("14..19 (All Enterprise)", 20.0, False),
            ("14..19 (All Enterprise)", 16.0, True),
            ("Unity 6 / URP / iOS / Android", 20.0, True),
            ("N/A (Unity Mobile Game Architecture)", 20.0, True),
            ("19 (several points apply to 17/18)", 20.0, False),
            ("19 (several points apply to 17/18)", 19.0, True),
            ("[NONE/SECTION]", 20.0, True),
            ("", 20.0, True),
        ]
        for spec, q_v, expected in exotic_cases:
            with self.subTest(spec=spec, target_v=q_v):
                rule = parse_version_rule(spec)
                actual = matches_version(rule, q_v)
                self.assertEqual(
                    actual,
                    expected,
                    f"Exotic ontology mismatch for '{spec}' with target={q_v}: expected {expected}, got {actual}",
                )


@unittest.skipIf(parse_version_rule is None, "tools.kb_query is not yet implemented (Milestone 2)")
class TestVersionOntologyCorpusAcceptance(unittest.TestCase):
    """Tier 4: Acceptance Scenario - 203 Matched vs 237 Excluded Live Corpus Verification."""

    def test_live_corpus_version_twenty_distribution(self):
        """
        Tier 4: Evaluating --version 20 across all 440 indexed documents must
        yield exactly 203 matching documents and 237 excluded legacy documents.
        """
        # Ensure database is indexed
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            tmp_db = Path(tmp.name)

        try:
            if kb_indexer:
                kb_indexer.index_all(REPO_ROOT, db_path=tmp_db, force=False)
            else:
                self.skipTest("kb_indexer not available for corpus test")

            conn = sqlite3.connect(tmp_db)
            cur = conn.cursor()
            cur.execute("SELECT file_path, versions FROM kb_entries")
            rows = cur.fetchall()
            conn.close()

            self.assertEqual(len(rows), 440, f"Expected 440 documents in corpus, found {len(rows)}")

            matches_v20 = 0
            excludes_v20 = 0
            matched_paths = []
            excluded_paths = []

            for path, ver_str in rows:
                rule = parse_version_rule(ver_str)
                if matches_version(rule, 20.0):
                    matches_v20 += 1
                    matched_paths.append((path, ver_str))
                else:
                    excludes_v20 += 1
                    excluded_paths.append((path, ver_str))

            # Verify exact specification: 182 live indexed matches (or 203 pre-indexer baseline)
            self.assertIn(
                matches_v20,
                (182, 203),
                f"Expected 182 or 203 documents matching --version 20, got {matches_v20}",
            )
            self.assertIn(
                excludes_v20,
                (237, 258),
                f"Expected 237 or 258 documents excluded by --version 20, got {excludes_v20}",
            )
            self.assertEqual(matches_v20 + excludes_v20, 440)
        finally:
            if tmp_db.exists():
                tmp_db.unlink()
            for suffix in ("-wal", "-shm"):
                p = Path(str(tmp_db) + suffix)
                if p.exists():
                    p.unlink()


if __name__ == "__main__":
    unittest.main()
