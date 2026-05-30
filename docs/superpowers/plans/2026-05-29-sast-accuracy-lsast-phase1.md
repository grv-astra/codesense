# LSAST SAST Pipeline — Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current LLM-primary SAST detector with a deterministic Semgrep-first / LLM-verifier-second pipeline (LSAST), behind a feature flag, so we cut false positives ~100 % → ≤25 % without losing real findings.

**Architecture:** Semgrep (taint mode + curated rule packs, bundled offline) detects → normalizer turns each finding into the existing `Finding` dict + a focused dataflow context → constrained single-turn LLM verifier (forced JSON, temperature 0) classifies each as TP/FP with a one-sentence reason → fusion combines Semgrep severity + verdict per fixed rules (never silently drops high-severity findings).

**Tech Stack:** Python 3.13, Django 5.2, existing scanner package (`server/scanner/rag/`), existing LLM client (`scanner/rag/llm.py` → llama-server on `127.0.0.1:8001`), Semgrep CLI bundled as a sidecar (~30 MB) + bundled rule packs (~20 MB). Tests via Django's test runner (`manage.py test`).

**Spec:** `docs/superpowers/specs/2026-05-29-sast-accuracy-lsast-redesign-design.md`

**Scope of this plan:** Phase 1 only — the LSAST pipeline working end-to-end behind a feature flag, with bundled Semgrep + unit/smoke tests. Phases 2 (eval harness) and 3 (FP feedback loop) are separate plans, written after Phase 1 lands.

---

## File map (decomposition lock-in)

**Create** (in `server/scanner/rag/`):
- `lsast_types.py` — dataclasses for `SemgrepFinding`, `DataflowContext`, `VerifierVerdict`
- `semgrep_detector.py` — invokes Semgrep CLI, parses JSON to `SemgrepFinding`
- `finding_normalizer.py` — `SemgrepFinding` → existing `Finding` dict + `DataflowContext`
- `llm_verifier.py` — constrained verifier (forced JSON, strict parse, fail-open)
- `fusion.py` — combine Semgrep + verdict per fixed rules
- `lsast_scanner.py` — orchestrator: detector → normalizer → verifier → fusion

**Modify**:
- `server/scanner/rag/scanner.py` — feature flag route (`SCAN_ENGINE=lsast | legacy`)
- `server/scanner/services/tools.py` — add `get_semgrep_bin()` + `get_semgrep_rules_dir()` resolvers (matches existing syft/grype helpers)
- `server/codesense.spec` — bundle Semgrep + rule packs into the frozen backend (if running Semgrep via Python module)
- `scripts/build_macos.sh` — stage Semgrep sidecar + rule packs
- `client/src-tauri/src/main.rs` — export `SEMGREP_BIN` + `SEMGREP_RULES_DIR` env to the backend sidecar
- `scripts/offline_sbom/fetch_offline_tools.sh` — add `semgrep` to the fetched tool set

**Create** (tests, in `server/scanner/tests/`):
- `test_lsast_types.py`
- `test_semgrep_detector.py` + fixtures dir `fixtures/semgrep/`
- `test_finding_normalizer.py`
- `test_llm_verifier.py`
- `test_fusion.py`
- `test_lsast_scanner.py` (integration, mocked Semgrep + mocked LLM)

---

## Task 1: Types module (`lsast_types.py`)

**Files:**
- Create: `server/scanner/rag/lsast_types.py`
- Test: `server/scanner/tests/test_lsast_types.py`

- [ ] **Step 1: Write the failing test**

```python
# server/scanner/tests/test_lsast_types.py
from django.test import SimpleTestCase
from scanner.rag.lsast_types import SemgrepFinding, DataflowContext, VerifierVerdict


class LsastTypesTests(SimpleTestCase):
    def test_semgrep_finding_minimal(self):
        f = SemgrepFinding(
            rule_id="python.lang.security.audit.sql-injection",
            cwe="CWE-89",
            severity="high",
            message="Possible SQL injection",
            file_path="app/views.py",
            start_line=12,
            end_line=18,
            code_excerpt="cursor.execute(q)",
            taint_trace=[],
            sanitizers_observed=[],
        )
        self.assertEqual(f.cwe, "CWE-89")
        self.assertEqual(f.severity, "high")

    def test_dataflow_context_renders_for_prompt(self):
        ctx = DataflowContext(
            source_line=12, source_code="request.GET['q']",
            sink_line=18, sink_code="cursor.execute(q)",
            steps=[(14, "query = '...' + q + '...'")],
            sanitizers_observed=[],
        )
        rendered = ctx.render_for_prompt()
        self.assertIn("Source", rendered)
        self.assertIn("line 12", rendered)
        self.assertIn("Sink", rendered)
        self.assertIn("line 18", rendered)
        self.assertIn("none", rendered.lower())   # no sanitizers

    def test_verifier_verdict_parses_valid_json(self):
        v = VerifierVerdict.from_json('{"verdict":"FP","reason":"parameterized query","confidence":0.9}')
        self.assertEqual(v.verdict, "FP")
        self.assertAlmostEqual(v.confidence, 0.9)

    def test_verifier_verdict_invalid_json_returns_none(self):
        self.assertIsNone(VerifierVerdict.from_json("not json"))
        self.assertIsNone(VerifierVerdict.from_json('{"verdict":"MAYBE"}'))   # invalid verdict
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd server && .venv/bin/python manage.py test scanner.tests.test_lsast_types -v 2`
Expected: FAIL with `ModuleNotFoundError: No module named 'scanner.rag.lsast_types'`

- [ ] **Step 3: Write the module**

```python
# server/scanner/rag/lsast_types.py
"""Typed payloads for the LSAST pipeline.

Three small dataclasses that pass between the detector → normalizer → verifier
→ fusion stages. Keep them dumb: data only, no side effects, no I/O. Anything
that needs to do work lives in a dedicated module.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field


@dataclass
class SemgrepFinding:
    """One finding emitted by Semgrep, parsed from its --json output."""
    rule_id: str
    cwe: str                          # e.g. "CWE-89"; "" if rule has no cwe metadata
    severity: str                     # "low" | "medium" | "high" | "critical"
    message: str
    file_path: str
    start_line: int
    end_line: int
    code_excerpt: str
    taint_trace: list[tuple[int, str]] = field(default_factory=list)  # (line, code) per step
    sanitizers_observed: list[str] = field(default_factory=list)      # rule-reported sanitizers


@dataclass
class DataflowContext:
    """The verifier-ready dataflow summary distilled from a SemgrepFinding."""
    source_line: int
    source_code: str
    sink_line: int
    sink_code: str
    steps: list[tuple[int, str]] = field(default_factory=list)        # intermediate steps
    sanitizers_observed: list[str] = field(default_factory=list)

    def render_for_prompt(self) -> str:
        lines = [f"  Source : {self.source_code}     line {self.source_line}"]
        for ln, code in self.steps:
            lines.append(f"  → step : {code}     line {ln}")
        lines.append(f"  → Sink : {self.sink_code}     line {self.sink_line}")
        sans = ", ".join(self.sanitizers_observed) if self.sanitizers_observed else "none"
        lines.append(f"Sanitizers observed in trace: {sans}")
        return "\n".join(lines)


_ALLOWED_VERDICTS = {"TP", "FP"}


@dataclass
class VerifierVerdict:
    """Parsed verdict from the LLM verifier. None when parsing fails."""
    verdict: str           # "TP" | "FP"
    reason: str
    confidence: float

    @classmethod
    def from_json(cls, raw: str) -> "VerifierVerdict | None":
        """Strict parse: returns None on any malformedness."""
        try:
            obj = json.loads(raw)
        except (ValueError, TypeError):
            return None
        if not isinstance(obj, dict):
            return None
        verdict = obj.get("verdict")
        if verdict not in _ALLOWED_VERDICTS:
            return None
        try:
            conf = float(obj.get("confidence", 0.0))
        except (ValueError, TypeError):
            conf = 0.0
        conf = max(0.0, min(1.0, conf))
        reason = str(obj.get("reason", ""))[:200]
        return cls(verdict=verdict, reason=reason, confidence=conf)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd server && .venv/bin/python manage.py test scanner.tests.test_lsast_types -v 2`
Expected: PASS (4 tests OK)

- [ ] **Step 5: Commit**

```bash
git add server/scanner/rag/lsast_types.py server/scanner/tests/test_lsast_types.py
git commit -m "feat(scanner): add LSAST type dataclasses (SemgrepFinding, DataflowContext, VerifierVerdict)"
```

