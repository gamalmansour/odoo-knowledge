"""
Test Suite for CLI Query Interface & Launcher Script (tools/kb_query.py and ./kb).
Tests CLI argument parsing, flags, output formats, exit codes, and shell launcher execution.
"""

import json
import os
import stat
import subprocess
import sys
import unittest
from pathlib import Path

# Ensure repo root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

KB_SCRIPT = REPO_ROOT / "kb"
CLI_SCRIPT = REPO_ROOT / "tools" / "kb_query.py"


@unittest.skipUnless(CLI_SCRIPT.exists(), "tools/kb_query.py is not yet implemented (Milestone 2)")
class TestCLIInterfaceFeatures(unittest.TestCase):
    """Tier 1: Feature Coverage for tools/kb_query.py CLI."""

    def run_cli(self, args, cwd=None):
        cmd = [sys.executable, str(CLI_SCRIPT)] + args
        return subprocess.run(
            cmd,
            cwd=cwd or str(REPO_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

    def test_cli_help_flag(self):
        """Tier 1: --help and -h exit with code 0."""
        for flag in ("--help", "-h"):
            res = self.run_cli([flag])
            self.assertEqual(res.returncode, 0, f"Expected 0 for {flag}")
            self.assertIn("usage:", res.stdout.lower())

    def test_cli_info_flag(self):
        """Tier 1: --info and -i print database statistics and exit with 0."""
        for flag in ("--info", "-i"):
            res = self.run_cli([flag])
            self.assertEqual(res.returncode, 0, f"Expected 0 for {flag}")
            out = res.stdout.lower()
            self.assertTrue("cache" in out or "documents" in out or "total" in out or "version" in out)

    def test_cli_basic_search(self):
        """Tier 1: Basic search query returns results."""
        res = self.run_cli(["locking"])
        self.assertEqual(res.returncode, 0)
        self.assertGreater(len(res.stdout.strip()), 0)

    def test_cli_unquoted_positional_arguments(self):
        """Tier 1: Multiple unquoted tokens joined as search query."""
        res = self.run_cli(["ir.access.csv", "-v", "20", "--format", "json"])
        self.assertEqual(res.returncode, 0)
        data = json.loads(res.stdout)
        self.assertIn("results", data)

    def test_cli_format_json(self):
        """Tier 1: --format json returns valid JSON string."""
        res = self.run_cli(["model", "--format", "json", "-n", "2"])
        self.assertEqual(res.returncode, 0)
        data = json.loads(res.stdout)
        self.assertIn("results", data)
        self.assertLessEqual(len(data["results"]), 2)

    def test_cli_format_markdown(self):
        """Tier 1: --format markdown returns markdown headings."""
        res = self.run_cli(["model", "--format", "markdown", "-n", "2"])
        self.assertEqual(res.returncode, 0)
        self.assertIn("###", res.stdout)

    def test_cli_format_compact(self):
        """Tier 1: --format compact returns concise lines."""
        res = self.run_cli(["model", "--format", "compact", "-n", "3"])
        self.assertEqual(res.returncode, 0)
        lines = [line for line in res.stdout.strip().splitlines() if line.strip()]
        self.assertLessEqual(len(lines), 6)

    def test_cli_category_filter(self):
        """Tier 1: --category or -c filters by category."""
        res = self.run_cli(["model", "-c", "orm", "--format", "json", "-n", "5"])
        self.assertEqual(res.returncode, 0)
        data = json.loads(res.stdout)
        for r in data["results"]:
            self.assertEqual(r.get("category"), "orm")

    def test_cli_limit_flag(self):
        """Tier 1: --limit or -n bounds results."""
        res = self.run_cli(["model", "-n", "1", "--format", "json"])
        self.assertEqual(res.returncode, 0)
        data = json.loads(res.stdout)
        self.assertLessEqual(len(data["results"]), 1)

    def test_cli_reindex_flag(self):
        """Tier 1: --reindex or -r forces cache rebuild."""
        res = self.run_cli(["--reindex", "--info"])
        self.assertEqual(res.returncode, 0)


@unittest.skipUnless(CLI_SCRIPT.exists(), "tools/kb_query.py is not yet implemented (Milestone 2)")
class TestCLIBoundaryCases(unittest.TestCase):
    """Tier 2: Boundary and Error Handling for CLI."""

    def run_cli(self, args):
        cmd = [sys.executable, str(CLI_SCRIPT)] + args
        return subprocess.run(
            cmd,
            cwd=str(REPO_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

    def test_cli_unknown_flag_exits_nonzero(self):
        """Tier 2: Unknown flag returns non-zero exit code."""
        res = self.run_cli(["--unknown-nonexistent-flag-xyz"])
        self.assertNotEqual(res.returncode, 0)

    def test_cli_empty_query_handles_gracefully(self):
        """Tier 2: Empty query string doesn't crash."""
        res = self.run_cli([""])
        self.assertEqual(res.returncode, 0)

    def test_cli_special_characters_query(self):
        """Tier 2: Complex dotted code string directly on CLI."""
        res = self.run_cli(["models.Constraint", "-v", "20", "--format", "json"])
        self.assertEqual(res.returncode, 0)
        data = json.loads(res.stdout)
        self.assertIn("results", data)


class TestKBLauncherScript(unittest.TestCase):
    """Tier 1 & 4: Executable Launcher Script (./kb)."""

    def test_kb_launcher_exists_and_executable(self):
        """Tier 1: Verify ./kb exists and has execute permissions."""
        if not KB_SCRIPT.exists():
            self.skipTest("./kb launcher script not yet created (Milestone 2)")
        self.assertTrue(KB_SCRIPT.is_file(), f"{KB_SCRIPT} is not a file")
        mode = os.stat(KB_SCRIPT).st_mode
        self.assertTrue(
            bool(mode & stat.S_IXUSR),
            f"{KB_SCRIPT} must be executable (chmod +x)",
        )
        # Check shebang
        content = KB_SCRIPT.read_text(encoding="utf-8")
        self.assertTrue(
            content.startswith("#!/"),
            "./kb must have a valid shell shebang (#!/bin/bash or #!/usr/bin/env bash)",
        )

    def test_kb_launcher_execution_from_repo_root(self):
        """Tier 4: Run ./kb from repo root."""
        if not KB_SCRIPT.exists():
            self.skipTest("./kb launcher script not yet created (Milestone 2)")
        res = subprocess.run(
            [str(KB_SCRIPT), "--help"],
            cwd=str(REPO_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.assertEqual(res.returncode, 0)
        self.assertIn("usage:", res.stdout.lower())

    def test_kb_launcher_execution_from_parent_workspace(self):
        """Tier 4: Run ./odoo-knowledge/kb from workspace root."""
        if not KB_SCRIPT.exists():
            self.skipTest("./kb launcher script not yet created (Milestone 2)")
        workspace_root = REPO_ROOT.parent
        res = subprocess.run(
            [str(KB_SCRIPT), "--help"],
            cwd=str(workspace_root),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.assertEqual(res.returncode, 0)
        self.assertIn("usage:", res.stdout.lower())


if __name__ == "__main__":
    unittest.main()
