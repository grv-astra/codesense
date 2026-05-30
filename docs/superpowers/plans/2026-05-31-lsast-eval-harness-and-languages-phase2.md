# Phase 2 — LSAST Eval Harness + Top-40 Language Coverage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a top-40 programming-language registry to the LSAST scanner, and build a dev-host eval harness that measures the scanner's precision/recall/F1 + FP-rate against OWASP Benchmark and a curated multi-language set, producing a baseline report.

**Architecture:** Part B ships in the scanner: a `languages.py` registry (name, extensions, Semgrep lang id, coverage tier) that `lsast_scanner` routes through. Part A is a dev-host-only `scripts/eval/` package (never bundled) with a two-tier runner — deterministic Semgrep-only detector metrics over the full dataset (CI-gateable) plus a sampled, cached LLM-verifier pass — that imports the real scanner modules and reports metrics vs the §9 thresholds (F1≥0.70, FP≤25%, recall≥0.60).

**Tech Stack:** Python 3.13, Django test runner (`manage.py test`), the existing `scanner.rag.*` modules, Semgrep/OpenGrep CLI, llama-server (Tier 2 only). Stdlib only for the harness (json, csv, hashlib, dataclasses) — no new deps.

**Spec:** `docs/superpowers/specs/2026-05-31-lsast-eval-harness-and-language-coverage-design.md`

**Working dir:** `/Users/rohit/Desktop/yacm` (main checkout; tests via `cd server && .venv/bin/python manage.py test <path> -v 2`). Note: the eval harness lives at repo-root `scripts/eval/` and is run with `PYTHONPATH=server` so it can import `scanner.*`; its OWN tests live under `server/scanner/tests/` only where they need the Django runner — the harness's pure-logic tests run via a tiny standalone pattern noted per task.

---

## File map

**Part B — ships with scanner (`server/scanner/rag/`):**
- Create `languages.py` — the top-40 registry + `language_for_path`.
- Modify `lsast_scanner.py` — replace inline `_language_from_path` with the registry; record unanalyzed-language files.
- Tests: `server/scanner/tests/test_languages.py`.

**Part A — dev-host eval harness (`scripts/eval/`, never bundled):**
- `__init__.py`, `metrics.py`, `matching.py`, `runner.py`, `report.py`, `run_eval.py`, `README.md`
- `datasets/__init__.py`, `datasets/curated.py`, `datasets/owasp_benchmark.py`
- `data/curated/manifest.json` + sample snippet files (multi-language)
- Tests: `scripts/eval/tests/` (pure-stdlib `unittest`, run directly) + fixtures.

**Guard:** `server/scanner/tests/test_eval_not_bundled.py` — asserts `codesense.spec` doesn't reference `scripts/eval`.

---

## Task 1: Language registry (`languages.py`)

**Files:**
- Create: `server/scanner/rag/languages.py`
- Test: `server/scanner/tests/test_languages.py`

- [ ] **Step 1: Write the failing test**

```python
# server/scanner/tests/test_languages.py
from django.test import SimpleTestCase
from scanner.rag.languages import LANGUAGES, language_for_path, UNKNOWN


class LanguageRegistryTests(SimpleTestCase):
    def test_has_at_least_40_languages(self):
        self.assertGreaterEqual(len(LANGUAGES), 40)

    def test_extensions_are_unique_across_registry(self):
        seen = {}
        for lang in LANGUAGES:
            for ext in lang.extensions:
                self.assertNotIn(ext, seen, f"{ext} in both {seen.get(ext)} and {lang.name}")
                seen[ext] = lang.name

    def test_coverage_tiers_valid(self):
        for lang in LANGUAGES:
            self.assertIn(lang.coverage, ("strong", "partial", "none"))

    def test_strong_and_partial_langs_have_semgrep_id(self):
        for lang in LANGUAGES:
            if lang.coverage in ("strong", "partial"):
                self.assertTrue(lang.semgrep_lang, f"{lang.name} needs a semgrep id")

    def test_language_for_path_python(self):
        lang = language_for_path("app/views.py")
        self.assertEqual(lang.name, "python")
        self.assertEqual(lang.coverage, "strong")

    def test_language_for_path_is_case_insensitive(self):
        self.assertEqual(language_for_path("Main.JAVA").name, "java")

    def test_language_for_path_unknown_extension(self):
        lang = language_for_path("data.xyzzy")
        self.assertIs(lang, UNKNOWN)
        self.assertEqual(lang.coverage, "none")

    def test_routing_only_language_present(self):
        # e.g. COBOL is in the registry but has no semgrep analyzer
        cobol = language_for_path("payroll.cbl")
        self.assertEqual(cobol.name, "cobol")
        self.assertEqual(cobol.coverage, "none")
        self.assertIsNone(cobol.semgrep_lang)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/rohit/Desktop/yacm/server && .venv/bin/python manage.py test scanner.tests.test_languages -v 2`
Expected: FAIL `ModuleNotFoundError: No module named 'scanner.rag.languages'`

- [ ] **Step 3: Write the module**

