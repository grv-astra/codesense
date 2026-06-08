# Session narrative — Code Sense LSAST quality work (2026-05-31)

This is the full account of the session, in the order it happened, so the dev team has the
same context the work was done with. It replaces "read the chat log."

## Background (state coming into the session)

**Code Sense** (`yacm`) is being repackaged as a single self-contained **offline** Windows/macOS
desktop app. The SAST engine is **LSAST**, the sole scan pipeline:

```
Semgrep/OpenGrep detector → finding normalizer → LLM verifier (TP/FP) → fusion (show/suppress/needs_review) → persist
```

- Backend: Django, frozen with PyInstaller as `codesense-server`; Tauri shell (`codesense`); bundled
  `llama-server` serving a quantized GGUF on `127.0.0.1:8001`; bundled Semgrep rules + (meant-to-be)
  OpenGrep binary; offline SBOM tools (Syft/Grype/Grant/Cosign).
- `main` is **71 commits ahead of `origin/main`** — **the push is blocked** (non-interactive shell
  can't supply GitHub HTTPS creds; no `gh`/SSH). This is unchanged and still requires the user to
  `git push` from their own terminal.
- A prior test scan of **Damn-Vulnerable-Bank (DVB)** produced 50 findings but surfaced 3 caveats,
  which became the work list below.

## Request 1 — "the finding names are all wrong. let the tool pick the finding names from semgrep. after this change, work on point 1 then 2 and then 3."

### (0) Finding-name fix
- **Problem:** `finding_normalizer.normalize()` set the finding `title` to the verbose Semgrep
  **message** (prose remediation text). The persisted `rule_id` was being dropped (it was stuffed
  into `affected`, which isn't a Finding model field).
- **Fix:** `title` now comes from the Semgrep **rule name** — the last dotted segment of the
  `check_id` (`_rule_name()`), e.g. `sequelize-raw-query`, `path-join-resolve-traversal`,
  `hardcoded-jwt-secret`. The prose message stays as `description`/`security_risk`. Falls back to
  message then `"Vulnerability"` if there's no rule id.
- **Why last-segment:** with a local `--config <dir>`, Semgrep/OpenGrep prefix the check_id with the
  whole install path (`Applications.CodeSense.app...semgrep-rules.dockerfile.security.missing-user`),
  so the full id is unusable; the last segment is the clean rule name.
- **Verified** on real DVB rule IDs (detector → normalizer) + 8 unit tests.

### (Point 1) Bundle a real OpenGrep binary
- **Problem:** the macOS app shipped with **no `semgrep` binary** — `fetch_offline_tools.sh` requested
  OpenGrep `v1.4.0` with the wrong asset name and **swallowed the 404 as a warning**, so a packaged
  scan found nothing. (A local wrapper had been bridging it.)
- **Fix:** corrected to the real release — `v1.22.0`, per-OS asset names (`opengrep_osx_arm64`,
  `opengrep_osx_x86`, `opengrep_manylinux_aarch64/x86`, `opengrep_windows_x86.exe`), made the fetch
  **fatal** (no more swallowed 404) with a size guard. Fixed the same class of bug in
  `build_windows.ps1` (it had `v1.4.0` + the wrong `opengrep_windows_x86_64.exe` name + a swallowed
  failure). All 5 asset URLs verified HTTP 200.
- **Detector compatibility (critical):** OpenGrep is a fork and differs from the dev-host Semgrep:
  - It **rejects `--metrics`** (rc=2). Dropped the flag; telemetry-off for upstream Semgrep is now via
    `SEMGREP_SEND_METRICS=off` env (OpenGrep ignores it).
  - It reads rule YAMLs with the **process locale** → on a non-UTF-8 locale it crashes with
    `UnicodeDecodeError` on rule files containing non-ASCII bytes. Fixed by forcing
    `PYTHONUTF8=1` + `LC_ALL=C.UTF-8` + `LANG=C.UTF-8` in the detector subprocess env.
  - Its `dataflow_trace` uses an OCaml **tagged-tuple** shape `["CliLoc", [ {start…}, "code" ]]`,
    not Semgrep's list-of-dicts — the old parser did `item.get(...)` on the `"CliLoc"` string and
    **crashed the whole scan** (`AttributeError`). Rewrote `_extract_taint_trace` to be robust to
    both shapes and never raise.
- **Verified:** the real `opengrep_osx_arm64` runs the exact detector invocation against the bundled
  rules and produces the same 32 findings as upstream Semgrep.

### (Point 2) Verifier false-positive audit
- **Question:** the verifier kept all 50 DVB findings "open" — is it working?
- **Findings (decisive):** ran the verifier **live** over all 32 DVB findings + a controlled safe/unsafe
  A/B. It returned **`TP` for everything** (conf 0.8–0.9, 0 fail-open) — *even a safe parameterized
  query whose own `reason` said "parameterized queries, which prevents SQL injection."* It does **not**
  fail open; it simply **never emits `FP`**.
- **Root cause:** the bundled model (`astra.gguf`, alias `astra-code-reviewer`) is a **Qwen2.5-Coder-3B
  fill-in-the-middle (FIM) completion model, not instruction-tuned**. It has a hard `TP`-label bias and,
  with longer prompts, **echoes the prompt back** (→ unparseable → fail-open). Prompt fixes were tested
  and made it *worse*. Suppression requires `FP`, so nothing is ever suppressed → "all open."
- **Decision:** **no risky code change.** A "parse the reason and flip TP→FP" override was considered and
  rejected — the model also hallucinates, and in a security tool a wrong *suppression* (missed vuln) is
  worse than a kept false positive. The current fail-safe (show everything) is correct while the model is
  non-discriminative. Documented in `scripts/eval/BASELINE.md`; the real fix is a model swap (scoped — see
  the scope doc).

### (Point 3) CWE-Unknown derivation
- **Problem:** many findings showed `CWE-Unknown` (rules without `cwe` metadata; in DVB this was mostly
  non-security lint rules firing repeatedly).
- **Fix:** layered `derive_cwe(metadata, rule_id)` — explicit `metadata.cwe` (hardened to handle int /
  `"CWE-89: …"` / bare number) → **rule-name keyword** map (`sqli`→89, `path-traversal`→22,
  `hardcoded`/`jwt-secret`→798, `csrf`→352, …) → **OWASP tag** map (Injection→74, XSS→79, SSRF→918, …) →
  **non-security category** (`correctness`/`best-practice`/… → CWE-710 "coding standards"). Returns `""`
  (→ `CWE-Unknown`) only when nothing fits, and never fabricates a CWE for an unclassifiable *security*
  rule.
- **Trap avoided:** naive substrings would mislabel `dockerfi**le-source**-not-pinned` as CWE-78 because
  "sou**rce**" contains "rce" — keys are long/unambiguous, guarded by a regression test.
- **Verified:** DVB `CWE-Unknown` dropped **2/11 → 0/11** unique rules, no misfires; 7 new unit tests.

### Live verification (in the installed app)
Because the app runs the *frozen* backend, the changes were verified end-to-end by: re-freezing
`codesense-server` (PyInstaller), swapping it **and** the real `opengrep_osx_arm64` binary into the
installed `Code Sense.app` (replacing the wrapper), ad-hoc re-signing (`codesign --force --deep --sign -`,
the app is adhoc-signed), relaunching, and re-scanning DVB through the API. Confirmed: rule-name titles +
reduced CWE-Unknown live. (Originals backed up to `/tmp/*.orig`.)

## Request 2 — "introduce an additional prompt during the reporting. let the LLM generate the finding name, description and other details present in the finding details in the app."

- Added a **second, separate LLM pass** (distinct from the TP/FP verifier): `report_enricher.py`
  authors the human-facing fields — **name → title, description, impact → security_risk,
  remediation → mitigation**.
- **Safe by design:** **fail-open** (any LLM failure/garble/disable leaves the deterministic
  Semgrep-derived fields); **CWE / severity / file / line are never LLM-authored** (the weak model would
  hallucinate them); **anchored to the Semgrep rule message** (`detector_note`) + "don't invent a
  different vuln class" — this fixed an initial hallucination where `missing-user` (CWE-250) came back as
  "OS Command Injection." Runtime toggle `LSAST_ENRICH_FINDINGS=0`. Added an optional `max_tokens`
  override to the LLM client (a report needs more than the verdict's 200-token cap).
- **Live result:** scan completed (50 findings); **17/50 got full LLM reports** (accurate, e.g.
  "Missing User Specification in Dockerfile", "SQL Injection Vulnerability"), the rest **fail-open** to
  deterministic fields. `mitigation` is now populated (was always empty). The ~34% rate is the same FIM
  model limitation from Point 2 — an instruction-tuned model lifts both the verifier and this.
- **Perf:** scan now makes ~2 LLM calls/finding (verifier + reporter), single-threaded → ~9 min for DVB.
  Batching is the obvious follow-up.
- 91 scanner tests green; verified live via a 3rd backend re-freeze + swap.

## Request 3 — "scope the instruction-tuned model swap"

Wrote `docs/superpowers/specs/2026-05-31-instruction-tuned-verifier-model-swap-scope.md`. Key insight:
the current model is **Qwen2.5-Coder-3B (base/FIM)**, so its **Instruct sibling is a same-architecture,
same-size, same-ChatML drop-in**; the existing `scripts/offline_ai/convert_model_to_gguf.sh` + build
staging already support it. The real work is **de-FIM-ing the LLM client** (its FIM stop-tokens and
`_clean_output()` "Vulnerability:" hunting would mangle clean instruct JSON). ~1–1.5 days, no
architectural change. (The user dismissed the follow-up parameter questions — i.e. they wanted the scope,
not an immediate build.)

## Request 4 — "/deep-research … best model for both calls, with variants for different device configs"

The `/deep-research` workflow **failed** (its subagents wouldn't emit the forced structured output; it
burned 105 agents / 1.36M tokens retrying). Re-ran the research via **3 parallel research agents +
direct Hugging Face verification** of the load-bearing claims. Result folded into the scope doc **§9**:

- **⚠️ VERIFIED LICENSE BLOCKER:** **Qwen2.5-Coder-3B (what we ship) is under the non-commercial
  `qwen-research` license.** Its 0.5B/1.5B/7B/14B/32B siblings are **Apache-2.0** — only the 3B is
  restricted. Shipping a 3B fine-tune in a commercial product is almost certainly outside the license.
  **Urgent: move off the 3B + get legal sign-off.**
- **Recommendation:** stay in **Qwen2.5-Coder-Instruct, Apache sizes only**, one ChatML code path, with a
  device-tier ladder (low = 1.5B @ Q5_K_M/Q6_K, mid/default = 7B @ Q4_K_M, high = 14B, GPU = 32B). **One
  model serves both calls** (two prompts). Make JSON bulletproof with llama.cpp **GBNF / `response_format`**
  grammar-constrained decoding. The non-commercial 3B leaves a "3B-class" gap — fill with **Qwen3-4B-Instruct**
  (Apache, same ChatML) or cross-family **IBM Granite-3.3-2B** (Apache). Second choices: Granite-3.x,
  Gemma-3/→4, Phi-4-mini (MIT, single size), Llama-3.2/3.1 (custom license). Full table + sources in the doc.

## Request 5 — this handoff package.

## Always-pending / blocked
- **Push `main` to `origin`** — blocked on the user's GitHub auth (do it from a normal terminal).
- **Commit these changes** — currently uncommitted on `main` (14 files).
- **Clean `build_macos.sh` DMG rebuild** for distribution (work was verified via in-place swap, not a fresh DMG).
