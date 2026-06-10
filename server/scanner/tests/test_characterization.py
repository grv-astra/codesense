"""Characterization lock for the DETECTOR pipeline (detector -> normalize -> derive_cwe).

This pins what the *detector* produces on a fixed, tiny fixture corpus so the
model/UX work in later roadmap weeks cannot silently change detection. It runs the
REAL engine (OpenGrep) + the bundled rules, so it is gated on SEMGREP_BIN +
SEMGREP_RULES_DIR being set (e.g. via server\\run_dev.ps1). Without them it skips,
which keeps a CI host that has no engine green.

NOTE (Windows / git-aware traversal): OpenGrep's directory walker enumerates **zero**
files for an arbitrary subdirectory that lives inside a git working tree, so scanning
``fixtures/characterization`` in place returns nothing. We therefore copy the fixture
into a temp directory (outside any repo) and scan that — which is also how the engine
behaves on an end-user's checked-out project.
"""
from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path

from django.test import SimpleTestCase

from scanner.rag.semgrep_detector import run_semgrep
from scanner.rag.finding_normalizer import normalize

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "characterization"
_HAVE_ENGINE = bool(os.getenv("SEMGREP_BIN")) and bool(os.getenv("SEMGREP_RULES_DIR"))

# Snapshot of current detector behavior on the fixture, captured 2026-06-10 with the
# bundled OpenGrep + staged semgrep-rules on Windows. title (= Semgrep rule slug) -> CWE.
# Locking the exact set is the point: a later change that adds/drops a finding or
# regresses CWE derivation must update this map *deliberately*, not silently.
_EXPECTED_TITLE_CWE = {
    "dockerfile-source-not-pinned": "CWE-710",
    "missing-user": "CWE-250",
    "tainted-sql-string": "CWE-915",
    "sqlalchemy-execute-raw-query": "CWE-89",
}


@unittest.skipUnless(_HAVE_ENGINE, "set SEMGREP_BIN + SEMGREP_RULES_DIR to run characterization")
class DetectorCharacterizationTests(SimpleTestCase):
    """Pins current detection behavior on a fixed fixture so the model/UX work
    in later weeks cannot silently change what the DETECTOR produces."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Copy the fixture out of the repo so the git-aware walker actually sees it.
        cls._tmp = Path(tempfile.mkdtemp(prefix="codesense_char_"))
        for p in FIXTURE_DIR.iterdir():
            if p.is_file():
                shutil.copy(p, cls._tmp / p.name)
        cls.findings = run_semgrep(str(cls._tmp))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls._tmp, ignore_errors=True)
        super().tearDownClass()

    def _titles(self) -> set[str]:
        return {normalize(f, "s", "u")[0]["title"] for f in self.findings}

    def test_detects_the_sqli_and_dockerfile_issues(self):
        titles = sorted(self._titles())
        # snapshot: at least the SQLi rule fires; titles are rule names (not prose)
        self.assertTrue(any("sql" in t.lower() for t in titles), titles)
        self.assertTrue(all(" " not in t for t in titles), f"titles must be rule slugs: {titles}")

    def test_every_finding_has_a_derived_cwe(self):
        cwes = {(f.cwe or "CWE-Unknown") for f in self.findings}
        self.assertNotIn("CWE-Unknown", cwes, f"derive_cwe regressed: {cwes}")

    def test_snapshot_exact_rule_set_and_cwes(self):
        """The full lock: exact rule slugs + their derived CWE. Update only on a
        deliberate detector/rules/CWE change (and record it in metrics/)."""
        got = {normalize(f, "s", "u")[0]["title"]: f.cwe for f in self.findings}
        self.assertEqual(got, _EXPECTED_TITLE_CWE)
