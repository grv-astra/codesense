# Code changes — file by file (14 files)

All paths relative to the `yacm` repo root. Full copies are in `code/<same path>`; the combined
diff is `codesense-changes.patch`. **91 scanner tests pass** (`cd server && .venv/bin/python manage.py test scanner`).

## Production code (server/scanner/rag/)

### `finding_normalizer.py` (modified)
- Added `_rule_name(rule_id)` — the last dotted segment of the Semgrep `check_id` (the clean rule name).
- `title` now = `_rule_name(f.rule_id) or f.message or "Vulnerability"` (was: the prose message).
- `description`/`security_risk` still = the Semgrep message.

### `semgrep_detector.py` (modified — the biggest change, ~205 lines)
- **CWE derivation:** hardened `_extract_cwe` + new `derive_cwe(metadata, rule_id)` with layered fallback
  (explicit CWE → `_cwe_from_rule_id` keyword map → `_cwe_from_owasp` map → `_cwe_from_category` →
  `CWE-710` for non-security categories). `parse_semgrep_json` now calls `derive_cwe`.
- **OpenGrep compatibility in `run_semgrep`:** dropped `--metrics off`; set subprocess env
  `PYTHONUTF8=1` + `LC_ALL=C.UTF-8` + `LANG=C.UTF-8` + `SEMGREP_SEND_METRICS=off`.
- **Robust taint trace:** rewrote `_extract_taint_trace` + new `_find_loc_and_code` to handle BOTH
  Semgrep's list-of-dicts and OpenGrep's `["CliLoc", [loc, code]]` tagged-tuple shape, never raising.
- Guarded `extra`/`metadata` against non-dict values.

### `report_enricher.py` (NEW)
- The "reporting" LLM pass: `build_report_prompt`, `generate_report` (fail-open → `None`), `apply_report`
  (overlays name/description/impact/remediation onto the finding dict, per-field fallback). `enrichment_enabled()`
  reads `LSAST_ENRICH_FINDINGS` (default on). Anchors on `detector_note` (the Semgrep message). `_REPORT_MAX_TOKENS = 384`.

### `lsast_types.py` (modified)
- New `FindingReport` dataclass + lenient `from_json` (tolerates alias keys: title/risk/mitigation/fix).

### `lsast_scanner.py` (modified)
- After fusion, for each **visible** finding, calls `generate_report(...)` + `apply_report(...)`
  (passes `detector_note=sf.message`). Fail-open keeps deterministic fields.

### `llm.py` (modified)
- `VLLMClient.invoke` accepts an optional `payload["max_tokens"]` override (bounded by context), bypassing
  the default 200-token cap. Backward-compatible (only active when a caller passes it). Used by the report pass.

## Build / packaging (scripts/)

### `offline_sbom/fetch_offline_tools.sh` (modified)
- OpenGrep fetch corrected: `OPENGREP_VERSION=1.22.0`, real per-OS asset names, **fatal** on failure
  (removed the swallowed-404 warning) + a `<1MB` size guard. Staged as `semgrep`/`semgrep.exe`.

### `build_windows.ps1` (modified)
- Same fix for Windows: `v1.22.0`, correct `opengrep_windows_x86.exe` (was the non-existent `_x86_64`),
  fatal + size guard (was a swallowed `Write-Warning`).

### `eval/BASELINE.md` (modified)
- Added the **Verifier (Tier 2) audit** section: root cause (FIM model TP-bias), the safe/unsafe A/B
  result, why no code patch was applied, and the model-swap recommendation.

## Tests (server/scanner/tests/) — all green

- `test_finding_normalizer.py` — title-from-rule-name + fallback cases (updated an existing assertion that
  intentionally changed).
- `test_semgrep_detector.py` — `DeriveCweTests` (incl. the `source`/`rce` misfire guard) +
  `ExtractTaintTraceTests` (Semgrep + OpenGrep shapes + never-raise) + the UTF-8-env/no-`--metrics` test.
- `test_report_enricher.py` (NEW) — `FindingReport.from_json`, prompt contents, fail-open, env toggle, overlay.
- `test_lsast_scanner.py` — `setUp` patches `generate_report`→None for hermeticity + a new wiring test
  asserting a visible finding is enriched while CWE/severity stay deterministic.

## Docs

### `docs/superpowers/specs/2026-05-31-instruction-tuned-verifier-model-swap-scope.md` (NEW)
- The model-swap scope. **§9 has the verified research + the urgent license finding + the device-tier mapping.**

## NOT included here (intentionally)
- The bundled Semgrep rules tree (`client/src-tauri/resources/semgrep-rules/`, ~2,100 files) — produced by
  `scripts/offline_sbom/stage_semgrep_rules.py` at build time; not "our code."
- Build artifacts / zips / `.gguf` models / `__pycache__`.
- The in-place app binary swap (a verification step, not a repo change) — for distribution, do a clean
  `build_macos.sh` / `build_windows.ps1` run.
