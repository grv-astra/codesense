# Code Sense Roadmap — Phase 3 Plan (Weeks 9–12): Features + Packaging + Harden

> **For agentic workers:** REQUIRED SUB-SKILL: use superpowers:subagent-driven-development or
> superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** expand language coverage with per-language eval, overhaul the finding-details view to surface the
new verdict/enrichment data, produce a clean signed/notarized installer, and measure the 12-week results.

**Architecture:** language work is registry + rules + eval only (no detector logic change). The UX consumes
the W7 API fields. The signed build extends the existing `build_macos.sh` / `build_windows.ps1`.

**Tech Stack:** Python/Django + `scripts/eval/`; React/TypeScript + Tauri (frontend, `client/src/`); shell +
PowerShell builds. Backend tests `cd server && .venv/bin/python manage.py test scanner`; frontend per
`client/` test setup. **Spec/Phase1/Phase2:** see those docs.

---

## Week 9 — Language-coverage expansion (feature)

**Session goal:** add ≥4 top-40 languages end-to-end (registry routing + bundled rules + per-language eval),
with explicit "no analyzer coverage" reporting for routing-only langs. **Acceptance test:** `language_for_path`
resolves the new extensions to the right `Language` with the right coverage tier; a per-language detector eval
runs for each; the registry stays well-formed (unique extensions). **Milestone: broader coverage, measured.**

### Task 9.1: Add registry entries + keep the table well-formed
**Files:** Modify `server/scanner/rag/languages.py` (the `LANGUAGES` list, line ~28); Test `server/scanner/tests/test_languages.py` (create if absent)
- [ ] **Step 1: Failing test** — new extensions resolve + registry invariants hold
```python
from django.test import SimpleTestCase
from scanner.rag.languages import language_for_path, LANGUAGES

class LanguageRegistryTests(SimpleTestCase):
    def test_new_languages_route(self):
        cases = {"main.go": "go", "app.rb": "ruby", "Program.cs": "csharp", "Main.kt": "kotlin"}
        for path, name in cases.items():
            self.assertEqual(language_for_path(path).name, name, path)

    def test_extensions_are_unique(self):
        seen = set()
        for lang in LANGUAGES:
            for ext in lang.extensions:
                self.assertNotIn(ext, seen, f"duplicate extension {ext}")
                seen.add(ext)

    def test_coverage_tiers_valid(self):
        for lang in LANGUAGES:
            self.assertIn(lang.coverage, {"strong", "partial", "none"})
```
- [ ] **Step 2: Run** `manage.py test scanner.tests.test_languages` → FAIL for any missing language. **Step 3:** add/confirm `Language` entries in `LANGUAGES` for Go (`.go`, strong), Ruby (`.rb`, strong), C# (`.cs`, strong), Kotlin (`.kt`,`.kts`, strong) — matching the existing entry shape `Language("go", (".go",), "go", "strong")`.
- [ ] **Step 4: Run** → PASS. **Step 5: Commit** `git commit -am "feat(languages): add Go/Ruby/C#/Kotlin routing entries"`

### Task 9.2: Per-language detector eval + coverage report
**Files:** Add curated fixtures under `scripts/eval/data/curated/` (one real + one safe per new language) + manifest entries
- [ ] **Step 1:** Add the fixtures (e.g. a Go SQLi via string concat + a safe parameterized Go file). **Step 2:** Run:
```bash
cd scripts/eval && PYTHONPATH=../../server SEMGREP_BIN=../../server/.venv/bin/semgrep \
  SEMGREP_RULES_DIR="$RULES_DIR" ../../server/.venv/bin/python run_eval.py --dataset curated --tier detector
```
Expected: per-language recall reported (the harness already breaks down per-language per the spec); the new languages show non-zero recall.
- [ ] **Step 3:** Record per-language coverage in `metrics/scorecard.md` "W9". Update `CLAUDE.md`; commit; write the W10 brief.

> **W10 brief:** in `client/src/types/finding.ts` add `rule_id?/confidence?/verifier_reason?`; in
> `client/src/components/update/UpdatedFinding.tsx` render confidence, verifier reason, remediation, dataflow,
> CWE link, severity (graceful when empty). Acceptance: renders for a real scan; render test.