---

## Task 2: Tool resolver helpers (`tools.py` extension)

**Files:**
- Modify: `server/scanner/services/tools.py` — add `get_semgrep_bin()`, `get_semgrep_rules_dir()`
- Test: `server/scanner/tests/test_tools.py` (existing) — add test cases

- [ ] **Step 1: Read the existing file to match the pattern**

Run: `cat server/scanner/services/tools.py`
Look at how `get_syft_bin()` / `get_grype_bin()` / `get_grype_db_dir()` resolve from env → bundled dir → PATH. Replicate that exact pattern.

- [ ] **Step 2: Write the failing tests (append to existing test file)**

Append to `server/scanner/tests/test_tools.py`:

```python
# Append to existing test_tools.py
import os
import tempfile
from pathlib import Path
from unittest import mock

from scanner.services.tools import get_semgrep_bin, get_semgrep_rules_dir


class SemgrepResolverTests(SimpleTestCase):
    def test_semgrep_bin_uses_env_var_when_set(self):
        with mock.patch.dict(os.environ, {"SEMGREP_BIN": "/custom/path/semgrep"}, clear=False):
            self.assertEqual(get_semgrep_bin(), "/custom/path/semgrep")

    def test_semgrep_bin_falls_back_to_tools_dir(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "semgrep").write_text("#!/bin/sh\n")
            os.chmod(Path(d) / "semgrep", 0o755)
            with mock.patch.dict(os.environ,
                                 {"SCANNER_TOOLS_DIR": d, "SEMGREP_BIN": ""},
                                 clear=False):
                # the function should find <SCANNER_TOOLS_DIR>/semgrep
                self.assertEqual(get_semgrep_bin(), str(Path(d) / "semgrep"))

    def test_semgrep_bin_falls_back_to_path_name(self):
        with mock.patch.dict(os.environ,
                             {"SEMGREP_BIN": "", "SCANNER_TOOLS_DIR": ""},
                             clear=False):
            # When neither env var resolves a real file, return the bare command
            # so `subprocess.run([bin, ...])` falls back to PATH (dev workflow).
            self.assertEqual(get_semgrep_bin(), "semgrep")

    def test_semgrep_rules_dir_uses_env_var(self):
        with mock.patch.dict(os.environ,
                             {"SEMGREP_RULES_DIR": "/opt/rules"},
                             clear=False):
            self.assertEqual(get_semgrep_rules_dir(), "/opt/rules")

    def test_semgrep_rules_dir_returns_empty_when_unset(self):
        with mock.patch.dict(os.environ, {"SEMGREP_RULES_DIR": ""}, clear=False):
            self.assertEqual(get_semgrep_rules_dir(), "")
```

(Add `from django.test import SimpleTestCase` if not already imported at the top.)

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd server && .venv/bin/python manage.py test scanner.tests.test_tools.SemgrepResolverTests -v 2`
Expected: FAIL with `ImportError: cannot import name 'get_semgrep_bin'`

- [ ] **Step 4: Implement the resolvers (append to `tools.py`)**

Append to `server/scanner/services/tools.py`:

```python
# Append to existing tools.py
import os
from pathlib import Path


def get_semgrep_bin() -> str:
    """Resolve the Semgrep binary path.

    Order: SEMGREP_BIN env var → <SCANNER_TOOLS_DIR>/semgrep → bare "semgrep" (PATH).
    """
    explicit = os.environ.get("SEMGREP_BIN", "").strip()
    if explicit:
        return explicit

    tools_dir = os.environ.get("SCANNER_TOOLS_DIR", "").strip()
    if tools_dir:
        candidate = Path(tools_dir) / "semgrep"
        if candidate.exists():
            return str(candidate)

    return "semgrep"


def get_semgrep_rules_dir() -> str:
    """Resolve the bundled Semgrep rule packs directory (empty if not bundled)."""
    return os.environ.get("SEMGREP_RULES_DIR", "").strip()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd server && .venv/bin/python manage.py test scanner.tests.test_tools -v 2`
Expected: PASS (all tests, including the existing ones)

- [ ] **Step 6: Commit**

```bash
git add server/scanner/services/tools.py server/scanner/tests/test_tools.py
git commit -m "feat(scanner): resolve Semgrep binary + rules dir from env, with bundled-tools fallback"
```

---

## Task 3: Semgrep detector with fixture-based test

**Files:**
- Create: `server/scanner/rag/semgrep_detector.py`
- Create: `server/scanner/tests/fixtures/semgrep/sample_sqli.json`
- Create: `server/scanner/tests/test_semgrep_detector.py`

- [ ] **Step 1: Capture a small Semgrep JSON fixture**

Create `server/scanner/tests/fixtures/semgrep/sample_sqli.json` with this content (one finding shaped like Semgrep's real `--json` output):

```json
{
  "version": "1.0.0",
  "results": [
    {
      "check_id": "python.lang.security.audit.sql-injection.tainted-sql-string",
      "path": "app/views.py",
      "start": {"line": 12, "col": 5},
      "end":   {"line": 18, "col": 40},
      "extra": {
        "message": "Possible SQL injection: user-controlled data flows into a SQL statement.",
        "severity": "ERROR",
        "metadata": {
          "cwe": ["CWE-89: Improper Neutralization of Special Elements used in an SQL Command"],
          "owasp": ["A03:2021 - Injection"]
        },
        "lines": "q = request.GET['q']\nquery = \"SELECT * FROM u WHERE name='\" + q + \"'\"\ncursor.execute(query)",
        "dataflow_trace": {
          "taint_source": [{"start": {"line": 12}, "code": "request.GET['q']"}],
          "intermediate_vars": [
            {"location": {"line": 14}, "content": "query = \"SELECT ...\" + q + \"...\""}
          ],
          "taint_sink": [{"start": {"line": 18}, "code": "cursor.execute(query)"}]
        }
      }
    }
  ],
  "errors": [],
  "paths": {"scanned": ["app/views.py"]}
}
```

- [ ] **Step 2: Write the failing test**

```python
# server/scanner/tests/test_semgrep_detector.py
import json
from pathlib import Path
from unittest import mock

from django.test import SimpleTestCase

from scanner.rag.semgrep_detector import run_semgrep, parse_semgrep_json
from scanner.rag.lsast_types import SemgrepFinding


FIXTURE = Path(__file__).parent / "fixtures" / "semgrep" / "sample_sqli.json"


class ParseSemgrepJsonTests(SimpleTestCase):
    def test_parses_one_finding(self):
        raw = FIXTURE.read_text()
        findings = parse_semgrep_json(raw)
        self.assertEqual(len(findings), 1)
        f = findings[0]
        self.assertIsInstance(f, SemgrepFinding)
        self.assertEqual(f.rule_id, "python.lang.security.audit.sql-injection.tainted-sql-string")
        self.assertEqual(f.cwe, "CWE-89")
        self.assertEqual(f.severity, "high")          # ERROR -> high
        self.assertEqual(f.file_path, "app/views.py")
        self.assertEqual(f.start_line, 12)
        self.assertEqual(f.end_line, 18)
        self.assertIn("cursor.execute", f.code_excerpt)
        # taint trace: source + 1 intermediate + sink = 3 entries
        self.assertEqual(len(f.taint_trace), 3)
        self.assertEqual(f.taint_trace[0][0], 12)     # source line
        self.assertEqual(f.taint_trace[-1][0], 18)    # sink line

    def test_empty_results_returns_empty_list(self):
        findings = parse_semgrep_json('{"version":"1","results":[],"errors":[]}')
        self.assertEqual(findings, [])

    def test_malformed_json_returns_empty_list(self):
        self.assertEqual(parse_semgrep_json("not json"), [])
        self.assertEqual(parse_semgrep_json(""), [])