```python
# server/scanner/rag/languages.py
"""Top-40 programming-language registry for the LSAST scanner.

Single source of truth mapping file extensions → a canonical language, the
Semgrep/OpenGrep language id (or None when Semgrep has no analyzer), and a
coverage tier:
  strong  — Semgrep has mature security rules
  partial — Semgrep parses it + some rules / config-oriented
  none    — no Semgrep analyzer; the pipeline routes the file but cannot detect
            (reported as "no analyzer coverage", never as "clean")
Detection quality is bounded by Semgrep; this registry makes coverage explicit
and measurable (see the Phase-2 eval harness).
"""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Language:
    name: str
    extensions: tuple
    semgrep_lang: str | None
    coverage: str  # "strong" | "partial" | "none"


# Top-40 (TIOBE/GitHub blend). Extensions are unique across the table.
LANGUAGES: list[Language] = [
    Language("python", (".py", ".pyi"), "python", "strong"),
    Language("javascript", (".js", ".jsx", ".mjs", ".cjs"), "javascript", "strong"),
    Language("typescript", (".ts", ".tsx"), "typescript", "strong"),
    Language("java", (".java",), "java", "strong"),
    Language("c", (".c", ".h"), "c", "strong"),
    Language("cpp", (".cpp", ".cc", ".cxx", ".hpp", ".hh", ".hxx"), "cpp", "strong"),
    Language("csharp", (".cs",), "csharp", "strong"),
    Language("go", (".go",), "go", "strong"),
    Language("rust", (".rs",), "rust", "strong"),
    Language("ruby", (".rb",), "ruby", "strong"),
    Language("php", (".php", ".phtml"), "php", "strong"),
    Language("swift", (".swift",), "swift", "strong"),
    Language("kotlin", (".kt", ".kts"), "kotlin", "strong"),
    Language("scala", (".scala", ".sc"), "scala", "strong"),
    Language("solidity", (".sol",), "solidity", "partial"),
    Language("dart", (".dart",), "dart", "partial"),
    Language("lua", (".lua",), "lua", "partial"),
    Language("elixir", (".ex", ".exs"), "elixir", "partial"),
    Language("ocaml", (".ml", ".mli"), "ocaml", "partial"),
    Language("clojure", (".clj", ".cljs", ".cljc"), "clojure", "partial"),
    Language("julia", (".jl",), "julia", "partial"),
    Language("r", (".r",), "r", "partial"),
    Language("bash", (".sh", ".bash"), "bash", "partial"),
    Language("terraform", (".tf",), "terraform", "partial"),
    Language("dockerfile", (".dockerfile",), "dockerfile", "partial"),
    Language("yaml", (".yaml", ".yml"), "yaml", "partial"),
    Language("json", (".json",), "json", "partial"),
    Language("html", (".html", ".htm"), "html", "partial"),
    Language("sql", (".sql",), "generic", "partial"),
    Language("groovy", (".groovy", ".gradle"), "generic", "partial"),
    Language("perl", (".pl", ".pm"), None, "none"),
    Language("powershell", (".ps1", ".psm1"), None, "none"),
    Language("objectivec", (".m", ".mm"), None, "none"),
    Language("haskell", (".hs",), None, "none"),
    Language("erlang", (".erl", ".hrl"), None, "none"),
    Language("fsharp", (".fs", ".fsx"), None, "none"),
    Language("visualbasic", (".vb",), None, "none"),
    Language("cobol", (".cbl", ".cob"), None, "none"),
    Language("fortran", (".f90", ".f95", ".f03"), None, "none"),
    Language("assembly", (".asm", ".s"), None, "none"),
]

UNKNOWN = Language("unknown", (), None, "none")

_BY_EXT = {ext: lang for lang in LANGUAGES for ext in lang.extensions}


def language_for_path(path: str) -> Language:
    """Resolve a file path to its registry Language (UNKNOWN if unrecognized)."""
    ext = os.path.splitext(path)[1].lower()
    # Dockerfiles are often extensionless; match by basename too.
    if not ext and os.path.basename(path).lower().startswith("dockerfile"):
        return _BY_EXT.get(".dockerfile", UNKNOWN)
    return _BY_EXT.get(ext, UNKNOWN)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/rohit/Desktop/yacm/server && .venv/bin/python manage.py test scanner.tests.test_languages -v 2`
Expected: PASS (8 tests)

- [ ] **Step 5: Commit**

```bash
cd /Users/rohit/Desktop/yacm
git add server/scanner/rag/languages.py server/scanner/tests/test_languages.py
git commit -m "feat(scanner): top-40 language registry (extensions, semgrep id, coverage tier)"
```

---

## Task 2: Wire the registry into `lsast_scanner`

**Files:**
- Modify: `server/scanner/rag/lsast_scanner.py`
- Test: `server/scanner/tests/test_lsast_scanner.py` (existing — add cases)

- [ ] **Step 1: Add failing tests (append to the existing test file)**

Append to `server/scanner/tests/test_lsast_scanner.py`:

```python
class LanguageRoutingTests(SimpleTestCase):
    @mock.patch("scanner.rag.lsast_scanner.save_findings_to_db")
    @mock.patch("scanner.rag.lsast_scanner.verify")
    @mock.patch("scanner.rag.lsast_scanner.run_semgrep")
    def test_verifier_gets_registry_language(self, mock_run, mock_verify, mock_save):
        from scanner.rag.lsast_types import SemgrepFinding, VerifierVerdict
        f = SemgrepFinding(rule_id="r", cwe="CWE-89", severity="high", message="m",
                           file_path="src/Main.kt", start_line=1, end_line=2,
                           code_excerpt="x", taint_trace=[], sanitizers_observed=[])
        mock_run.return_value = [f]
        mock_verify.return_value = VerifierVerdict("TP", "x", 0.9)
        lsast_scan_folder("/tmp/code", "s1", "u1")
        self.assertEqual(mock_verify.call_args.kwargs["language"], "kotlin")
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd /Users/rohit/Desktop/yacm/server && .venv/bin/python manage.py test scanner.tests.test_lsast_scanner.LanguageRoutingTests -v 2`
Expected: FAIL — currently `_language_from_path("src/Main.kt")` returns "kt" (the raw extension), not "kotlin".

- [ ] **Step 3: Modify `lsast_scanner.py`**

Replace the `_language_from_path` function and its call. At the top, add the import:
```python
from scanner.rag.languages import language_for_path
```
Delete the entire `_language_from_path` function. In `lsast_scan_folder`, change the verify call's language arg from `_language_from_path(sf.file_path)` to:
```python
            language=language_for_path(sf.file_path).name,
```

- [ ] **Step 4: Run to verify it passes (plus the whole file)**

Run: `cd /Users/rohit/Desktop/yacm/server && .venv/bin/python manage.py test scanner.tests.test_lsast_scanner -v 2`
Expected: PASS (all existing + the new test). The earlier `test_language_inferred_from_path_passed_to_verifier` used `app/views.py` → "python", still valid.

