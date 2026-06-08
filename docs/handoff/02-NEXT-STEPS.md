# Next steps, open items & decisions

Ordered roughly by priority. Items marked **[decision]** need a human call before implementing.

## 0. Immediate housekeeping
- **Commit these 14 files** on a branch (they're uncommitted on `main`). Suggested message:
  "LSAST: rule-name titles, real OpenGrep bundling + compat, layered CWE derivation, verifier audit, LLM report enrichment."
- **Push `main` to `origin`** — currently **blocked**: local `main` is **71 commits ahead** and the push
  fails in a non-interactive shell (`could not read Username for 'https://github.com'`). Run
  `git push origin main` from a normal terminal with a PAT/SSH configured. *(Nothing in this handoff can
  unblock this — it needs the user's GitHub credentials.)*

## 1. ⚠️ Model license — URGENT (compliance, not just quality)
**Verified on Hugging Face:** the model we ship, **Qwen2.5-Coder-3B** (the `astra.gguf` fine-tune base),
is under the **non-commercial `qwen-research` license**. Its 0.5B/1.5B/7B/14B/32B siblings are Apache-2.0;
**only the 3B is restricted.** Shipping it in a commercial product is almost certainly a violation.
- **Action:** confirm the exact base-model lineage of `astra.gguf` with whoever fine-tuned it, get legal
  sign-off, and plan to **move off the 3B** regardless of the quality swap below.
- See `docs/instruction-tuned-model-swap-scope.md` §9.1.

## 2. Instruction-tuned model swap (fixes the verifier AND the enrichment rate)
The bundled FIM model is why the verifier rubber-stamps `TP` and the enrichment only parses ~34% of the
time. Scope is fully written (`docs/instruction-tuned-model-swap-scope.md`). Summary:
- **[decision] Which model/size ladder?** Recommended: **Qwen2.5-Coder-Instruct, Apache sizes** — low =
  1.5B (Q5_K_M/Q6_K), mid/default = 7B (Q4_K_M), high = 14B, GPU = 32B. One ChatML code path. The
  non-commercial 3B leaves a "3B-class" gap → fill with **Qwen3-4B-Instruct** (Apache, same ChatML) or
  cross-family **IBM Granite-3.3-2B** (Apache). Second choices: Granite-3.x, Gemma-3/→4, Phi-4-mini (MIT).
- **[decision] Quant per tier** (Q4_K_M vs Q5/Q6/Q8 — sub-2B should avoid Q4) and **whether to add
  grammar-constrained JSON** (recommended — see below).
- **Implementation (~1–1.5 days):**
  1. Convert the chosen Instruct model → GGUF via the existing `scripts/offline_ai/convert_model_to_gguf.sh`
     (point `MODEL_SRC` at the HF dir; produce Q4_K_M + a higher-precision variant). Needs a networked build host once.
  2. **De-FIM `server/scanner/rag/llm.py`:** the FIM `_STOP_TOKENS` and `_clean_output()`'s "Vulnerability:"
     hunting + FIM-marker stripping will mangle clean instruct JSON — gate them off / make `_clean_output`
     a near-no-op. Allow a small **system prompt** (the code currently says "NO system prompt" for the FIM model).
  3. Add **grammar-constrained JSON** to the verifier + reporter calls: `llama-server` supports GBNF and
     `response_format` (`json_object` is the build-stable one; `json_schema` is flakier across versions —
     pin the build). This makes valid JSON essentially guaranteed.
  4. Re-tighten the verifier prompt (the "default to FP unless you can name a concrete exploit path" framing
     that *failed* on the FIM model should now work).
  5. **Validate** with the scripts in `verification/`: the safe/unsafe **A/B** (safe parameterized query must
     now → `FP`), the **DVB audit** (expect a non-zero suppress rate), the **enrichment sample** (target
     >80% parse, accurate, no hallucination), and **eval Tier-2** (`scripts/eval/run_eval.py --tier verifier`
     vs the §9 thresholds: F1 ≥ 0.70, FP ≤ 25%, recall ≥ 0.60). Then re-freeze + in-place swap + DVB rescan.
- **Device-tier packaging:** ship different installers per tier (the build scripts already stage
  `$MODEL_GGUF` → `resources/model/astra.gguf`; just point it at the chosen GGUF). Consider a small
  launcher check that picks the tier by available RAM.

## 3. Scan performance — batching
Each finding now triggers **2 sequential LLM calls** (verifier + reporter); a ~50-finding DVB scan takes
~9 min single-threaded. Options: batch/parallelize the verifier+reporter calls, or merge them into one call
that returns verdict + report together. `LSAST_ENRICH_FINDINGS=0` disables enrichment as a stopgap.

## 4. Verifier value (depends on #2)
Until the model swap, the verifier suppresses nothing (fail-safe). After the swap, re-confirm fusion
actually suppresses safe/low-severity findings, and consider **persisting** `confidence` + `verifier_reason`
(currently set by `fusion.fuse` but dropped by `FindingModel.insert_many` — they aren't model fields; needs
a small migration) so the UI can show verdict metadata.

## 5. Distribution build
The session verified changes via an **in-place backend swap** into the installed app, not a fresh DMG. For
release, do a clean `scripts/build_macos.sh` (and `build_windows.ps1`) run — which will now fetch the real
OpenGrep binary (#Point 1) — and re-run the eval baseline.

## Verification commands (quick reference)
```bash
# unit tests (expect 91 passing)
cd server && .venv/bin/python manage.py test scanner

# verifier A/B + DVB audit + enrichment sample (need llama-server on :8001 and the bundled rules)
cd server && SEMGREP_BIN=/path/to/opengrep SEMGREP_RULES_DIR=/path/to/semgrep-rules \
  .venv/bin/python manage.py shell < ../verification/verifier_ab.py
# (verifier_audit.py and enrich_sample.py run the same way)

# eval harness (detector + verifier tiers)
cd scripts/eval && PYTHONPATH=../../server SEMGREP_BIN=… SEMGREP_RULES_DIR=… \
  ../../server/.venv/bin/python run_eval.py --dataset curated --tier detector
```