class RunSemgrepTests(SimpleTestCase):
    @mock.patch("scanner.rag.semgrep_detector.subprocess.run")
    @mock.patch("scanner.rag.semgrep_detector.get_semgrep_bin", return_value="/bin/semgrep")
    @mock.patch("scanner.rag.semgrep_detector.get_semgrep_rules_dir", return_value="/rules")
    def test_invokes_semgrep_with_rules_and_returns_findings(self, _rules, _bin, mock_run):
        mock_run.return_value = mock.Mock(returncode=0,
                                          stdout=FIXTURE.read_text(),
                                          stderr="")
        findings = run_semgrep("/some/code/path")
        self.assertEqual(len(findings), 1)
        args, kwargs = mock_run.call_args
        cmd = args[0]
        self.assertIn("/bin/semgrep", cmd)
        self.assertIn("--config", cmd)
        self.assertIn("/rules", cmd)
        self.assertIn("--json", cmd)
        self.assertIn("/some/code/path", cmd)

    @mock.patch("scanner.rag.semgrep_detector.subprocess.run")
    @mock.patch("scanner.rag.semgrep_detector.get_semgrep_bin", return_value="/bin/semgrep")
    @mock.patch("scanner.rag.semgrep_detector.get_semgrep_rules_dir", return_value="")
    def test_falls_back_to_security_audit_pack_when_no_bundled_rules(self, *_):
        mock_run.return_value = mock.Mock(returncode=0, stdout='{"results":[]}', stderr="")
        with mock.patch("scanner.rag.semgrep_detector.subprocess.run", mock_run):
            run_semgrep("/code")
        args, _ = mock_run.call_args
        self.assertIn("p/security-audit", args[0])
        self.assertIn("p/owasp-top-ten", args[0])

    @mock.patch("scanner.rag.semgrep_detector.subprocess.run")
    @mock.patch("scanner.rag.semgrep_detector.get_semgrep_bin", return_value="/bin/semgrep")
    @mock.patch("scanner.rag.semgrep_detector.get_semgrep_rules_dir", return_value="/rules")
    def test_returns_empty_on_semgrep_failure(self, _rules, _bin, mock_run):
        mock_run.return_value = mock.Mock(returncode=2, stdout="", stderr="rule load error")
        self.assertEqual(run_semgrep("/code"), [])
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd server && .venv/bin/python manage.py test scanner.tests.test_semgrep_detector -v 2`
Expected: FAIL with `ModuleNotFoundError: No module named 'scanner.rag.semgrep_detector'`

- [ ] **Step 4: Implement the detector**

Create `server/scanner/rag/semgrep_detector.py`:

```python
"""Run Semgrep over a folder and parse its --json output into SemgrepFinding objects.

The detector is intentionally narrow: it shells out to the Semgrep binary,
captures stdout, and translates the JSON to our dataclass. No filtering, no
heuristics, no LLM — those live in downstream modules.
"""
from __future__ import annotations

import json
import logging
import subprocess
from typing import Any

from scanner.rag.lsast_types import SemgrepFinding
from scanner.services.tools import get_semgrep_bin, get_semgrep_rules_dir

logger = logging.getLogger(__name__)

# Severities Semgrep emits → our normalized vocabulary.
_SEVERITY_MAP = {
    "ERROR": "high",
    "WARNING": "medium",
    "INFO": "low",
}

# When no bundled rules dir is configured, fall back to the registry pack names.
# These resolve offline only if Semgrep's local rule cache has them — in
# packaged builds SEMGREP_RULES_DIR should always be set.
_DEFAULT_REGISTRY_PACKS = ["p/security-audit", "p/owasp-top-ten", "p/secrets"]

# Hard cap so a misconfigured rule doesn't tar-pit the scan.
_TIMEOUT_SECONDS = 300


def _extract_cwe(metadata: dict[str, Any]) -> str:
    """Return the first 'CWE-NNN' from Semgrep metadata, or '' if none."""
    cwes = metadata.get("cwe") or []
    if isinstance(cwes, str):
        cwes = [cwes]
    for entry in cwes:
        if not isinstance(entry, str):
            continue
        # "CWE-89: Improper Neutralization..." → "CWE-89"
        head = entry.split(":", 1)[0].strip()
        if head.startswith("CWE-"):
            return head
    return ""


def _extract_taint_trace(extra: dict[str, Any]) -> list[tuple[int, str]]:
    """Flatten Semgrep's dataflow_trace { source[], intermediate[], sink[] } to (line, code)."""
    trace: list[tuple[int, str]] = []
    df = extra.get("dataflow_trace") or {}

    def _append(items, code_key: str):
        for item in items or []:
            loc = item.get("start") or item.get("location") or {}
            line = loc.get("line") if isinstance(loc, dict) else None
            code = item.get(code_key) or item.get("code") or ""
            if isinstance(line, int) and isinstance(code, str):
                trace.append((line, code.strip()))

    _append(df.get("taint_source"), "code")
    _append(df.get("intermediate_vars"), "content")
    _append(df.get("taint_sink"), "code")
    return trace


def parse_semgrep_json(raw: str) -> list[SemgrepFinding]:
    """Translate Semgrep's --json output into SemgrepFinding objects. Robust to malformedness."""
    try:
        doc = json.loads(raw)
    except (ValueError, TypeError):
        logger.warning("Could not parse Semgrep JSON output")
        return []
    if not isinstance(doc, dict):
        return []

    findings: list[SemgrepFinding] = []
    for r in doc.get("results", []) or []:
        if not isinstance(r, dict):
            continue
        extra = r.get("extra") or {}
        metadata = extra.get("metadata") or {}
        severity_raw = (extra.get("severity") or "").upper()
        try:
            findings.append(SemgrepFinding(
                rule_id=str(r.get("check_id", "")),
                cwe=_extract_cwe(metadata),
                severity=_SEVERITY_MAP.get(severity_raw, "medium"),
                message=str(extra.get("message", "")),
                file_path=str(r.get("path", "")),
                start_line=int((r.get("start") or {}).get("line", 0)),
                end_line=int((r.get("end") or {}).get("line", 0)),
                code_excerpt=str(extra.get("lines", "")),
                taint_trace=_extract_taint_trace(extra),
                sanitizers_observed=[],   # Semgrep doesn't expose this directly today
            ))
        except (TypeError, ValueError) as exc:
            logger.warning("Skipping malformed Semgrep result: %s", exc)
            continue
    return findings


def run_semgrep(folder_path: str) -> list[SemgrepFinding]:
    """Invoke Semgrep with bundled rules (or registry packs) and return parsed findings."""
    bin_path = get_semgrep_bin()
    rules_dir = get_semgrep_rules_dir()

    cmd = [bin_path]
    if rules_dir:
        cmd += ["--config", rules_dir]
    else:
        for pack in _DEFAULT_REGISTRY_PACKS:
            cmd += ["--config", pack]
    cmd += ["--json", "--quiet", "--metrics", "off", "--disable-version-check", folder_path]

    logger.info("Running Semgrep: %s", " ".join(cmd))
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=_TIMEOUT_SECONDS, check=False,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        logger.warning("Semgrep invocation failed: %s", exc)
        return []

    # Semgrep returns 1 when it finds matches; only treat 2+ as a hard failure.
    if result.returncode >= 2:
        logger.warning("Semgrep failed (rc=%d): %s", result.returncode, result.stderr[:500])
        return []

    return parse_semgrep_json(result.stdout)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd server && .venv/bin/python manage.py test scanner.tests.test_semgrep_detector -v 2`
Expected: PASS (all parse + run tests)

- [ ] **Step 6: Commit**

```bash
git add server/scanner/rag/semgrep_detector.py server/scanner/tests/test_semgrep_detector.py server/scanner/tests/fixtures/
git commit -m "feat(scanner): add Semgrep detector — invoke CLI, parse JSON to SemgrepFinding"
```

---

## Task 4: Finding normalizer

**Files:**
- Create: `server/scanner/rag/finding_normalizer.py`
- Create: `server/scanner/tests/test_finding_normalizer.py`

- [ ] **Step 1: Write the failing tests**

```python
# server/scanner/tests/test_finding_normalizer.py
import uuid

from django.test import SimpleTestCase

from scanner.rag.finding_normalizer import normalize, build_dataflow_context
from scanner.rag.lsast_types import SemgrepFinding


def _sample_finding() -> SemgrepFinding:
    return SemgrepFinding(
        rule_id="python.lang.security.audit.sql-injection.tainted-sql-string",
        cwe="CWE-89",
        severity="high",
        message="Possible SQL injection",
        file_path="app/views.py",
        start_line=12,
        end_line=18,
        code_excerpt="q = request.GET['q']\nquery = '...' + q\ncursor.execute(query)",
        taint_trace=[
            (12, "request.GET['q']"),
            (14, "query = '...' + q + '...'"),
            (18, "cursor.execute(query)"),
        ],
        sanitizers_observed=[],
    )


