#!/usr/bin/env python3
"""
Master Test Runner for odoo-knowledge Test Suite.
Discovers and executes all unit tests across Tiers 1-4.
Zero external dependencies: pure Python standard library.
"""

import os
import sys
import time
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TESTS_DIR = REPO_ROOT / "tests"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def main():
    print("=" * 72)
    print("  odoo-knowledge Automated Test Suite Runner")
    print(f"  Target Repository: {REPO_ROOT}")
    print(f"  Test Directory:    {TESTS_DIR}")
    print("=" * 72)

    loader = unittest.TestLoader()
    suite = loader.discover(start_dir=str(TESTS_DIR), pattern="test_*.py")

    t0 = time.perf_counter()
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    elapsed = time.perf_counter() - t0

    print("-" * 72)
    print(f"Tests run:       {result.testsRun}")
    print(f"Passed:          {result.testsRun - len(result.failures) - len(result.errors) - len(result.skipped)}")
    print(f"Skipped:         {len(result.skipped)}")
    print(f"Failures:        {len(result.failures)}")
    print(f"Errors:          {len(result.errors)}")
    print(f"Execution time:  {elapsed:.3f} seconds")
    print("-" * 72)

    if result.wasSuccessful():
        print("ALL ACTIVE TESTS PASSED! ✅")
        return 0
    else:
        print("TEST RUN ENCOUNTERED FAILURES / DEFECTS! ❌")
        return 1


if __name__ == "__main__":
    sys.exit(main())
