# Code Sense Roadmap — Phase 1 Plan (Weeks 1–5): Stabilize + Model Swap

> **For agentic workers:** REQUIRED SUB-SKILL: use superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Lock current behavior with characterization tests + a baseline scorecard, then swap the
non-commercial FIM model for an Apache-licensed instruction-tuned model with a de-FIM'd client and
grammar-constrained JSON, so the verifier discriminates TP/FP and enrichment parses reliably.

**Architecture:** All model work is gated by a `LLM_MODEL_MODE` env (`fim` default = unchanged legacy
behavior; `instruct` = new path) so it's backward-compatible. The detector/normalizer are NOT touched —
characterization tests (W1) lock them. Served by the existing `llama-server`; one ChatML code path.

**Tech Stack:** Python 3.13 / Django (server), `server/.venv`, llama.cpp `llama-server`, Semgrep/OpenGrep,
the `scripts/eval/` harness. Run tests with `cd server && .venv/bin/python manage.py test scanner`.

**Spec:** `docs/superpowers/specs/2026-05-31-codesense-12week-roadmap-design.md`.

---

## Week 1 — Baselines + characterization lock

**Session goal:** establish the balanced scorecard with real numbers, and pin current
detector/normalizer/CWE behavior so later weeks can't silently regress it.
**Acceptance test:** `metrics/scorecard.md` committed with a value (or `N/A — established W#`) for every row;
`server/scanner/tests/test_characterization.py` green and pinned.

### Task 1.1: Characterization fixture + snapshot test (lock detector→normalize→derive_cwe)

**Files:**
- Create: `server/scanner/tests/fixtures/characterization/app.py`
- Create: `server/scanner/tests/fixtures/characterization/Dockerfile`
- Create: `server/scanner/tests/test_characterization.py`

- [ ] **Step 1: Create the fixture code** (two tiny files that the bundled rules flag deterministically)

`server/scanner/tests/fixtures/characterization/app.py`:
```python
import sqlite3
def handler(request):
    q = request.GET["q"]
    conn = sqlite3.connect("db")
    conn.execute("SELECT * FROM users WHERE name = '" + q + "'")  # tainted concat
```

`server/scanner/tests/fixtures/characterization/Dockerfile`:
```dockerfile
FROM python:3.11
COPY . /app
CMD ["python", "/app/app.py"]
```

- [ ] **Step 2: Write the failing characterization test**

`server/scanner/tests/test_characterization.py`:
```python
import os
import unittest
from pathlib import Path

from django.test import SimpleTestCase

from scanner.rag.semgrep_detector import run_semgrep
from scanner.rag.finding_normalizer import normalize

FIXTURE_DIR = str(Path(__file__).parent / "fixtures" / "characterization")
_HAVE_ENGINE = bool(os.getenv("SEMGREP_BIN")) and bool(os.getenv("SEMGREP_RULES_DIR"))


@unittest.skipUnless(_HAVE_ENGINE, "set SEMGREP_BIN + SEMGREP_RULES_DIR to run characterization")
class DetectorCharacterizationTests(SimpleTestCase):
    """Pins current detection behavior on a fixed fixture so the model/UX work
    in later weeks cannot silently change what the DETECTOR produces."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.findings = run_semgrep(FIXTURE_DIR)

    def test_detects_the_sqli_and_dockerfile_issues(self):
        titles = sorted({normalize(f, "s", "u")[0]["title"] for f in self.findings})
        # snapshot: at least the SQLi rule fires; titles are rule names (not prose)
        self.assertTrue(any("sql" in t.lower() for t in titles), titles)
        self.assertTrue(all(" " not in t for t in titles), f"titles must be rule slugs: {titles}")

    def test_every_finding_has_a_derived_cwe(self):
        cwes = {(f.cwe or "CWE-Unknown") for f in self.findings}
        self.assertNotIn("CWE-Unknown", cwes, f"derive_cwe regressed: {cwes}")
```