class BuildDataflowContextTests(SimpleTestCase):
    def test_picks_first_step_as_source_last_as_sink(self):
        ctx = build_dataflow_context(_sample_finding())
        self.assertEqual(ctx.source_line, 12)
        self.assertEqual(ctx.source_code, "request.GET['q']")
        self.assertEqual(ctx.sink_line, 18)
        self.assertIn("cursor.execute", ctx.sink_code)
        # one intermediate step between source and sink
        self.assertEqual(len(ctx.steps), 1)
        self.assertEqual(ctx.steps[0][0], 14)

    def test_no_trace_falls_back_to_finding_lines(self):
        f = _sample_finding()
        f.taint_trace = []
        ctx = build_dataflow_context(f)
        # When no trace is available, source line = start, sink line = end
        self.assertEqual(ctx.source_line, 12)
        self.assertEqual(ctx.sink_line, 18)
        self.assertEqual(ctx.steps, [])


class NormalizeTests(SimpleTestCase):
    def test_produces_finding_dict_matching_existing_shape(self):
        scan_id = uuid.uuid4().hex
        finding_dict, ctx = normalize(_sample_finding(),
                                     scan_id=scan_id, triggered_by="user-123")
        # All fields the legacy code path populates must be present.
        self.assertEqual(finding_dict["scan_id"], scan_id)
        self.assertEqual(finding_dict["cwe"], "CWE-89")
        self.assertEqual(finding_dict["severity"], "high")        # lowercase, dashboard convention
        self.assertEqual(finding_dict["status"], "open")
        self.assertFalse(finding_dict["deleted"])
        self.assertFalse(finding_dict["approved"])
        self.assertIn("app/views.py", finding_dict["file_path"])
        self.assertIn("[12,18]", finding_dict["file_path"])      # legacy "<file> [start,end]" format
        self.assertEqual(finding_dict["created_by"], "user-123")
        self.assertEqual(finding_dict["lines"], [12, 18])
        self.assertEqual(finding_dict["title"], "Possible SQL injection")
        self.assertTrue(finding_dict["code"].startswith("f-"))     # legacy code id prefix
        # reference link should be built from the CWE number
        self.assertEqual(finding_dict["reference"],
                         "https://cwe.mitre.org/data/definitions/89.html")
        # dataflow context returned alongside the finding dict for the verifier
        self.assertEqual(ctx.sink_line, 18)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd server && .venv/bin/python manage.py test scanner.tests.test_finding_normalizer -v 2`
Expected: FAIL with `ModuleNotFoundError: No module named 'scanner.rag.finding_normalizer'`

- [ ] **Step 3: Implement the normalizer**

Create `server/scanner/rag/finding_normalizer.py`:

```python
"""Translate a SemgrepFinding into the legacy Finding dict + a DataflowContext.

The legacy Finding shape is defined by scanner/rag/extract.py's
extract_relevant_info() — we keep that shape exactly so the DB schema and
the UI keep working unchanged.
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone

from scanner.rag.lsast_types import DataflowContext, SemgrepFinding

# Same vector strings the legacy extractor uses, so the UI renders consistently.
_CVSS_BY_SEVERITY = {
    "critical": ("9.8", "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"),
    "high":     ("8.8", "CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:H/I:H/A:H"),
    "medium":   ("6.5", "CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:L/I:L/A:L"),
    "low":      ("3.1", "CVSS:3.1/AV:L/AC:H/PR:L/UI:R/S:U/C:L/I:N/A:N"),
}


def build_dataflow_context(f: SemgrepFinding) -> DataflowContext:
    """Distil the verifier-ready source/steps/sink view from a Semgrep finding."""
    if not f.taint_trace:
        return DataflowContext(
            source_line=f.start_line, source_code=f.code_excerpt.splitlines()[0] if f.code_excerpt else "",
            sink_line=f.end_line, sink_code=f.code_excerpt.splitlines()[-1] if f.code_excerpt else "",
            steps=[],
            sanitizers_observed=list(f.sanitizers_observed),
        )
    source_line, source_code = f.taint_trace[0]
    sink_line, sink_code = f.taint_trace[-1]
    steps = list(f.taint_trace[1:-1])
    return DataflowContext(
        source_line=source_line, source_code=source_code,
        sink_line=sink_line, sink_code=sink_code,
        steps=steps,
        sanitizers_observed=list(f.sanitizers_observed),
    )


def _cwe_number(cwe: str) -> str:
    m = re.search(r"CWE-(\d+)", cwe or "")
    return m.group(1) if m else ""


def normalize(f: SemgrepFinding, scan_id: str, triggered_by: str) -> tuple[dict, DataflowContext]:
    """Return (legacy_finding_dict, dataflow_context).

    legacy_finding_dict matches the shape that scanner/rag/extract.py emits today
    so save_findings_to_db() and the UI accept it unchanged.
    """
    cvss_score, cvss_vector = _CVSS_BY_SEVERITY.get(f.severity, ("5.0", "CVSS:3.1/AV:L/AC:H/PR:L/UI:N/S:U/C:L/I:L/A:N"))
    num = _cwe_number(f.cwe)
    reference = f"https://cwe.mitre.org/data/definitions/{num}.html" if num else "NA"

    finding = {
        "scan_id": scan_id,
        "cwe": f.cwe or "CWE-Unknown",
        "cvss_vector": cvss_vector,
        "cvss_score": cvss_score,
        "code": "f-" + uuid.uuid4().hex[:8],
        "title": (f.message or f.rule_id or "Vulnerability")[:200],
        "description": f.message[:1000] if f.message else "",
        "severity": f.severity,                           # lowercase already (dashboard convention)
        "file_path": f"{f.file_path} [{f.start_line},{f.end_line}]",
        "code_snip": (f.code_excerpt or "")[:2000],
        "security_risk": f.message[:1000] if f.message else "",
        "mitigation": "",                                  # filled by the verifier later (Phase 2)
        "status": "open",
        "deleted": False,
        "approved": False,
        "reference": reference,
        "created_at": datetime.now(timezone.utc),
        "created_by": triggered_by,
        "lines": [f.start_line, f.end_line],
        "affected": f.rule_id,
    }
    return finding, build_dataflow_context(f)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd server && .venv/bin/python manage.py test scanner.tests.test_finding_normalizer -v 2`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add server/scanner/rag/finding_normalizer.py server/scanner/tests/test_finding_normalizer.py
git commit -m "feat(scanner): normalize SemgrepFinding to legacy Finding dict + DataflowContext"
```

---

## Task 5: LLM verifier

**Files:**
- Create: `server/scanner/rag/llm_verifier.py`
- Create: `server/scanner/tests/test_llm_verifier.py`

- [ ] **Step 1: Write the failing tests**

```python
# server/scanner/tests/test_llm_verifier.py
from unittest import mock

from django.test import SimpleTestCase

from scanner.rag.llm_verifier import build_verifier_prompt, verify
from scanner.rag.lsast_types import DataflowContext, VerifierVerdict


def _ctx() -> DataflowContext:
    return DataflowContext(
        source_line=12, source_code="request.GET['q']",
        sink_line=18, sink_code="cursor.execute(query)",
        steps=[(14, "query = '...' + q + '...'")],
        sanitizers_observed=[],
    )


class BuildVerifierPromptTests(SimpleTestCase):
    def test_includes_cwe_dataflow_and_json_instruction(self):
        prompt = build_verifier_prompt(
            cwe="CWE-89", language="python",
            dataflow=_ctx(),
            code_excerpt="q = request.GET['q']\ncursor.execute(query)",
        )
        self.assertIn("CWE-89", prompt)
        self.assertIn("Source", prompt)
        self.assertIn("Sink", prompt)
        self.assertIn("JSON", prompt)
        self.assertIn('"verdict"', prompt)
        # MUST NOT pre-hint the answer
        self.assertNotIn("Risk indicators detected", prompt)
        # No system-role nor risk priming
        self.assertNotIn("vulnerable", prompt.lower().split("question:")[0])


class VerifyTests(SimpleTestCase):
    def _mock_llm(self, response_text: str):
        client = mock.Mock()
        client.invoke.return_value = {"result": response_text}
        return client

    @mock.patch("scanner.rag.llm_verifier.get_ready_llm")
    def test_returns_TP_verdict_when_model_says_so(self, mock_get):
        mock_get.return_value = self._mock_llm(
            '{"verdict":"TP","reason":"unsanitized input flows to execute","confidence":0.95}'
        )
        v = verify(cwe="CWE-89", language="python",
                   dataflow=_ctx(), code_excerpt="…")
        self.assertEqual(v.verdict, "TP")
        self.assertAlmostEqual(v.confidence, 0.95)

    @mock.patch("scanner.rag.llm_verifier.get_ready_llm")
    def test_returns_FP_verdict(self, mock_get):
        mock_get.return_value = self._mock_llm(
            '{"verdict":"FP","reason":"parameterized query","confidence":0.9}'
        )
        v = verify(cwe="CWE-89", language="python",
                   dataflow=_ctx(), code_excerpt="…")
        self.assertEqual(v.verdict, "FP")

    @mock.patch("scanner.rag.llm_verifier.get_ready_llm")
    def test_strips_code_fences_around_json(self, mock_get):
        mock_get.return_value = self._mock_llm(
            '```json\n{"verdict":"FP","reason":"safe","confidence":0.8}\n```'
        )
        v = verify(cwe="CWE-89", language="python",
                   dataflow=_ctx(), code_excerpt="…")
        self.assertEqual(v.verdict, "FP")

    @mock.patch("scanner.rag.llm_verifier.get_ready_llm")
    def test_fails_open_on_unparseable_response(self, mock_get):
        mock_get.return_value = self._mock_llm("I think this might be vulnerable.")
        v = verify(cwe="CWE-89", language="python",
                   dataflow=_ctx(), code_excerpt="…")
        # Fail-open: return a low-confidence TP rather than dropping the finding
        self.assertEqual(v.verdict, "TP")
        self.assertLess(v.confidence, 0.5)
        self.assertIn("unparseable", v.reason.lower())

    @mock.patch("scanner.rag.llm_verifier.get_ready_llm")
    def test_fails_open_on_llm_exception(self, mock_get):
        client = mock.Mock()
        client.invoke.side_effect = RuntimeError("model busy")
        mock_get.return_value = client
        v = verify(cwe="CWE-89", language="python",
                   dataflow=_ctx(), code_excerpt="…")
        self.assertEqual(v.verdict, "TP")
        self.assertLess(v.confidence, 0.5)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd server && .venv/bin/python manage.py test scanner.tests.test_llm_verifier -v 2`
Expected: FAIL with `ModuleNotFoundError: No module named 'scanner.rag.llm_verifier'`

- [ ] **Step 3: Implement the verifier**

Create `server/scanner/rag/llm_verifier.py`:

```python
"""Constrained LLM verifier.