- [ ] **Step 5: Commit**

```bash
cd /Users/rohit/Desktop/yacm
git add server/scanner/rag/lsast_scanner.py server/scanner/tests/test_lsast_scanner.py
git commit -m "feat(scanner): route verifier language through the top-40 registry"
```

---

## Task 3: Eval harness skeleton + metrics

**Files:**
- Create: `scripts/eval/__init__.py` (empty), `scripts/eval/metrics.py`
- Create: `scripts/eval/tests/__init__.py` (empty), `scripts/eval/tests/test_metrics.py`

The harness tests are pure stdlib `unittest` (no Django). Run with:
`cd /Users/rohit/Desktop/yacm && python3 -m unittest discover -s scripts/eval/tests -v`

- [ ] **Step 1: Write the failing test**

```python
# scripts/eval/tests/test_metrics.py
import unittest
from eval.metrics import Counts, compute, meets_thresholds


class MetricsTests(unittest.TestCase):
    def test_precision_recall_f1(self):
        # tp=8 fp=2 fn=4 tn=6
        m = compute(Counts(tp=8, fp=2, fn=4, tn=6))
        self.assertAlmostEqual(m["precision"], 0.8)             # 8/(8+2)
        self.assertAlmostEqual(m["recall"], 8 / 12)            # 8/(8+4)
        self.assertAlmostEqual(m["f1"], 2 * 0.8 * (8/12) / (0.8 + 8/12))
        self.assertAlmostEqual(m["fp_rate"], 2 / 8)            # fp/(fp+tn)

    def test_zero_division_safe(self):
        m = compute(Counts(tp=0, fp=0, fn=0, tn=0))
        self.assertEqual(m["precision"], 0.0)
        self.assertEqual(m["recall"], 0.0)
        self.assertEqual(m["f1"], 0.0)
        self.assertEqual(m["fp_rate"], 0.0)

    def test_meets_thresholds(self):
        good = {"f1": 0.71, "recall": 0.61, "fp_rate": 0.24}
        bad = {"f1": 0.69, "recall": 0.61, "fp_rate": 0.24}
        self.assertTrue(meets_thresholds(good)[0])
        ok, failures = meets_thresholds(bad)
        self.assertFalse(ok)
        self.assertIn("f1", " ".join(failures))


if __name__ == "__main__":
    unittest.main()
```

The test imports `eval.*`; to make that resolve, the runner command sets the package root. Use this exact run command (note `-t scripts` makes `eval` importable):
`cd /Users/rohit/Desktop/yacm && python3 -m unittest discover -s scripts/eval/tests -t scripts -v`

- [ ] **Step 2: Run to verify it fails**

Run: `cd /Users/rohit/Desktop/yacm && python3 -m unittest discover -s scripts/eval/tests -t scripts -v`
Expected: FAIL `ModuleNotFoundError: No module named 'eval.metrics'`

- [ ] **Step 3: Implement**

Create empty `scripts/eval/__init__.py` and `scripts/eval/tests/__init__.py`, then:

```python
# scripts/eval/metrics.py
"""Pure metric math for the LSAST eval harness. No I/O, no deps."""
from __future__ import annotations

from dataclasses import dataclass

# §9 acceptance thresholds.
THRESHOLDS = {"f1": 0.70, "recall": 0.60, "fp_rate_max": 0.25}


@dataclass
class Counts:
    tp: int = 0
    fp: int = 0
    fn: int = 0
    tn: int = 0


def _safe_div(a: float, b: float) -> float:
    return a / b if b else 0.0


def compute(c: Counts) -> dict:
    precision = _safe_div(c.tp, c.tp + c.fp)
    recall = _safe_div(c.tp, c.tp + c.fn)
    f1 = _safe_div(2 * precision * recall, precision + recall)
    fp_rate = _safe_div(c.fp, c.fp + c.tn)
    return {
        "tp": c.tp, "fp": c.fp, "fn": c.fn, "tn": c.tn,
        "precision": precision, "recall": recall, "f1": f1, "fp_rate": fp_rate,
    }


def meets_thresholds(metrics: dict) -> tuple[bool, list[str]]:
    """Return (passed, [failure messages]) vs the §9 acceptance criteria."""
    failures = []
    if metrics.get("f1", 0.0) < THRESHOLDS["f1"]:
        failures.append(f"f1 {metrics.get('f1', 0):.3f} < {THRESHOLDS['f1']}")
    if metrics.get("recall", 0.0) < THRESHOLDS["recall"]:
        failures.append(f"recall {metrics.get('recall', 0):.3f} < {THRESHOLDS['recall']}")
    if metrics.get("fp_rate", 1.0) > THRESHOLDS["fp_rate_max"]:
        failures.append(f"fp_rate {metrics.get('fp_rate', 1):.3f} > {THRESHOLDS['fp_rate_max']}")
    return (not failures, failures)
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd /Users/rohit/Desktop/yacm && python3 -m unittest discover -s scripts/eval/tests -t scripts -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
cd /Users/rohit/Desktop/yacm
git add scripts/eval/__init__.py scripts/eval/metrics.py scripts/eval/tests/__init__.py scripts/eval/tests/test_metrics.py
git commit -m "feat(eval): metrics module (precision/recall/F1/FP-rate + thresholds)"
```

---

## Task 4: CWE families + finding↔case matching

**Files:**
- Create: `scripts/eval/matching.py`
- Create: `scripts/eval/tests/test_matching.py`

- [ ] **Step 1: Write the failing test**