---

## Week 10 — Finding-details UX overhaul (feature; consumes W7 API fields)

**Session goal:** the details view surfaces the verifier confidence + reason, the LLM remediation, the
dataflow, a CWE reference link, and severity — degrading gracefully for fail-open findings with empty fields.
**Acceptance test:** the details component renders all fields for a real scan finding and shows nothing
broken when a field is empty; a component render test passes. **Milestone: richer triage UX.**

### Task 10.1: Extend the finding TypeScript type
**Files:** Modify `client/src/types/finding.ts`
- [ ] **Step 1:** Add optional fields to the finding interface (follow the existing field declarations):
```typescript
  rule_id?: string;
  confidence?: number | null;
  verifier_reason?: string;
```
- [ ] **Step 2:** Typecheck: `cd client && npx tsc --noEmit` → Expected: no new errors. **Step 3: Commit** `git commit -am "feat(ui): finding type gains rule_id/confidence/verifier_reason"`

### Task 10.2: Render the fields in the details view
**Files:** Modify `client/src/components/update/UpdatedFinding.tsx`
- [ ] **Step 1: Write/extend a render test** (follow the existing `client/` test setup — vitest/RTL; if none exists, add a minimal vitest test). Assert the component shows the remediation + a confidence indicator + the CWE link when present, and renders without crashing when `confidence`/`verifier_reason`/`mitigation` are undefined.
```tsx
// client/src/components/update/UpdatedFinding.test.tsx
import { render, screen } from "@testing-library/react";
import UpdatedFinding from "./UpdatedFinding";
const base = { title: "node-mysql-sqli", cwe: "CWE-89", severity: "high",
  description: "d", security_risk: "r", mitigation: "use params",
  confidence: 0.82, verifier_reason: "tainted concat", rule_id: "x.sqli" };
test("renders remediation + cwe link + confidence", () => {
  render(<UpdatedFinding finding={base as any} />);
  expect(screen.getByText(/use params/)).toBeInTheDocument();
  expect(screen.getByText(/CWE-89/)).toBeInTheDocument();
});
test("renders without optional fields", () => {
  render(<UpdatedFinding finding={{ ...base, confidence: undefined,
    verifier_reason: undefined, mitigation: "" } as any} />);
  expect(screen.getByText(/node-mysql-sqli/)).toBeInTheDocument();
});
```
- [ ] **Step 2: Run** `cd client && npx vitest run src/components/update/UpdatedFinding.test.tsx` → FAIL (fields not rendered).
- [ ] **Step 3: Implement** — in `UpdatedFinding.tsx`, following the component's existing section/markup pattern, add: a **Remediation** block (`finding.mitigation`, shown only if non-empty), an **Impact** block (`finding.security_risk`), a **Verifier** block (confidence as a % + `verifier_reason`, shown only if `confidence != null`), and a **CWE link** (`https://cwe.mitre.org/data/definitions/<n>.html` from `finding.cwe`). Guard each with a truthy check so empty fields render nothing.
- [ ] **Step 4: Run** the render test → PASS; `npx tsc --noEmit` clean.
- [ ] **Step 5:** Manual check against a live scan (instruct model) — details view shows the new blocks. Record in scorecard "W10". **Step 6: Commit** `git commit -am "feat(ui): finding-details shows verifier verdict, remediation, dataflow, CWE link"`
- [ ] **Step 7:** Update `CLAUDE.md`; write the W11 brief.

> **W11 brief:** extend `scripts/build_macos.sh` (DMG sign+notarize when creds set) and `build_windows.ps1`;
> produce an installer bundling the real OpenGrep + the Apache model (mid tier) + rules. Acceptance: fresh-VM
> install + run + scan.

---

## Week 11 — Clean signed/notarized distribution build

**Session goal:** a clean build produces an installer that bundles the real OpenGrep binary, the Apache
instruct model, and the rules, and that installs + runs + scans on a fresh machine. **Acceptance test:** the
DMG/EXE, run on a clean VM (no dev tools), installs, launches, logs in, and completes a scan producing
findings with rule-name titles + verifier verdicts. **Milestone: shippable installer.**