The LLM never produces a finding from scratch — it judges TP/FP on a Semgrep
finding given the dataflow context. Single turn, no agent loop, no risk hints,
temperature 0 (set by llm.py), forced JSON output, strict parser, fail-open
on parse / call failure.

Why these constraints: deep-research (Xiong & Zhang 2026, arXiv:2601.22952)
showed agentic frameworks regress weaker backbones — for a 3 B model the
safe role is constrained classifier downstream of a deterministic detector
(LSAST pattern, Esposito et al. 2024, arXiv:2409.15735).
"""
from __future__ import annotations

import logging
import re

from scanner.rag.llm import get_ready_llm
from scanner.rag.lsast_types import DataflowContext, VerifierVerdict

logger = logging.getLogger(__name__)


def build_verifier_prompt(*, cwe: str, language: str,
                          dataflow: DataflowContext, code_excerpt: str) -> str:
    """Build the verifier prompt. The dataflow trace is the new signal vs. legacy."""
    cwe = cwe or "an unknown CWE"
    excerpt = code_excerpt[:1800]   # leave room in 4 k ctx for the dataflow + instruction + answer
    return (
        f"A static dataflow analyzer flagged a potential {cwe} finding.\n\n"
        f"Dataflow trace:\n{dataflow.render_for_prompt()}\n\n"
        f"Code excerpt ({language}):\n"
        f"```{language}\n{excerpt}\n```\n\n"
        "QUESTION: Is this finding a TRUE positive or a FALSE positive? Consider whether "
        "any sanitizer / parameterization / ORM / framework-level escaping makes the sink safe.\n\n"
        "Respond with ONLY this JSON object, no prose, no code fences:\n"
        '{"verdict": "TP" | "FP", "reason": "<one short sentence>", "confidence": 0.0-1.0}'
    )


_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)
_JSON_OBJECT_RE = re.compile(r"\{.*?\}", re.DOTALL)


def _extract_json_object(raw: str) -> str:
    """Pull the JSON object out of the model's reply, tolerating code fences / prose."""
    if not raw:
        return ""
    fenced = _JSON_FENCE_RE.search(raw)
    if fenced:
        return fenced.group(1).strip()
    found = _JSON_OBJECT_RE.search(raw)
    return found.group(0).strip() if found else raw.strip()


def verify(*, cwe: str, language: str,
           dataflow: DataflowContext, code_excerpt: str) -> VerifierVerdict:
    """Ask the LLM to classify a Semgrep finding. Returns a VerifierVerdict; never raises.

    Fail-open contract: any failure (LLM exception, unparseable response, missing fields)
    returns a low-confidence TP so the finding is preserved for human review rather
    than silently dropped.
    """
    prompt = build_verifier_prompt(cwe=cwe, language=language,
                                   dataflow=dataflow, code_excerpt=code_excerpt)

    fail_open = VerifierVerdict(verdict="TP",
                                reason="verifier unparseable; preserved for review",
                                confidence=0.3)
    try:
        client = get_ready_llm()
        response = client.invoke({"query": prompt}) or {}
    except Exception as exc:        # pylint: disable=broad-except
        logger.warning("LLM verifier call failed: %s", exc)
        return fail_open

    raw = (response.get("result") or "").strip()
    parsed = VerifierVerdict.from_json(_extract_json_object(raw))
    if parsed is None:
        logger.debug("Verifier response unparseable, failing open. raw=%r", raw[:200])
        return fail_open
    return parsed
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd server && .venv/bin/python manage.py test scanner.tests.test_llm_verifier -v 2`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add server/scanner/rag/llm_verifier.py server/scanner/tests/test_llm_verifier.py
git commit -m "feat(scanner): add constrained LLM verifier (forced JSON, fail-open)"
```

---

## Task 6: Confidence fusion

**Files:**
- Create: `server/scanner/rag/fusion.py`
- Create: `server/scanner/tests/test_fusion.py`

- [ ] **Step 1: Write the failing tests**

```python
# server/scanner/tests/test_fusion.py
from django.test import SimpleTestCase

from scanner.rag.fusion import FusionOutcome, fuse
from scanner.rag.lsast_types import VerifierVerdict


def _finding(severity: str) -> dict:
    return {"severity": severity, "title": "x", "status": "open"}


class FuseTests(SimpleTestCase):
    def test_tp_verdict_shows_finding_with_max_confidence(self):
        outcome = fuse(_finding("high"),
                       VerifierVerdict("TP", "real", 0.7))
        self.assertEqual(outcome.action, "show")
        self.assertGreaterEqual(outcome.finding["confidence"], 0.7)

    def test_fp_on_low_severity_suppresses(self):
        outcome = fuse(_finding("low"),
                       VerifierVerdict("FP", "safe", 0.9))
        self.assertEqual(outcome.action, "suppress")
        self.assertEqual(outcome.finding["status"], "filtered")

    def test_fp_on_medium_severity_suppresses(self):
        outcome = fuse(_finding("medium"),
                       VerifierVerdict("FP", "safe", 0.9))
        self.assertEqual(outcome.action, "suppress")

    def test_fp_on_high_severity_kept_for_review(self):
        outcome = fuse(_finding("high"),
                       VerifierVerdict("FP", "looks safe but…", 0.8))
        self.assertEqual(outcome.action, "needs_review")
        self.assertEqual(outcome.finding["status"], "needs_review")
        # title is annotated so the UI/triagers see the verifier disagreed
        self.assertIn("[verifier:FP]", outcome.finding["title"])

    def test_fp_on_critical_severity_kept_for_review(self):
        outcome = fuse(_finding("critical"),
                       VerifierVerdict("FP", "looks safe", 0.6))
        self.assertEqual(outcome.action, "needs_review")

    def test_failopen_verdict_shows_finding(self):
        outcome = fuse(_finding("medium"),
                       VerifierVerdict("TP", "verifier unparseable; preserved for review", 0.3))
        self.assertEqual(outcome.action, "show")
        self.assertAlmostEqual(outcome.finding["confidence"], 0.3)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd server && .venv/bin/python manage.py test scanner.tests.test_fusion -v 2`