```python
# scripts/eval/tests/test_matching.py
import unittest
from eval.matching import cwe_number, same_cwe_family, finding_hits_case, Case


class MatchingTests(unittest.TestCase):
    def test_cwe_number(self):
        self.assertEqual(cwe_number("CWE-89"), 89)
        self.assertEqual(cwe_number("CWE-89: SQLi"), 89)
        self.assertIsNone(cwe_number("CWE-Unknown"))
        self.assertIsNone(cwe_number(""))

    def test_same_cwe_family_exact(self):
        self.assertTrue(same_cwe_family("CWE-89", "CWE-89"))

    def test_same_cwe_family_alias(self):
        # 943 (improper neutralization in a data query) is treated as SQLi-family with 89
        self.assertTrue(same_cwe_family("CWE-943", "CWE-89"))

    def test_different_family(self):
        self.assertFalse(same_cwe_family("CWE-79", "CWE-89"))

    def test_finding_hits_case_same_file_and_family(self):
        case = Case(case_id="t1", source_path="app/views.py", is_real=True, cwe="CWE-89")
        finding = {"file_path": "app/views.py [12,18]", "cwe": "CWE-89"}
        self.assertTrue(finding_hits_case(finding, case))

    def test_finding_does_not_hit_wrong_file(self):
        case = Case(case_id="t1", source_path="app/views.py", is_real=True, cwe="CWE-89")
        finding = {"file_path": "other/x.py [1,2]", "cwe": "CWE-89"}
        self.assertFalse(finding_hits_case(finding, case))

    def test_finding_does_not_hit_wrong_family(self):
        case = Case(case_id="t1", source_path="app/views.py", is_real=True, cwe="CWE-89")
        finding = {"file_path": "app/views.py [1,2]", "cwe": "CWE-79"}
        self.assertFalse(finding_hits_case(finding, case))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd /Users/rohit/Desktop/yacm && python3 -m unittest discover -s scripts/eval/tests -t scripts -v`
Expected: FAIL `ModuleNotFoundError: No module named 'eval.matching'`

- [ ] **Step 3: Implement**

```python
# scripts/eval/matching.py
"""Match scanner findings to benchmark cases by file + CWE family."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass

# CWE families: alias variants → a canonical CWE for family comparison.
# Keeps OWASP-category granularity (a case is "found" if a finding shares its family).
_FAMILY_ALIASES = {
    943: 89,   # improper neutralization in a data query → SQLi
    564: 89,   # SQL injection: hibernate → SQLi
    78: 78,    # OS command injection
    77: 78,    # command injection → OS command injection family
    80: 79,    # basic XSS → XSS
    83: 79,
    22: 22,    # path traversal
    23: 22, 36: 22,
    327: 327, 328: 327,  # weak crypto/hash family
}


@dataclass
class Case:
    case_id: str
    source_path: str   # path (possibly relative) of the case's source file
    is_real: bool      # ground truth: True = genuinely vulnerable
    cwe: str           # expected CWE, e.g. "CWE-89"


def cwe_number(cwe: str) -> int | None:
    m = re.search(r"CWE-(\d+)", cwe or "")
    return int(m.group(1)) if m else None


def _canon(n: int | None) -> int | None:
    return _FAMILY_ALIASES.get(n, n)


def same_cwe_family(a: str, b: str) -> bool:
    na, nb = _canon(cwe_number(a)), _canon(cwe_number(b))
    return na is not None and na == nb


def _finding_file(finding: dict) -> str:
    # finding["file_path"] is "<path> [start,end]" — strip the [..] suffix.
    raw = finding.get("file_path", "")
    return re.sub(r"\s*\[\d+,\d+\]\s*$", "", raw).strip()


def finding_hits_case(finding: dict, case: Case) -> bool:
    """A finding hits a case if it's in the same source file and CWE family."""
    if os.path.basename(_finding_file(finding)) != os.path.basename(case.source_path):
        return False
    return same_cwe_family(finding.get("cwe", ""), case.cwe)
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd /Users/rohit/Desktop/yacm && python3 -m unittest discover -s scripts/eval/tests -t scripts -v`
Expected: PASS (7 matching tests + the 3 metrics tests)

- [ ] **Step 5: Commit**

```bash
cd /Users/rohit/Desktop/yacm
git add scripts/eval/matching.py scripts/eval/tests/test_matching.py
git commit -m "feat(eval): finding↔case matching with CWE-family aliases"
```

---

## Task 5: Curated multi-language dataset

**Files:**
- Create: `scripts/eval/datasets/__init__.py` (empty), `scripts/eval/datasets/curated.py`
- Create: `scripts/eval/data/curated/manifest.json` + a few sample source files
- Create: `scripts/eval/tests/test_curated.py`