### Task 11.1: macOS signed/notarized DMG
**Files:** Modify `scripts/build_macos.sh`
- [ ] **Step 1:** Confirm the model staging targets the chosen tier GGUF (from `MODEL_GGUF`/`MODEL_TIER`) and `LLM_MODEL_MODE=instruct` is set in the launcher env (`client/src-tauri/src/main.rs` — add the env alongside `VLLM_MODEL`). 
- [ ] **Step 2:** Run a clean build with signing creds:
```bash
APPLE_SIGNING_IDENTITY="Developer ID Application: <Name> (<TEAMID>)" \
  APPLE_ID=... APPLE_PASSWORD=... APPLE_TEAM_ID=... \
  MODEL_GGUF=dist/model/astra-7B-Q4_K_M.gguf LLAMA_SERVER=~/llama.cpp/build/bin/llama-server \
  bash scripts/build_macos.sh
```
Expected: a `.dmg` under `client/src-tauri/target/release/bundle/dmg/`; `codesign --verify --deep --strict` OK; `xcrun stapler validate` OK.
- [ ] **Step 3:** Acceptance — install the DMG on a clean macOS VM, launch, log in, scan a small repo → findings appear with rule-name titles + (if instruct model present) verifier verdicts. Record pass/fail + app size in scorecard "W11".
- [ ] **Step 4: Commit** `git commit -am "build(macos): sign+notarize DMG bundling OpenGrep + instruct model"`

### Task 11.2: Windows EXE
**Files:** Modify `scripts/build_windows.ps1`
- [ ] **Step 1:** Mirror the model/mode wiring; run `build_windows.ps1` on a Windows build host → produces the installer with `semgrep.exe` (real OpenGrep, already fixed) + the model + rules.
- [ ] **Step 2:** Acceptance — install on a clean Windows VM, launch, scan → findings appear. Record in scorecard.
- [ ] **Step 3: Commit** `git commit -am "build(windows): installer bundling OpenGrep + instruct model"`
- [ ] **Step 4:** Update `CLAUDE.md`; write the W12 brief.

> **W12 brief:** re-run the full scorecard (accuracy + perf + packaging), write `metrics/RESULTS.md` with the
> before/after table vs W1, fix the top regressions, finalize release notes.

---

## Week 12 — Harden + measure results

**Session goal:** the 12-week outcomes are measured against the W1 baseline and documented; top regressions
fixed. **Acceptance test:** `metrics/RESULTS.md` shows the before/after scorecard with targets met (or
documented gaps); `manage.py test scanner` green; the eval gate green. **Milestone: outcomes measured.**

### Task 12.1: Re-run the full scorecard
- [ ] **Step 1:** Re-measure every scorecard axis (detector + verifier Tier-2 + enrichment parse-rate + DVB
  scan wall-time + build/app-size) with the W12 build/model. **Step 2:** Use `scripts/eval/scorecard.py`'s
  `render_scorecard` to render W12 values.

### Task 12.2: Write the before/after results doc
**Files:** Create `metrics/RESULTS.md`
- [ ] **Step 1:** Table with W1 → W12 for each metric + the §9 thresholds + pass/fail. **Step 2:** A short
  narrative: what improved, what's still open (deferred items from the spec §7), recommended next quarter.
- [ ] **Step 3: Commit** `git add metrics/RESULTS.md && git commit -m "docs(results): 12-week before/after scorecard"`

### Task 12.3: Final hardening + handoff
- [ ] Fix the top 1–2 regressions surfaced by the re-measure (each TDD: failing test → fix → green → commit).
- [ ] Update `CLAUDE.md` to "roadmap complete"; write release notes. Final `git commit`.

## Phase 3 acceptance summary
- [ ] +4 languages route + have per-language eval.
- [ ] Finding-details view surfaces verdict/remediation/dataflow/CWE (render test green).
- [ ] Signed DMG + EXE install + scan on clean VMs.
- [ ] `metrics/RESULTS.md` shows before/after; tests + eval gate green.