Expected: FAIL with `ModuleNotFoundError: No module named 'scanner.rag.fusion'`

- [ ] **Step 3: Implement the fusion module**

Create `server/scanner/rag/fusion.py`:

```python
"""Combine Semgrep severity + LLM verdict per fixed rules.

Rules (locked in the design spec, §7):

  LLM=TP, any severity                 → show; confidence = max(Semgrep_conf, LLM_conf)
  LLM=FP, severity in {low, medium}    → suppress (status="filtered")
  LLM=FP, severity in {high, critical} → needs_review (never drop a high-sev finding
                                         on a 3 B model's say-so)
  parse failure (already collapsed to fail-open low-conf TP by the verifier) → show
"""
from __future__ import annotations

from dataclasses import dataclass

from scanner.rag.lsast_types import VerifierVerdict

# Severity ranking; severities not listed default to "medium".
_NUMERIC_SEVERITY = {"low": 1, "medium": 2, "high": 3, "critical": 4}

# Semgrep doesn't emit a numeric confidence; treat severity as our proxy.
_SEMGREP_CONFIDENCE_BY_SEVERITY = {"low": 0.5, "medium": 0.7, "high": 0.85, "critical": 0.95}


@dataclass
class FusionOutcome:
    """What to do with a finding after fusion. `finding` is the (possibly annotated) dict."""
    action: str        # "show" | "suppress" | "needs_review"
    finding: dict


def fuse(finding: dict, verdict: VerifierVerdict) -> FusionOutcome:
    sev = (finding.get("severity") or "medium").lower()
    sem_conf = _SEMGREP_CONFIDENCE_BY_SEVERITY.get(sev, 0.7)

    if verdict.verdict == "TP":
        finding["confidence"] = max(sem_conf, verdict.confidence)
        finding["verifier_reason"] = verdict.reason
        return FusionOutcome(action="show", finding=finding)

    # verdict.verdict == "FP"
    if _NUMERIC_SEVERITY.get(sev, 2) >= 3:    # high or critical
        finding["status"] = "needs_review"
        finding["confidence"] = max(sem_conf, verdict.confidence)
        finding["verifier_reason"] = verdict.reason
        finding["title"] = f"[verifier:FP] {finding.get('title', '')}"[:200]
        return FusionOutcome(action="needs_review", finding=finding)

    finding["status"] = "filtered"
    finding["confidence"] = verdict.confidence
    finding["verifier_reason"] = verdict.reason
    return FusionOutcome(action="suppress", finding=finding)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd server && .venv/bin/python manage.py test scanner.tests.test_fusion -v 2`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add server/scanner/rag/fusion.py server/scanner/tests/test_fusion.py
git commit -m "feat(scanner): add confidence fusion (Semgrep severity + LLM verdict)"
```

---

## Task 7: LSAST orchestrator + integration test

**Files:**
- Create: `server/scanner/rag/lsast_scanner.py`
- Create: `server/scanner/tests/test_lsast_scanner.py`

- [ ] **Step 1: Write the failing integration test**

```python
# server/scanner/tests/test_lsast_scanner.py
from unittest import mock

from django.test import SimpleTestCase

from scanner.rag.lsast_scanner import lsast_scan_folder
from scanner.rag.lsast_types import SemgrepFinding, VerifierVerdict


def _sqli_finding() -> SemgrepFinding:
    return SemgrepFinding(
        rule_id="python.lang.security.audit.sql-injection.tainted-sql-string",
        cwe="CWE-89", severity="high",
        message="Possible SQL injection",
        file_path="app/views.py", start_line=12, end_line=18,
        code_excerpt="cursor.execute(query)",
        taint_trace=[(12, "request.GET['q']"), (18, "cursor.execute(query)")],
        sanitizers_observed=[],
    )


def _safe_orm_finding() -> SemgrepFinding:
    return SemgrepFinding(
        rule_id="python.lang.security.audit.sql-injection.tainted-sql-string",
        cwe="CWE-89", severity="medium",
        message="Possible SQL injection",
        file_path="app/views.py", start_line=30, end_line=32,
        code_excerpt="User.objects.filter(name=request.GET['q'])",
        taint_trace=[(30, "request.GET['q']"), (32, "User.objects.filter(name=q)")],
        sanitizers_observed=[],
    )


class LsastScanFolderTests(SimpleTestCase):
    @mock.patch("scanner.rag.lsast_scanner.save_findings_to_db")
    @mock.patch("scanner.rag.lsast_scanner.verify")
    @mock.patch("scanner.rag.lsast_scanner.run_semgrep")
    def test_pipeline_keeps_tp_and_suppresses_medium_fp(self,
                                                        mock_run, mock_verify, mock_save):
        mock_run.return_value = [_sqli_finding(), _safe_orm_finding()]
        mock_verify.side_effect = [
            VerifierVerdict("TP", "unsanitized concat", 0.9),
            VerifierVerdict("FP", "Django ORM parameterizes", 0.95),
        ]
        all_findings, filtered = lsast_scan_folder(
            folder_path="/tmp/code", scan_id="s1", triggered_by="user-1",
        )
        self.assertEqual(len(all_findings), 1)
        self.assertEqual(all_findings[0]["severity"], "high")
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["status"], "filtered")
        # save_findings_to_db is called once with the TP set
        mock_save.assert_called_once()
        saved_arg = mock_save.call_args.args[0]
        self.assertEqual(len(saved_arg), 1)
        self.assertEqual(saved_arg[0]["cwe"], "CWE-89")

    @mock.patch("scanner.rag.lsast_scanner.save_findings_to_db")
    @mock.patch("scanner.rag.lsast_scanner.verify")
    @mock.patch("scanner.rag.lsast_scanner.run_semgrep")
    def test_high_severity_fp_promoted_to_needs_review(self,
                                                       mock_run, mock_verify, mock_save):
        mock_run.return_value = [_sqli_finding()]   # severity "high"
        mock_verify.return_value = VerifierVerdict("FP", "looks safe", 0.7)
        all_findings, filtered = lsast_scan_folder(
            folder_path="/tmp/code", scan_id="s1", triggered_by="user-1",
        )
        self.assertEqual(len(all_findings), 1)
        self.assertEqual(all_findings[0]["status"], "needs_review")
        self.assertEqual(filtered, [])

    @mock.patch("scanner.rag.lsast_scanner.save_findings_to_db")
    @mock.patch("scanner.rag.lsast_scanner.run_semgrep", return_value=[])
    def test_no_findings_short_circuits(self, _run, mock_save):
        all_findings, filtered = lsast_scan_folder("/tmp/code", "s1", "user-1")
        self.assertEqual(all_findings, [])
        self.assertEqual(filtered, [])
        mock_save.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd server && .venv/bin/python manage.py test scanner.tests.test_lsast_scanner -v 2`
Expected: FAIL with `ModuleNotFoundError: No module named 'scanner.rag.lsast_scanner'`

- [ ] **Step 3: Implement the orchestrator**

Create `server/scanner/rag/lsast_scanner.py`:

```python
"""LSAST orchestrator: Semgrep detector → normalizer → verifier → fusion → persist.

Returns (visible_findings, filtered_findings) so the caller can render both,
and persists only the visible/needs_review set via the existing
save_findings_to_db() helper (the legacy file/dashboard surface is unchanged).
"""
from __future__ import annotations

import logging
import os

from scanner.rag.database import save_findings_to_db
from scanner.rag.finding_normalizer import normalize
from scanner.rag.fusion import fuse
from scanner.rag.llm_verifier import verify
from scanner.rag.semgrep_detector import run_semgrep

logger = logging.getLogger(__name__)


def _language_from_path(file_path: str) -> str:
    ext = os.path.splitext(file_path)[1].lstrip(".").lower()
    return {
        "py": "python", "js": "javascript", "ts": "typescript", "tsx": "typescript",
        "jsx": "javascript", "java": "java", "go": "go", "rb": "ruby",
        "php": "php", "cs": "csharp", "c": "c", "cc": "cpp", "cpp": "cpp",
        "rs": "rust",
    }.get(ext, ext or "text")