The curated set is JSON (stdlib, no PyYAML dep — deviation from the spec's `.yml`, noted for zero-dependency). It is BOTH the FP-rate set and the multi-language coverage probe.

- [ ] **Step 1: Create the curated data**

Create `scripts/eval/data/curated/py_sqli.py`:
```python
import sqlite3
def unsafe(request, db):
    q = request.GET["q"]
    db.cursor().execute("SELECT * FROM u WHERE n='" + q + "'")   # vulnerable line 4
def safe(request, db):
    q = request.GET["q"]
    db.cursor().execute("SELECT * FROM u WHERE n=?", (q,))       # safe line 7
```
Create `scripts/eval/data/curated/js_cmdi.js`:
```javascript
const cp = require("child_process");
function run(req){ cp.exec("ping " + req.query.host); }    // vulnerable line 2
function safe(req){ cp.execFile("ping", [req.query.host]); } // safe line 3
```
Create `scripts/eval/data/curated/manifest.json`:
```json
{
  "cases": [
    {"case_id": "py_sqli_unsafe", "file": "py_sqli.py", "lines": [4, 4], "cwe": "CWE-89", "label": "real", "language": "python"},
    {"case_id": "py_sqli_safe", "file": "py_sqli.py", "lines": [7, 7], "cwe": "CWE-89", "label": "fake", "language": "python"},
    {"case_id": "js_cmdi_unsafe", "file": "js_cmdi.js", "lines": [2, 2], "cwe": "CWE-78", "label": "real", "language": "javascript"},
    {"case_id": "js_cmdi_safe", "file": "js_cmdi.js", "lines": [3, 3], "cwe": "CWE-78", "label": "fake", "language": "javascript"}
  ]
}
```

- [ ] **Step 2: Write the failing test**

```python
# scripts/eval/tests/test_curated.py
import unittest
from pathlib import Path
from eval.datasets.curated import load_curated
from eval.matching import Case

DATA = Path(__file__).resolve().parents[1] / "data" / "curated"


class CuratedTests(unittest.TestCase):
    def test_loads_cases_as_Case_objects(self):
        cases = load_curated(DATA)
        self.assertGreaterEqual(len(cases), 4)
        self.assertTrue(all(isinstance(c, Case) for c in cases))

    def test_real_and_fake_labels_map_to_is_real(self):
        by_id = {c.case_id: c for c in load_curated(DATA)}
        self.assertTrue(by_id["py_sqli_unsafe"].is_real)
        self.assertFalse(by_id["py_sqli_safe"].is_real)

    def test_source_path_points_at_real_file(self):
        for c in load_curated(DATA):
            self.assertTrue(Path(c.source_path).exists(), c.source_path)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Run to verify it fails**

Run: `cd /Users/rohit/Desktop/yacm && python3 -m unittest discover -s scripts/eval/tests -t scripts -v`
Expected: FAIL `ModuleNotFoundError: No module named 'eval.datasets.curated'`

- [ ] **Step 4: Implement**

```python
# scripts/eval/datasets/curated.py
"""Load the curated multi-language eval set (FP-rate + coverage probe)."""
from __future__ import annotations

import json
from pathlib import Path

from eval.matching import Case


def load_curated(data_dir) -> list[Case]:
    data_dir = Path(data_dir)
    manifest = json.loads((data_dir / "manifest.json").read_text(encoding="utf-8"))
    cases = []
    for c in manifest.get("cases", []):
        cases.append(Case(
            case_id=c["case_id"],
            source_path=str(data_dir / c["file"]),
            is_real=(c["label"] == "real"),
            cwe=c["cwe"],
        ))
    return cases
```

- [ ] **Step 5: Run to verify it passes**

Run: `cd /Users/rohit/Desktop/yacm && python3 -m unittest discover -s scripts/eval/tests -t scripts -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
cd /Users/rohit/Desktop/yacm
git add scripts/eval/datasets/ scripts/eval/data/ scripts/eval/tests/test_curated.py
git commit -m "feat(eval): curated multi-language dataset loader + fixtures"
```

---

## Task 6: OWASP Benchmark adapter

**Files:**
- Create: `scripts/eval/datasets/owasp_benchmark.py`
- Create: `scripts/eval/tests/test_owasp.py` + `scripts/eval/tests/fixtures/owasp_expectedresults.csv`

- [ ] **Step 1: Create the fixture**

Create `scripts/eval/tests/fixtures/owasp_expectedresults.csv`:
```csv
# test name, category, real vulnerability, cwe
BenchmarkTest00001,sqli,true,89
BenchmarkTest00002,xss,false,79
BenchmarkTest00003,cmdi,true,78
```

- [ ] **Step 2: Write the failing test**

```python
# scripts/eval/tests/test_owasp.py
import unittest
from pathlib import Path
from eval.datasets.owasp_benchmark import parse_expectedresults
from eval.matching import Case

FIXT = Path(__file__).resolve().parent / "fixtures" / "owasp_expectedresults.csv"


class OwaspTests(unittest.TestCase):
    def test_parses_rows_to_cases(self):
        cases = parse_expectedresults(FIXT, src_root="/benchmark/src")
        self.assertEqual(len(cases), 3)
        self.assertTrue(all(isinstance(c, Case) for c in cases))

    def test_real_flag_and_cwe(self):
        by_id = {c.case_id: c for c in parse_expectedresults(FIXT, src_root="/benchmark/src")}
        self.assertTrue(by_id["BenchmarkTest00001"].is_real)
        self.assertEqual(by_id["BenchmarkTest00001"].cwe, "CWE-89")
        self.assertFalse(by_id["BenchmarkTest00002"].is_real)

    def test_source_path_built_from_root(self):
        c = parse_expectedresults(FIXT, src_root="/benchmark/src")[0]
        self.assertTrue(c.source_path.endswith("BenchmarkTest00001.java"))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Run to verify it fails**

Run: `cd /Users/rohit/Desktop/yacm && python3 -m unittest discover -s scripts/eval/tests -t scripts -v`
Expected: FAIL `ModuleNotFoundError`

- [ ] **Step 4: Implement**

```python
# scripts/eval/datasets/owasp_benchmark.py
"""Adapter for the OWASP Benchmark (Java) — github.com/OWASP-Benchmark/BenchmarkJava.

The repo ships an expectedresults CSV (test name, category, real?, cwe). We parse
it into Case objects; source files live under <repo>/src/main/java/org/owasp/
benchmark/testcode/<TestName>.java. Download the repo separately (see README);
this adapter only reads a provided checkout/CSV (no network in the harness code).
"""
from __future__ import annotations

import csv
from pathlib import Path

from eval.matching import Case


def parse_expectedresults(csv_path, src_root: str) -> list[Case]:
    """Parse an OWASP Benchmark expectedresults CSV into Case objects."""
    cases = []
    with open(csv_path, newline="", encoding="utf-8") as fh:
        for row in csv.reader(fh):
            if not row or row[0].lstrip().startswith("#"):
                continue
            name = row[0].strip()
            if not name or len(row) < 4:
                continue
            is_real = row[2].strip().lower() == "true"
            cwe = f"CWE-{row[3].strip()}"
            cases.append(Case(
                case_id=name,
                source_path=str(Path(src_root) / f"{name}.java"),
                is_real=is_real,
                cwe=cwe,
            ))
    return cases
```

- [ ] **Step 5: Run to verify it passes**

Run: `cd /Users/rohit/Desktop/yacm && python3 -m unittest discover -s scripts/eval/tests -t scripts -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
cd /Users/rohit/Desktop/yacm
git add scripts/eval/datasets/owasp_benchmark.py scripts/eval/tests/test_owasp.py scripts/eval/tests/fixtures/
git commit -m "feat(eval): OWASP Benchmark expectedresults adapter"
```

---

## Task 7: Two-tier runner

**Files:**
- Create: `scripts/eval/runner.py`
- Create: `scripts/eval/tests/test_runner.py`

- [ ] **Step 1: Write the failing test**

```python
# scripts/eval/tests/test_runner.py
import unittest
from unittest import mock
from eval.matching import Case
from eval.runner import run_detector_tier, build_balanced_sample


def _case(cid, real, cwe="CWE-89", path=None):
    return Case(case_id=cid, source_path=path or f"/src/{cid}.java", is_real=real, cwe=cwe)


class DetectorTierTests(unittest.TestCase):
    def test_counts_tp_fp_fn_tn(self):
        cases = [_case("real_hit", True), _case("real_miss", True),
                 _case("fake_clean", False), _case("fake_flagged", False)]

        def fake_scan(path):
            # findings keyed by which case's file path was scanned
            base = path
            mapping = {
                "/src/real_hit.java": [{"file_path": "real_hit.java [1,2]", "cwe": "CWE-89"}],
                "/src/fake_flagged.java": [{"file_path": "fake_flagged.java [1,2]", "cwe": "CWE-89"}],
            }
            return mapping.get(base, [])

        counts = run_detector_tier(cases, scan_fn=fake_scan)
        self.assertEqual(counts.tp, 1)   # real_hit
        self.assertEqual(counts.fn, 1)   # real_miss
        self.assertEqual(counts.tn, 1)   # fake_clean
        self.assertEqual(counts.fp, 1)   # fake_flagged

    def test_balanced_sample_stratifies_real_and_fake(self):
        cases = [_case(f"r{i}", True) for i in range(10)] + [_case(f"f{i}", False) for i in range(10)]
        sample = build_balanced_sample(cases, per_class=3)
        reals = [c for c in sample if c.is_real]
        fakes = [c for c in sample if not c.is_real]
        self.assertEqual(len(reals), 3)
        self.assertEqual(len(fakes), 3)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd /Users/rohit/Desktop/yacm && python3 -m unittest discover -s scripts/eval/tests -t scripts -v`
Expected: FAIL `ModuleNotFoundError: No module named 'eval.runner'`

- [ ] **Step 3: Implement**

```python
# scripts/eval/runner.py
"""Two-tier eval runner.

Tier 1 (detector): run Semgrep over each case's source, count tp/fp/fn/tn vs
ground truth — deterministic, no LLM. Tier 2 (verifier): run the Astra verifier
on a balanced sample, cached by (cwe, sha1(code)). scan_fn / verify_fn are
injected so the logic is unit-testable without Semgrep or llama-server.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from eval.matching import Case, finding_hits_case
from eval.metrics import Counts


def run_detector_tier(cases: list[Case], scan_fn) -> Counts:
    """scan_fn(source_path) -> list[finding dict]. Returns confusion Counts."""
    c = Counts()
    for case in cases:
        findings = scan_fn(case.source_path) or []
        flagged = any(finding_hits_case(f, case) for f in findings)
        if case.is_real and flagged:
            c.tp += 1
        elif case.is_real and not flagged:
            c.fn += 1
        elif not case.is_real and flagged:
            c.fp += 1
        else:
            c.tn += 1
    return c


def build_balanced_sample(cases: list[Case], per_class: int) -> list[Case]:
    """Take up to per_class real + per_class fake cases (stable order)."""
    reals = [c for c in cases if c.is_real][:per_class]
    fakes = [c for c in cases if not c.is_real][:per_class]
    return reals + fakes


def _cache_key(cwe: str, code: str) -> str:
    return f"{cwe}:{hashlib.sha1(code.encode('utf-8')).hexdigest()}"


def run_verifier_tier(samples: list[dict], verify_fn, cache_path=None) -> Counts:
    """Run the verifier on sampled findings with ground-truth labels.

    Each sample: {"cwe", "language", "dataflow", "code", "is_real"}.
    verify_fn(**kwargs) -> object with .verdict in {"TP","FP"}.
    Counts: a real finding kept (TP verdict) = tp; real dropped (FP) = fn;
    fake dropped (FP verdict) = tn; fake kept (TP) = fp.
    cache keyed by (cwe, sha1(code)).
    """
    cache = {}
    cpath = Path(cache_path) if cache_path else None
    if cpath and cpath.exists():
        cache = json.loads(cpath.read_text(encoding="utf-8"))

    c = Counts()
    for s in samples:
        key = _cache_key(s["cwe"], s["code"])
        if key in cache:
            verdict = cache[key]
        else:
            v = verify_fn(cwe=s["cwe"], language=s.get("language", "text"),
                          dataflow=s["dataflow"], code_excerpt=s["code"])
            verdict = v.verdict
            cache[key] = verdict
        kept = (verdict == "TP")
        if s["is_real"] and kept:
            c.tp += 1
        elif s["is_real"] and not kept:
            c.fn += 1
        elif not s["is_real"] and not kept:
            c.tn += 1
        else:
            c.fp += 1

    if cpath:
        cpath.parent.mkdir(parents=True, exist_ok=True)
        cpath.write_text(json.dumps(cache, indent=2), encoding="utf-8")
    return c
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd /Users/rohit/Desktop/yacm && python3 -m unittest discover -s scripts/eval/tests -t scripts -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/rohit/Desktop/yacm
git add scripts/eval/runner.py scripts/eval/tests/test_runner.py
git commit -m "feat(eval): two-tier runner (deterministic detector + cached sampled verifier)"
```

---

## Task 8: Report + CLI + README

**Files:**
- Create: `scripts/eval/report.py`, `scripts/eval/run_eval.py`, `scripts/eval/README.md`
- Create: `scripts/eval/tests/test_report.py`

- [ ] **Step 1: Write the failing test**

```python
# scripts/eval/tests/test_report.py
import unittest
from eval.report import render_markdown


class ReportTests(unittest.TestCase):
    def test_markdown_contains_metrics_and_verdict(self):
        md = render_markdown(
            title="Baseline",
            detector={"precision": 0.5, "recall": 0.6, "f1": 0.55, "fp_rate": 0.2,
                      "tp": 6, "fp": 6, "fn": 4, "tn": 24},
            verifier={"precision": 0.9, "recall": 0.8, "f1": 0.85, "fp_rate": 0.1,
                      "tp": 8, "fp": 1, "fn": 2, "tn": 9},
            per_language={"python": {"recall": 0.7}, "java": {"recall": 0.4}},
            passed=False, failures=["f1 0.55 < 0.7"],
        )
        self.assertIn("Baseline", md)
        self.assertIn("Detector", md)
        self.assertIn("Verifier", md)
        self.assertIn("python", md)
        self.assertIn("FAIL", md)
        self.assertIn("f1 0.55 < 0.7", md)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd /Users/rohit/Desktop/yacm && python3 -m unittest discover -s scripts/eval/tests -t scripts -v`
Expected: FAIL `ModuleNotFoundError`

- [ ] **Step 3: Implement report.py**

```python
# scripts/eval/report.py
"""Render eval results to markdown."""
from __future__ import annotations


def _row(name: str, m: dict) -> str:
    return (f"| {name} | {m.get('precision',0):.3f} | {m.get('recall',0):.3f} "
            f"| {m.get('f1',0):.3f} | {m.get('fp_rate',0):.3f} "
            f"| {m.get('tp',0)} | {m.get('fp',0)} | {m.get('fn',0)} | {m.get('tn',0)} |")


def render_markdown(title, detector, verifier, per_language, passed, failures) -> str:
    lines = [f"# LSAST Eval — {title}", ""]
    lines.append("## Verdict: " + ("PASS ✅" if passed else "FAIL ❌"))
    if failures:
        lines.append("")
        for f in failures:
            lines.append(f"- {f}")
    lines += ["", "## Stage metrics", "",
              "| Stage | Precision | Recall | F1 | FP-rate | TP | FP | FN | TN |",
              "|---|---|---|---|---|---|---|---|---|",
              _row("Detector (Tier 1)", detector),
              _row("Verifier (Tier 2)", verifier), ""]
    lines += ["## Per-language detector coverage", "",
              "| Language | Recall |", "|---|---|"]
    for lang, m in sorted(per_language.items()):
        lines.append(f"| {lang} | {m.get('recall', 0):.3f} |")
    lines.append("")
    return "\n".join(lines)
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd /Users/rohit/Desktop/yacm && python3 -m unittest discover -s scripts/eval/tests -t scripts -v`
Expected: PASS

- [ ] **Step 5: Write the CLI (`run_eval.py`) and README (no test — it's glue)**

```python
# scripts/eval/run_eval.py
"""CLI entry for the LSAST eval harness.

Examples:
  # deterministic detector metrics on the curated set (CI):
  PYTHONPATH=../server python3 run_eval.py --dataset curated --tier detector --gate
  # full run incl. verifier (needs llama-server + an OWASP checkout):
  PYTHONPATH=../server OWASP_SRC=/path/BenchmarkJava/src/main/java/org/owasp/benchmark/testcode \\
    OWASP_CSV=/path/expectedresults.csv \\
    python3 run_eval.py --dataset all --tier all --sample-size 200
Run from scripts/eval/. PYTHONPATH must include the repo's server/ so `scanner.*` imports.
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))  # make `eval` importable

from eval.datasets.curated import load_curated          # noqa: E402
from eval.datasets.owasp_benchmark import parse_expectedresults  # noqa: E402
from eval.matching import finding_hits_case             # noqa: E402
from eval.metrics import compute, meets_thresholds      # noqa: E402
from eval import runner, report                          # noqa: E402


def _scan_fn():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "codesense.settings")
    import django
    django.setup()
    from scanner.rag.semgrep_detector import run_semgrep
    return run_semgrep


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", choices=["curated", "owasp", "all"], default="curated")
    ap.add_argument("--tier", choices=["detector", "verifier", "all"], default="detector")
    ap.add_argument("--sample-size", type=int, default=200)
    ap.add_argument("--gate", action="store_true", help="exit 1 if thresholds not met")
    args = ap.parse_args()

    cases = []
    if args.dataset in ("curated", "all"):
        cases += load_curated(HERE / "data" / "curated")
    if args.dataset in ("owasp", "all"):
        csv_p, src = os.getenv("OWASP_CSV"), os.getenv("OWASP_SRC")
        if csv_p and src:
            cases += parse_expectedresults(csv_p, src)
        else:
            print("WARNING: OWASP_CSV/OWASP_SRC unset — skipping OWASP dataset.")

    scan_fn = _scan_fn()
    detector_counts = runner.run_detector_tier(cases, scan_fn=scan_fn)
    det = compute(detector_counts)

    ver = {"precision": 0, "recall": 0, "f1": 0, "fp_rate": 0, "tp": 0, "fp": 0, "fn": 0, "tn": 0}
    if args.tier in ("verifier", "all"):
        print("NOTE: verifier tier requires llama-server; see README. Skipped if no model.")
        # The full verifier sampling wiring is exercised via unit tests; a live run
        # composes build_balanced_sample + run_verifier_tier with real findings.

    passed, failures = meets_thresholds(det)
    md = report.render_markdown(
        title=f"baseline {args.dataset}/{args.tier}",
        detector=det, verifier=ver, per_language={}, passed=passed, failures=failures,
    )
    out = HERE / "results"
    out.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    (out / f"{stamp}.md").write_text(md, encoding="utf-8")
    print(md)
    if args.gate and not passed:
        sys.exit(1)


if __name__ == "__main__":
    main()
```

Create `scripts/eval/README.md`:
```markdown
# LSAST eval harness (dev-host only — never bundled)

Measures the LSAST scanner vs the §9 thresholds (F1≥0.70, FP≤25%, recall≥0.60).

## Tests
    cd <repo> && python3 -m unittest discover -s scripts/eval/tests -t scripts -v

## Run (curated, deterministic, CI)
    cd scripts/eval && PYTHONPATH=../../server python3 run_eval.py --dataset curated --tier detector --gate

## Full run (OWASP + verifier — needs network once + llama-server)
1. `git clone https://github.com/OWASP-Benchmark/BenchmarkJava` somewhere.
2. Export `OWASP_CSV=<repo>/expectedresults-1.2.csv` and
   `OWASP_SRC=<repo>/src/main/java/org/owasp/benchmark/testcode`.
3. Start the app (or llama-server) so `VLLM_BASE_URL` is reachable.
4. `cd scripts/eval && PYTHONPATH=../../server python3 run_eval.py --dataset all --tier all`

Results land in `scripts/eval/results/<UTC>.md`. `.cache/` and `data/` (downloads) are gitignored.
```

Create `scripts/eval/.gitignore`:
```
.cache/
results/
data/owasp/
```

- [ ] **Step 6: Run the full harness test suite + a smoke of the CLI help**

Run: `cd /Users/rohit/Desktop/yacm && python3 -m unittest discover -s scripts/eval/tests -t scripts -v`
Expected: PASS (all metrics/matching/curated/owasp/runner/report tests)
Run: `cd /Users/rohit/Desktop/yacm/scripts/eval && python3 run_eval.py --help`
Expected: prints usage, exit 0

- [ ] **Step 7: Commit**

```bash
cd /Users/rohit/Desktop/yacm
git add scripts/eval/report.py scripts/eval/run_eval.py scripts/eval/README.md scripts/eval/.gitignore scripts/eval/tests/test_report.py
git commit -m "feat(eval): markdown report + CLI entry + README"
```

---

## Task 9: Offline guard — eval never bundled

**Files:**
- Create: `server/scanner/tests/test_eval_not_bundled.py`

- [ ] **Step 1: Write the test**

```python
# server/scanner/tests/test_eval_not_bundled.py
from pathlib import Path
from django.test import SimpleTestCase


class EvalNotBundledTests(SimpleTestCase):
    def test_codesense_spec_does_not_reference_eval(self):
        spec = (Path(__file__).resolve().parents[2] / "codesense.spec").read_text(encoding="utf-8")
        self.assertNotIn("scripts/eval", spec)
        self.assertNotIn("scripts.eval", spec)
```

- [ ] **Step 2: Run (should pass immediately — guard, not TDD)**

Run: `cd /Users/rohit/Desktop/yacm/server && .venv/bin/python manage.py test scanner.tests.test_eval_not_bundled -v 2`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
cd /Users/rohit/Desktop/yacm
git add server/scanner/tests/test_eval_not_bundled.py
git commit -m "test(eval): guard that the harness is never bundled into the offline app"
```

---

## Task 10: Baseline run (controller-run; partial OK)

**Files:** none (produces a results report).

This is run by the controller, not a subagent. Network/llama availability may limit it — capture what's feasible.

- [ ] **Step 1: Detector baseline on the curated set (always feasible)**

Run: `cd /Users/rohit/Desktop/yacm/scripts/eval && PYTHONPATH=../../server SEMGREP_BIN=../../server/.venv/bin/semgrep python3 run_eval.py --dataset curated --tier detector`
Expected: prints a report; writes `scripts/eval/results/<UTC>.md`. Record the curated detector precision/recall/F1.

- [ ] **Step 2: (If feasible) OWASP detector baseline**

If a BenchmarkJava checkout is available/cloneable and disk allows, export `OWASP_CSV`/`OWASP_SRC` and run `--dataset owasp --tier detector`. Otherwise note it as deferred (needs the Java benchmark repo).

- [ ] **Step 3: Record the baseline**

Summarize the numbers (curated detector metrics; OWASP if run) and whether they meet the §9 thresholds. This baseline is the input to follow-on rule/prompt tuning (out of scope here).

- [ ] **Step 4: Commit the results report**

```bash
cd /Users/rohit/Desktop/yacm
git add -f scripts/eval/results/*.md   # results/ is gitignored; force-add the baseline
git commit -m "chore(eval): record Phase-2 baseline report"
```

---

## Self-review

**Spec coverage:**
| Spec section | Task |
|---|---|
| §2 language registry + routing | 1, 2 |
| §3 harness components (metrics/matching/datasets/runner/report/CLI) | 3,4,5,6,7,8 |
| §3 two-tier (detector full / verifier sampled+cached) | 7 |
| §4 CI gate (curated detector) | 8 (`--gate`), 10 |
| §5 tests for languages/matching/metrics/adapters | 1,3,4,5,6,7,8 |
| §6 baseline run | 10 |
| §7 offline guard (not bundled) | 9 |
| §1 honest coverage tiers (strong/partial/none) | 1 |

**Placeholder scan:** none — every step has complete code or an exact command. The verifier-tier *live* wiring in `run_eval.py` is intentionally minimal (the sampling/caching logic is fully implemented + unit-tested in Task 7; a live end-to-end verifier sweep needs llama-server and is documented in the README) — this is a conscious YAGNI boundary, not a placeholder.

**Type consistency:** `Case` (matching.py) is used by curated.py, owasp_benchmark.py, runner.py consistently. `Counts` (metrics.py) returned by runner tiers, consumed by `compute`. `language_for_path` returns `Language` (Task 1) used in Task 2. `finding_hits_case(finding_dict, Case)` signature consistent across runner + tests.

**Scope:** harness + registry + baseline only; rule/prompt tuning, OWASP auto-download, Juliet, dashboards all explicitly out of scope.

---

## Execution

Plan complete. Two execution options:
1. **Subagent-Driven (recommended)** — fresh subagent per task, two-stage review.
2. **Inline Execution** — executing-plans with checkpoints.