- [ ] **Step 3: Run it and confirm it passes with the engine env set**

Run:
```bash
cd server && SEMGREP_BIN="$PWD/.venv/bin/semgrep" \
  SEMGREP_RULES_DIR="/Applications/Code Sense.app/Contents/Resources/resources/semgrep-rules" \
  .venv/bin/python manage.py test scanner.tests.test_characterization -v 2
```
Expected: `OK` (2 tests). Without the env it reports `skipped` — that's fine for CI-without-engine.

- [ ] **Step 4: Commit**
```bash
git add server/scanner/tests/test_characterization.py server/scanner/tests/fixtures/characterization
git commit -m "test(lsast): characterization lock for detector→normalize→cwe"
```

### Task 1.2: Scorecard script + baseline doc

**Files:**
- Create: `scripts/eval/scorecard.py`
- Create: `metrics/scorecard.md`
- Test: `scripts/eval/tests/test_scorecard.py`

- [ ] **Step 1: Write the failing test for the markdown formatter**

`scripts/eval/tests/test_scorecard.py`:
```python
from scorecard import render_scorecard

def test_render_scorecard_has_all_axes():
    md = render_scorecard({
        "detector_f1": 1.0, "verifier_fp_suppression": 0.0,
        "enrichment_parse_rate": 0.34, "scan_wall_s_p50": 540.0,
        "build_signed_ok": False, "app_size_gb": 5.7,
    })
    for label in ("Detector F1", "Verifier FP-suppression", "Enrichment parse-rate",
                  "Scan wall-time", "Signed build", "App size"):
        assert label in md
    assert "0.34" in md
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd scripts/eval && PYTHONPATH=. python3 -m pytest tests/test_scorecard.py -v`
Expected: FAIL (`ModuleNotFoundError: scorecard` / `render_scorecard`).

- [ ] **Step 3: Implement `scripts/eval/scorecard.py`**
```python
"""Render the balanced scorecard (accuracy + perf + packaging) as markdown.

Values are passed in (measured elsewhere); this module only formats + diffs, so
it's unit-testable without an engine/LLM. Missing keys render as 'N/A'."""
from __future__ import annotations

_ROWS = [
    ("Detector F1", "detector_f1", "{:.3f}"),
    ("Detector FP-rate", "detector_fp_rate", "{:.3f}"),
    ("Verifier FP-suppression", "verifier_fp_suppression", "{:.3f}"),
    ("Verifier Tier-2 F1", "verifier_f1", "{:.3f}"),
    ("Enrichment parse-rate", "enrichment_parse_rate", "{:.2f}"),
    ("Scan wall-time (p50, s)", "scan_wall_s_p50", "{:.0f}"),
    ("Per-finding LLM latency (s)", "llm_latency_s", "{:.1f}"),
    ("Signed build OK", "build_signed_ok", "{}"),
    ("App size (GB)", "app_size_gb", "{:.1f}"),
]


def render_scorecard(values: dict, *, title: str = "Scorecard") -> str:
    lines = [f"## {title}", "", "| Metric | Value |", "|---|---|"]
    for label, key, fmt in _ROWS:
        v = values.get(key)
        cell = "N/A" if v is None else fmt.format(v)
        lines.append(f"| {label} | {cell} |")
    return "\n".join(lines) + "\n"
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd scripts/eval && PYTHONPATH=. python3 -m pytest tests/test_scorecard.py -v`
Expected: PASS.

- [ ] **Step 5: Measure the baseline and write `metrics/scorecard.md`**