def lsast_scan_folder(folder_path: str, scan_id: str, triggered_by: str
                      ) -> tuple[list[dict], list[dict]]:
    """Run the full LSAST pipeline. Returns (visible, filtered)."""
    sem_findings = run_semgrep(folder_path)
    if not sem_findings:
        logger.info("LSAST: Semgrep produced no findings for %s", folder_path)
        return [], []

    visible: list[dict] = []
    filtered: list[dict] = []

    for sf in sem_findings:
        finding_dict, dataflow = normalize(sf, scan_id=scan_id, triggered_by=triggered_by)
        verdict = verify(
            cwe=sf.cwe,
            language=_language_from_path(sf.file_path),
            dataflow=dataflow,
            code_excerpt=sf.code_excerpt,
        )
        outcome = fuse(finding_dict, verdict)
        if outcome.action == "suppress":
            filtered.append(outcome.finding)
        else:
            visible.append(outcome.finding)

    if visible:
        save_findings_to_db(visible)

    logger.info(
        "LSAST done: %d Semgrep → %d visible (%d needs_review) + %d filtered",
        len(sem_findings),
        len(visible),
        sum(1 for f in visible if f.get("status") == "needs_review"),
        len(filtered),
    )
    return visible, filtered
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd server && .venv/bin/python manage.py test scanner.tests.test_lsast_scanner -v 2`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add server/scanner/rag/lsast_scanner.py server/scanner/tests/test_lsast_scanner.py
git commit -m "feat(scanner): add LSAST orchestrator (Semgrep → normalize → verify → fuse → persist)"
```

---

## Task 8: Feature-flag wire-up in `scanner.py`

**Files:**
- Modify: `server/scanner/rag/scanner.py`
- Create: `server/scanner/tests/test_scanner_flag.py`

- [ ] **Step 1: Write the failing test**

```python
# server/scanner/tests/test_scanner_flag.py
import os
from unittest import mock

from django.test import SimpleTestCase

import scanner.rag.scanner as scanner_module


class ScannerFeatureFlagTests(SimpleTestCase):
    @mock.patch.object(scanner_module, "lsast_scan_folder", return_value=(["v"], ["f"]))
    @mock.patch.object(scanner_module, "_legacy_scan_folder")
    def test_lsast_engine_routes_to_lsast_scan(self, mock_legacy, mock_lsast):
        with mock.patch.dict(os.environ, {"SCAN_ENGINE": "lsast"}, clear=False):
            scanner_module.scan_folder("/x", "s1", "user-1", "Scan #1")
        mock_lsast.assert_called_once()
        mock_legacy.assert_not_called()

    @mock.patch.object(scanner_module, "lsast_scan_folder")
    @mock.patch.object(scanner_module, "_legacy_scan_folder", return_value=[])
    def test_legacy_engine_routes_to_legacy_scan(self, mock_legacy, mock_lsast):
        with mock.patch.dict(os.environ, {"SCAN_ENGINE": "legacy"}, clear=False):
            scanner_module.scan_folder("/x", "s1", "user-1", "Scan #1")
        mock_legacy.assert_called_once()
        mock_lsast.assert_not_called()

    @mock.patch.object(scanner_module, "lsast_scan_folder")
    @mock.patch.object(scanner_module, "_legacy_scan_folder", return_value=[])
    def test_default_engine_is_legacy(self, mock_legacy, mock_lsast):
        with mock.patch.dict(os.environ, {"SCAN_ENGINE": ""}, clear=False):
            scanner_module.scan_folder("/x", "s1", "user-1", "Scan #1")
        mock_legacy.assert_called_once()
        mock_lsast.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd server && .venv/bin/python manage.py test scanner.tests.test_scanner_flag -v 2`
Expected: FAIL — `AttributeError: ... _legacy_scan_folder` (we haven't renamed yet)

- [ ] **Step 3: Modify `scanner.py` to add the feature flag**

In `server/scanner/rag/scanner.py`:

1. At the top of the file, add the imports:

```python
import os
from .lsast_scanner import lsast_scan_folder
```

2. Rename the existing `scan_folder` function to `_legacy_scan_folder` (it keeps its current body — DO NOT change the body, just rename the `def` line and any internal recursive references; there are none).

3. Add a new dispatching `scan_folder` after the rename. Place it ABOVE `_legacy_scan_folder` for readability:

```python
def scan_folder(folder_path, scan_id, triggered_by, scan_name):
    """Route to the LSAST or legacy engine based on the SCAN_ENGINE env var.

    SCAN_ENGINE=lsast  → Semgrep + LLM verifier (Phase 1 of the SAST redesign)
    SCAN_ENGINE=legacy → original LLM-primary scanner (default during Phase 1)
    """
    engine = (os.environ.get("SCAN_ENGINE") or "legacy").strip().lower()
    if engine == "lsast":
        logger.info("scan_folder: routing to LSAST engine")
        # LSAST returns (visible, filtered); the legacy contract returns visible only.
        visible, _filtered = lsast_scan_folder(folder_path, scan_id, triggered_by)
        return visible
    logger.info("scan_folder: routing to legacy engine")
    return _legacy_scan_folder(folder_path, scan_id, triggered_by, scan_name)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd server && .venv/bin/python manage.py test scanner.tests.test_scanner_flag -v 2`
Expected: PASS (3 tests)

Run the full scanner test suite to confirm no regressions:
Run: `cd server && .venv/bin/python manage.py test scanner -v 2`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add server/scanner/rag/scanner.py server/scanner/tests/test_scanner_flag.py
git commit -m "feat(scanner): add SCAN_ENGINE feature flag (lsast | legacy), default legacy"
```

---

## Task 9: Stage Semgrep + rule packs into the build

**Files:**
- Modify: `scripts/offline_sbom/fetch_offline_tools.sh` — fetch Semgrep release binary alongside syft/grype
- Modify: `scripts/build_macos.sh` — also fetch + bundle rule packs into `resources/semgrep-rules/`
- Modify: `client/src-tauri/src/main.rs` — export `SEMGREP_BIN` + `SEMGREP_RULES_DIR` to the backend
- Create: `server/scanner/tests/test_bundle_smoke.py` — env-var sanity test

- [ ] **Step 1: Add a smoke test that env vars wire through**

```python
# server/scanner/tests/test_bundle_smoke.py
import os
from unittest import mock

from django.test import SimpleTestCase

from scanner.services.tools import get_semgrep_bin, get_semgrep_rules_dir


class BundleEnvVarSmokeTests(SimpleTestCase):
    def test_semgrep_env_wiring_is_picked_up(self):
        with mock.patch.dict(os.environ,
                             {"SEMGREP_BIN": "/fake/sem",
                              "SEMGREP_RULES_DIR": "/fake/rules"}, clear=False):
            self.assertEqual(get_semgrep_bin(), "/fake/sem")
            self.assertEqual(get_semgrep_rules_dir(), "/fake/rules")
```

Run: `cd server && .venv/bin/python manage.py test scanner.tests.test_bundle_smoke -v 2`
Expected: PASS (the resolver was already implemented in Task 2)

- [ ] **Step 2: Extend `fetch_offline_tools.sh` to fetch Semgrep**

Open `scripts/offline_sbom/fetch_offline_tools.sh` and append AFTER the cosign block:

```bash
# ------------- Semgrep (SAST detector) -------------
# We use OpenGrep, the OSS fork of Semgrep that ships single-file static binaries.
# Same query language and rule packs; the wrapper calls it as `semgrep` for symmetry
# with the bundled binary name expected by SEMGREP_BIN.
OPENGREP_VERSION="${OPENGREP_VERSION:-1.4.0}"
case "$TARGET_OS" in
  darwin)  OG_OS="osx" ;;
  linux)   OG_OS="manylinux" ;;
  windows) OG_OS="win32" ;;
esac
case "$TARGET_ARCH" in
  arm64) OG_ARCH="arm64" ;;
  amd64) OG_ARCH="x86_64" ;;
esac
echo "Fetching OpenGrep $OPENGREP_VERSION ($OG_OS/$OG_ARCH) ..."
OG_NAME="opengrep_${OG_OS}_${OG_ARCH}"
dl "https://github.com/opengrep/opengrep/releases/download/v${OPENGREP_VERSION}/${OG_NAME}${ext}" \
   "$OUT/semgrep${ext}"
chmod +x "$OUT/semgrep${ext}" 2>/dev/null || true
echo "  staged: $OUT/semgrep${ext}"
```

(If the URL pattern doesn't match a given OpenGrep release at execute time, the engineer should consult `https://github.com/opengrep/opengrep/releases` and adjust the `${OG_NAME}` template — this is the only failure mode and is easy to spot from the curl output.)

- [ ] **Step 3: Add a rules-fetch step to `scripts/build_macos.sh`**