Run the detector tier + capture numbers (use real values; where a measurement needs llama-server/eval data
you don't have yet, record `N/A — established W#`):
```bash
cd scripts/eval && PYTHONPATH=../../server \
  SEMGREP_BIN=../../server/.venv/bin/semgrep \
  SEMGREP_RULES_DIR="/Applications/Code Sense.app/Contents/Resources/resources/semgrep-rules" \
  ../../server/.venv/bin/python run_eval.py --dataset curated --tier detector
```
Then hand-write `metrics/scorecard.md` with a "Baseline (W1)" section: detector F1/FP from that run;
`verifier_fp_suppression = 0.000` and `enrichment_parse_rate = 0.34` (from this session's audits);
`scan_wall_s_p50 ≈ 540` (DVB, ~9 min); `build_signed_ok = false`; `app_size_gb = 5.7`.

- [ ] **Step 6: Commit**
```bash
git add scripts/eval/scorecard.py scripts/eval/tests/test_scorecard.py metrics/scorecard.md
git commit -m "feat(eval): scorecard renderer + W1 baseline metrics"
```

### Task 1.3: End-of-session handoff
- [ ] Update `CLAUDE.md` with: "W1 done — characterization tests lock the detector; baseline in
  `metrics/scorecard.md`." Append a **Next-week brief** for W2 (below). Commit:
  `git commit -am "docs: W1 wrap + W2 brief"`.

> **W2 brief:** convert `Qwen/Qwen2.5-Coder-7B-Instruct` (Apache) to GGUF Q4_K_M via
> `scripts/offline_ai/convert_model_to_gguf.sh`; add `LLM_MODEL_MODE` env to `server/scanner/rag/llm.py`
> (default `fim`); the new model is selected by config but the FIM path stays default. Goal: instruct model
> *loads + serves* behind the flag; legacy unchanged.

---

## Week 2 — License-safe model, converted + bundled behind a flag

**Session goal:** an Apache-licensed instruct model converts to GGUF, is selectable behind a flag, loads,
and serves — with legacy (FIM) behavior unchanged when the flag is off.
**Acceptance test:** with `LLM_MODEL_MODE=instruct` + the instruct GGUF, an integration test does a chat
round-trip; with the default, `test_semgrep_detector`/verifier tests are unchanged. **Milestone: compliance blocker resolved.**

### Task 2.1: Add the model-mode flag to the LLM client (no behavior change yet)

**Files:**
- Modify: `server/scanner/rag/llm.py`
- Test: `server/scanner/tests/test_llm_mode.py`

- [ ] **Step 1: Write the failing test**

`server/scanner/tests/test_llm_mode.py`:
```python
import os
from unittest import mock
from django.test import SimpleTestCase
from scanner.rag.llm import VLLMClient, model_mode


class ModelModeTests(SimpleTestCase):
    def test_defaults_to_fim(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("LLM_MODEL_MODE", None)
            self.assertEqual(model_mode(), "fim")

    def test_instruct_when_set(self):
        with mock.patch.dict(os.environ, {"LLM_MODEL_MODE": "instruct"}):
            self.assertEqual(model_mode(), "instruct")
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd server && .venv/bin/python manage.py test scanner.tests.test_llm_mode -v 2`
Expected: FAIL (`cannot import name 'model_mode'`).

- [ ] **Step 3: Add `model_mode()` to `server/scanner/rag/llm.py`** (near the top, after imports)
```python
def model_mode() -> str:
    """'instruct' (instruction-tuned, JSON-following) or 'fim' (legacy FIM model)."""
    return "instruct" if os.getenv("LLM_MODEL_MODE", "fim").lower() == "instruct" else "fim"
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd server && .venv/bin/python manage.py test scanner.tests.test_llm_mode -v 2`
Expected: PASS.

- [ ] **Step 5: Commit**
```bash
git add server/scanner/rag/llm.py server/scanner/tests/test_llm_mode.py
git commit -m "feat(llm): add LLM_MODEL_MODE flag (default fim, no behavior change)"
```

### Task 2.2: Convert + verify the Apache instruct GGUF (build-host task, documented + scripted)

**Files:**
- Modify: `scripts/offline_ai/convert_model_to_gguf.sh` (only the header docs — it already takes `MODEL_SRC`)
- Create: `scripts/offline_ai/README-model-swap.md`

- [ ] **Step 1: Document + run the conversion** (networked build host; needs a llama.cpp checkout)
```bash
# download HF weights once (build host only):
huggingface-cli download Qwen/Qwen2.5-Coder-7B-Instruct --local-dir /tmp/qwen7b-instruct
LLAMA_CPP=~/llama.cpp QUANT=Q4_K_M \
  scripts/offline_ai/convert_model_to_gguf.sh /tmp/qwen7b-instruct dist/model
# -> dist/model/astra-Q4_K_M.gguf  (~4.7 GB)
```

- [ ] **Step 2: Verify it loads + serves** (the acceptance check)
```bash
/path/to/llama-server --model dist/model/astra-Q4_K_M.gguf --host 127.0.0.1 --port 8001 \
  --ctx-size 4096 --alias astra-code-reviewer --api-key EMPTY &
curl -s http://127.0.0.1:8001/v1/models | python3 -c "import sys,json;print(json.load(sys.stdin)['data'][0]['id'])"
```
Expected: prints the model id; the GGUF metadata `general.name` contains "Qwen2.5-Coder-7B-Instruct" and
the license is Apache-2.0 (verify on the HF card).

- [ ] **Step 3: Write `scripts/offline_ai/README-model-swap.md`** documenting the above + the per-tier
  variants (1.5B Q5_K_M / 7B Q4_K_M / 14B Q4_K_M) and that the build stages the chosen GGUF as
  `resources/model/astra.gguf`.

- [ ] **Step 4: Commit**
```bash
git add scripts/offline_ai/convert_model_to_gguf.sh scripts/offline_ai/README-model-swap.md
git commit -m "docs(model): instruct-model conversion + bundling steps"
```

### Task 2.3: Integration round-trip test (gated; run when the instruct server is up)

**Files:** Create `server/scanner/tests/test_llm_integration.py`
- [ ] **Step 1: Write the gated test**
```python
import os, unittest
from django.test import SimpleTestCase
from scanner.rag.llm import get_ready_llm

_LIVE = os.getenv("LLM_LIVE_TEST") == "1"

@unittest.skipUnless(_LIVE, "set LLM_LIVE_TEST=1 with a running llama-server")
class LlmRoundTripTests(SimpleTestCase):
    def test_chat_roundtrip_returns_text(self):
        client = get_ready_llm(force_healthcheck=True)
        out = client.invoke({"query": 'Reply with the single word: ok'}) or {}
        self.assertTrue((out.get("result") or "").strip())
```
- [ ] **Step 2: Run with the instruct server up**
Run: `cd server && LLM_LIVE_TEST=1 LLM_MODEL_MODE=instruct VLLM_BASE_URL=http://127.0.0.1:8001/v1 .venv/bin/python manage.py test scanner.tests.test_llm_integration -v 2`
Expected: PASS (non-empty reply). Without `LLM_LIVE_TEST=1`: skipped.
- [ ] **Step 3: Commit** `git add -A && git commit -m "test(llm): gated chat round-trip integration test"`

### Task 2.4: Handoff
- [ ] Update `CLAUDE.md` (W2 done; instruct model loads behind `LLM_MODEL_MODE=instruct`). Write the W3 brief. Commit.

> **W3 brief:** in `llm.py`, gate the FIM hacks on `model_mode()`: in `instruct` mode skip `_STOP_TOKENS` +
> the `_clean_output` "Vulnerability:" hunting, send a system message, and add `response_format` to the
> request body. Then verify the A/B (`/tmp/verifier_ab.py`): safe→FP, unsafe→TP.

---

## Week 3 — De-FIM the client + grammar-constrained JSON

**Session goal:** in instruct mode the client sends clean chat (system+user), forces JSON, and does NOT
apply FIM output-mangling. **Acceptance test:** the verifier A/B returns `FP` for a safe parameterized query
and `TP` for unsafe concat; JSON parse-rate ≈100% on the probe set.

### Task 3.1: Gate `_clean_output` + stop tokens + add system prompt & response_format

**Files:** Modify `server/scanner/rag/llm.py`; Test `server/scanner/tests/test_llm_instruct.py`

- [ ] **Step 1: Write the failing test** (instruct mode changes the request body)
```python
import os
from unittest import mock
from django.test import SimpleTestCase
from scanner.rag import llm as llmmod
from scanner.rag.llm import VLLMClient

class InstructRequestTests(SimpleTestCase):
    @mock.patch.dict(os.environ, {"LLM_MODEL_MODE": "instruct"})
    @mock.patch("scanner.rag.llm.requests.post")
    def test_instruct_sends_system_msg_json_format_and_no_fim_stops(self, mock_post):
        mock_post.return_value = mock.Mock(status_code=200,
            json=lambda: {"choices": [{"message": {"content": '{"ok": true}'}}]})
        c = VLLMClient()
        c.invoke({"query": "hi", "response_format": {"type": "json_object"}})
        body = mock_post.call_args.kwargs["json"]
        roles = [m["role"] for m in body["messages"]]
        self.assertIn("system", roles)
        self.assertEqual(body.get("response_format"), {"type": "json_object"})
        self.assertNotIn("<|fim_middle|>", body.get("stop", []))

    @mock.patch.dict(os.environ, {"LLM_MODEL_MODE": "instruct"})
    def test_instruct_clean_output_is_passthrough(self):
        c = VLLMClient()
        self.assertEqual(c._clean_output('{"verdict":"FP"}'), '{"verdict":"FP"}')
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd server && .venv/bin/python manage.py test scanner.tests.test_llm_instruct -v 2`
Expected: FAIL (instruct branch not implemented).

- [ ] **Step 3: Implement the instruct branch in `VLLMClient`**

In `_clean_output`, short-circuit for instruct mode (add as the first lines):
```python
        if model_mode() == "instruct":
            return (content or "").strip()
```
In `invoke`, build the body conditionally on mode:
```python
        is_instruct = model_mode() == "instruct"
        messages = []
        if is_instruct:
            messages.append({"role": "system",
                             "content": "You are a security analysis assistant. Respond with only valid JSON."})
        messages.append({"role": "user", "content": prompt})
        body = {
            "model": self.model, "temperature": self.temperature,
            "max_tokens": safe_max, "messages": messages,
        }
        if is_instruct:
            rf = payload.get("response_format")
            if rf:
                body["response_format"] = rf
        else:
            body["stop"] = _STOP_TOKENS
```
(Replace the existing single-`body` construction; keep the retry/400 handling around it.)

- [ ] **Step 4: Run to verify it passes**

Run: `cd server && .venv/bin/python manage.py test scanner.tests.test_llm_instruct scanner.tests.test_semgrep_detector -v 2`
Expected: PASS (and the legacy detector/verifier tests still pass — fim path unchanged).

- [ ] **Step 5: Commit**
```bash
git add server/scanner/rag/llm.py server/scanner/tests/test_llm_instruct.py
git commit -m "feat(llm): instruct mode — system prompt, JSON response_format, no FIM mangling"
```

### Task 3.2: Pass `response_format` from the verifier + enricher

**Files:** Modify `server/scanner/rag/llm_verifier.py`, `server/scanner/rag/report_enricher.py`
- [ ] **Step 1:** In `llm_verifier.verify`, change the invoke call to:
  `response = client.invoke({"query": prompt, "response_format": {"type": "json_object"}}) or {}`
- [ ] **Step 2:** In `report_enricher.generate_report`, change to:
  `client.invoke({"query": prompt, "max_tokens": _REPORT_MAX_TOKENS, "response_format": {"type": "json_object"}})`
- [ ] **Step 3: Run** `cd server && .venv/bin/python manage.py test scanner -v 1` → Expected: 93+ passing (no regressions; fim mode ignores response_format).
- [ ] **Step 4: Commit** `git commit -am "feat(lsast): request JSON object format from verifier + enricher"`

### Task 3.3: Live A/B acceptance + handoff
- [ ] **Step 1:** With the instruct server up, run the A/B:
```bash
cd server && LLM_MODEL_MODE=instruct VLLM_BASE_URL=http://127.0.0.1:8001/v1 \
  .venv/bin/python manage.py shell < /path/to/verification/verifier_ab.py
```
Expected: UNSAFE → `TP`, **SAFE → `FP`** (the key change vs the FIM model), both parseable.
- [ ] **Step 2:** Record the result in `metrics/scorecard.md` under "W3". Update `CLAUDE.md`. Commit. Write the W4 brief.

> **W4 brief:** re-tighten `build_verifier_prompt` ("default FP unless you can name a concrete exploit
> path"), then measure verifier Tier-2 on curated: `run_eval.py --tier verifier`. Confirm `fusion` suppresses
> FP+low/medium. Acceptance: Tier-2 meets §9 or a documented gap.

---

## Week 4 — Verifier correctness + fusion suppression

**Session goal:** with the instruct model + JSON, the verifier discriminates and fusion suppresses safe
low/medium findings. **Acceptance test:** `run_eval.py --tier verifier --dataset curated` meets §9
(F1 ≥ 0.70, FP ≤ 25%, recall ≥ 0.60) or logs a documented gap + plan; characterization tests still green.
**Milestone: verifier discriminates.**

### Task 4.1: Strengthen the verifier prompt (now that the model follows instructions)
**Files:** Modify `server/scanner/rag/llm_verifier.py`; Test `server/scanner/tests/test_finding_normalizer.py` is unaffected; add to `test_semgrep_detector`-style verifier test.
- [ ] **Step 1: Write a failing prompt-content test** in a new `server/scanner/tests/test_llm_verifier.py`:
```python
from django.test import SimpleTestCase
from scanner.rag.llm_verifier import build_verifier_prompt
from scanner.rag.lsast_types import DataflowContext

class VerifierPromptTests(SimpleTestCase):
    def test_prompt_biases_to_fp_without_exploit_path(self):
        p = build_verifier_prompt(cwe="CWE-89", language="python",
            dataflow=DataflowContext(1,"x",2,"y"), code_excerpt="q")
        self.assertIn("FALSE positive", p)
        self.assertIn("concrete exploit path", p)
```
- [ ] **Step 2: Run** → FAIL. **Step 3:** add to `build_verifier_prompt` the guidance line:
  `"Default to FALSE positive (FP) unless you can name a concrete exploit path from source to sink."`
- [ ] **Step 4: Run** the test → PASS. **Step 5: Commit** `git commit -am "feat(verifier): FP-default prompt for the instruct model"`

### Task 4.2: Measure Tier-2 + record
- [ ] **Step 1:** With instruct server up:
```bash
cd scripts/eval && PYTHONPATH=../../server LLM_MODEL_MODE=instruct \
  VLLM_BASE_URL=http://127.0.0.1:8001/v1 SEMGREP_BIN=../../server/.venv/bin/semgrep \
  SEMGREP_RULES_DIR="/Applications/Code Sense.app/Contents/Resources/resources/semgrep-rules" \
  ../../server/.venv/bin/python run_eval.py --dataset curated --tier all
```
Expected: a Tier-2 verifier precision/recall/F1 + FP-rate (non-zero suppression). Record in `metrics/scorecard.md` "W4"; if below §9, write the gap + a tuning note.
- [ ] **Step 2:** Re-run characterization (`test_characterization`) → still green (detector untouched).
- [ ] **Step 3:** Update `CLAUDE.md`; commit; write the W5 brief.

> **W5 brief:** raise enrichment parse-rate >80% with the instruct model (re-run `enrich_sample.py`); add a
> device-tier model config (`MODEL_TIER=low|mid|high` → 1.5B/7B/14B gguf filename) read at launch. Acceptance:
> enrichment >80% parse + ≥2 tiers switch.

---

## Week 5 — Enrichment quality + device-tier model config

**Session goal:** enrichment parses >80% and runs accurately on the instruct model; the build can target a
device tier. **Acceptance test:** `enrich_sample.py` shows >80% parse on a 10-finding set; a `model_tier()`
config resolves ≥2 tiers to the right GGUF filename. **Milestone: LLM quality fixed.**

### Task 5.1: Device-tier model resolution
**Files:** Modify `server/scanner/rag/llm.py` (or a small new `server/scanner/rag/model_tiers.py`); Test `server/scanner/tests/test_model_tiers.py`
- [ ] **Step 1: Failing test**
```python
import os
from unittest import mock
from django.test import SimpleTestCase
from scanner.rag.model_tiers import gguf_filename_for_tier

class ModelTierTests(SimpleTestCase):
    def test_tiers_map_to_filenames(self):
        self.assertEqual(gguf_filename_for_tier("low"), "astra-1.5B.gguf")
        self.assertEqual(gguf_filename_for_tier("mid"), "astra-7B.gguf")
        self.assertEqual(gguf_filename_for_tier("high"), "astra-14B.gguf")
    def test_unknown_defaults_to_mid(self):
        self.assertEqual(gguf_filename_for_tier("bogus"), "astra-7B.gguf")
```
- [ ] **Step 2: Run** → FAIL. **Step 3:** create `server/scanner/rag/model_tiers.py`:
```python
"""Map a device tier to the GGUF filename the build stages. The launcher/build
chooses the tier; this keeps the mapping in one tested place."""
_TIERS = {"low": "astra-1.5B.gguf", "mid": "astra-7B.gguf", "high": "astra-14B.gguf"}

def gguf_filename_for_tier(tier: str) -> str:
    return _TIERS.get((tier or "").lower(), _TIERS["mid"])
```
- [ ] **Step 4: Run** → PASS. **Step 5: Commit** `git add -A && git commit -m "feat(llm): device-tier→gguf mapping"`

### Task 5.2: Enrichment parse-rate acceptance
- [ ] **Step 1:** With the instruct server up, run the enrichment sample over the DVB backend (or a fixed 10-finding set):
```bash
cd server && LLM_MODEL_MODE=instruct VLLM_BASE_URL=http://127.0.0.1:8001/v1 \
  SEMGREP_BIN=/path/to/opengrep SEMGREP_RULES_DIR=/path/to/semgrep-rules \
  .venv/bin/python manage.py shell < /path/to/verification/enrich_sample.py
```
Expected: >8/10 findings return a non-None report (>80% parse), accurate, no hallucinated CWE class.
- [ ] **Step 2:** Record in `metrics/scorecard.md` "W5 — enrichment parse-rate". Update `CLAUDE.md` (Phase 1 complete). Commit. Write the Phase-2 / W6 brief.

> **Phase 1 done when:** instruct model live behind the flag, verifier emits FP (A/B + Tier-2), enrichment
> >80% parse, characterization green, scorecard rows W1–W5 filled. **W6 brief:** parallelize verifier+reporter
> calls in `lsast_scanner.py` with bounded concurrency; acceptance = DVB wall-time ↓≥40% vs W1, identical findings.

---

## Phase 1 acceptance summary
- [ ] Characterization tests green (detector locked).
- [ ] `metrics/scorecard.md` has W1 baseline + W3/W4/W5 entries.
- [ ] Instruct model loads behind `LLM_MODEL_MODE=instruct`; A/B: safe→FP, unsafe→TP.
- [ ] Verifier Tier-2 measured vs §9; enrichment parse-rate >80%.
- [ ] `cd server && .venv/bin/python manage.py test scanner` green throughout.