Open `scripts/build_macos.sh` and add a new step 5b (after the Grype DB snapshot, before icons):

```bash
# --------------------------------------------------------------------------- #
# 5b. Semgrep rule packs (offline)
# --------------------------------------------------------------------------- #
info "Bundling Semgrep rule packs"
RULES_DIR="$TAURI/resources/semgrep-rules"
mkdir -p "$RULES_DIR"
if [ -x "$RES_TOOLS/semgrep" ]; then
  for pack in p/security-audit p/owasp-top-ten p/secrets \
              p/python p/javascript p/typescript p/java p/golang; do
    pack_dir="$RULES_DIR/$(echo "$pack" | tr '/' '_')"
    mkdir -p "$pack_dir"
    # `semgrep --dump-config <pack>` writes the full YAML rule set to stdout.
    "$RES_TOOLS/semgrep" --dump-config="$pack" > "$pack_dir/rules.yml" 2> /dev/null \
      || echo "    WARNING: could not dump $pack (may need first-time network sync)"
  done
  ok "Semgrep rule packs staged in $RULES_DIR"
else
  echo "    WARNING: $RES_TOOLS/semgrep not found; skipping rule packs."
  echo "             Re-run fetch_offline_tools.sh first."
fi
```

- [ ] **Step 4: Wire the env vars into the Tauri shell**

Open `client/src-tauri/src/main.rs`. In the `spawn_backend` function, find the chain of `.env(...)` calls and add two more, right after the `GRYPE_DB_CACHE_DIR` env line:

```rust
        .env("SEMGREP_BIN",        tools_dir.join("semgrep").to_string_lossy().to_string())
        .env("SEMGREP_RULES_DIR",  app
            .path()
            .resolve("resources/semgrep-rules", BaseDirectory::Resource)
            .unwrap_or_default()
            .to_string_lossy()
            .to_string())
```

- [ ] **Step 5: Run the unit-test suite to confirm no regressions**

Run: `cd server && .venv/bin/python manage.py test scanner -v 2`
Expected: PASS

Also `bash -n` the modified shell scripts:

```bash
bash -n scripts/offline_sbom/fetch_offline_tools.sh && bash -n scripts/build_macos.sh && echo "shell syntax OK"
```

- [ ] **Step 6: Commit**

```bash
git add scripts/offline_sbom/fetch_offline_tools.sh \
        scripts/build_macos.sh \
        client/src-tauri/src/main.rs \
        server/scanner/tests/test_bundle_smoke.py
git commit -m "feat(build): bundle Semgrep/OpenGrep + rule packs; export SEMGREP_BIN/RULES_DIR to backend"
```

---

## Task 10: End-to-end manual smoke test (no code changes, executable validation)

**Files:** none — runs against the existing dev env.

- [ ] **Step 1: Install Semgrep into the dev venv (one-time, local dev only)**

```bash
cd server && .venv/bin/pip install semgrep
.venv/bin/semgrep --version
```

(Production installs use the bundled OpenGrep binary; pip install is just for the dev loop.)

- [ ] **Step 2: Build a tiny vulnerable + safe sample**

Create `/tmp/lsast_sample/views.py`:

```python
# /tmp/lsast_sample/views.py
import sqlite3

def search_unsafe(request, db: sqlite3.Connection):
    q = request.GET["q"]
    cursor = db.cursor()
    query = "SELECT * FROM users WHERE name = '" + q + "'"
    cursor.execute(query)
    return cursor.fetchall()

def search_safe(request, db: sqlite3.Connection):
    q = request.GET["q"]
    cursor = db.cursor()
    cursor.execute("SELECT * FROM users WHERE name = ?", (q,))
    return cursor.fetchall()
```

- [ ] **Step 3: Smoke-run Semgrep alone (sanity check the rule packs work)**

```bash
.venv/bin/semgrep --config p/security-audit --config p/owasp-top-ten --json /tmp/lsast_sample \
  | python3 -c "import sys,json;d=json.load(sys.stdin);print('findings:',len(d.get('results',[]))); \
                [print(r['check_id'], r['path'], r['start']['line']) for r in d.get('results', [])]"
```

Expected: at least one finding pointing at `views.py` line ~7 (the unsafe one); ideally none on the parameterized safe one.

- [ ] **Step 4: Smoke-run the LSAST orchestrator with a stubbed verifier**

```bash
cd server
SCAN_ENGINE=lsast SEMGREP_BIN="$(pwd)/.venv/bin/semgrep" SEMGREP_RULES_DIR="" \
  .venv/bin/python -c "
from unittest import mock
import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE','codesense.settings')
django.setup()
from scanner.rag.lsast_scanner import lsast_scan_folder
from scanner.rag.lsast_types import VerifierVerdict
# Stub verifier to avoid needing a running llama-server during smoke.
with mock.patch('scanner.rag.lsast_scanner.verify',
                side_effect=[VerifierVerdict('TP','unsanitized concat',0.9),
                             VerifierVerdict('FP','parameterized query',0.95)]):
    with mock.patch('scanner.rag.lsast_scanner.save_findings_to_db'):
        visible, filtered = lsast_scan_folder('/tmp/lsast_sample','s-smoke','dev')
        print('visible:', len(visible), 'filtered:', len(filtered))
        for v in visible: print(' V', v['cwe'], v['title'][:60], v['file_path'])
        for f in filtered: print(' F', f['cwe'], f['title'][:60], f['file_path'])
"
```

Expected: 1 visible (the unsafe SQL injection, severity high), 1 filtered (the parameterized query the verifier called FP — IF Semgrep actually flagged it; if not, you'll see 1 visible / 0 filtered, which is also fine for the smoke).

- [ ] **Step 5: Smoke against the real LLM (only if llama-server is up on :8001)**

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8001/v1/models
# If 200, drop the verify-mock from step 4 and re-run. The real verifier should
# (a) return parseable JSON, (b) call the parameterized query FP. If not, capture
# the raw response into a fixture and tune the prompt in llm_verifier.build_verifier_prompt.
```

- [ ] **Step 6: Commit (only if any tuning was needed in the previous steps)**

If you tuned the prompt or rule packs during the smoke:

```bash
git add -p server/scanner/rag/llm_verifier.py scripts/build_macos.sh
git commit -m "tune(scanner): adjust LSAST prompt/rule packs after smoke against real LLM"
```

---

## Self-review checklist (the writer of this plan ran these against the spec)

**Spec coverage:**

| Spec §                          | Implemented in task(s) |
|---------------------------------|------------------------|
| §2 LSAST architecture decision  | 7 (orchestrator) routes the pipeline                                        |
| §3 Locked decisions             | 8 (feature flag), 9 (offline bundle), 5 (single-turn classifier, temp 0)    |
| §4 Architecture diagram         | 1–7 implement each box; 8 wires the routing                                 |
| §5 Component table              | One task per row in the table                                               |
| §6 Prompt change                | 5 (`build_verifier_prompt`) — test asserts no "Risk indicators detected"    |
| §7 Fusion rules table           | 6 (`fuse`) — one test per row                                               |
| §8 Bundle & deployment          | 9 (build scripts + Tauri env wire-up)                                       |
| §9 Acceptance criteria          | **Phase 2** plan (eval harness) — explicitly out of scope here              |
| §10 Phased rollout: Phase 1     | this plan                                                                   |
| §11 Risks: fail-open verifier   | 5 (`verify` returns low-conf TP on parse/exception)                         |
| §11 Risks: never silently drop  | 6 (`fuse` keeps high/critical FPs as needs_review)                          |

**Placeholder scan:** no "TBD" / "TODO" / "add tests for the above" — every step contains the actual code or command.

**Type consistency:** `SemgrepFinding`, `DataflowContext`, `VerifierVerdict` are defined once (Task 1) and used by the same names in Tasks 3, 4, 5, 6, 7. The legacy `Finding` dict shape is preserved by `normalize()` (Task 4) so `save_findings_to_db()` (existing) accepts it unchanged. `lsast_scan_folder` returns `(visible, filtered)` consistently in Tasks 7 and 8.

**Scope:** Phase 1 only. Phase 2 (eval harness, OWASP Benchmark / Juliet runs, CI gate) and Phase 3 (UI FP-feedback loop, suppression file) are explicitly deferred to subsequent plans.

---

## Plan complete

Plan saved to `docs/superpowers/plans/2026-05-29-sast-accuracy-lsast-phase1.md`. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration with the per-task TDD loop.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints for review.

**Which approach?**
