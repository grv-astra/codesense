# Scope — Swap the bundled FIM model for an instruction-tuned model

- **Date:** 2026-05-31
- **Status:** Scoping (pre-implementation) — for a go/no-go + parameter decision
- **Repo:** `yacm` (Code Sense), branch `main`
- **Motivates:** the verifier TP-bias audit + the report-enrichment parse-rate, both in `scripts/eval/BASELINE.md`

## 1. Problem

Two LSAST quality gaps trace to **one root cause — the bundled model**:

1. **Verifier never emits `FP`.** It rubber-stamps every finding `TP` (even code it describes as safe), so `fusion` suppresses nothing → "all findings open." (Audit: 0 FP over 32 DVB findings + a safe/unsafe A/B both → TP.)
2. **Report enrichment only parses ~34% of the time.** The model garbles JSON; the rest fail-open to deterministic fields.

Both are because the shipped model is a **fill-in-the-middle (FIM) code-completion model, not instruction-tuned** — it can't reliably follow "answer with this JSON" and, with longer prompts, *echoes the prompt back*.

## 2. Current state (grounded in the repo)

| Thing | Today |
|---|---|
| Model | **Qwen2.5-Coder-3B**, **base/FIM** variant (GGUF metadata: `general.name="Qwen2.5 Coder 3B"`, `size_label=3B`, FIM tokens `<|fim_prefix/middle/suffix/pad|>`) |
| Quant / size | `q8_0`, **3.1 GB**, at `resources/model/astra.gguf` |
| Server | Metal `llama-server` on `127.0.0.1:8001`, `--ctx-size 4096 --alias astra-code-reviewer` (`client/src-tauri/src/main.rs`) |
| Client env | `VLLM_MODEL=astra-code-reviewer`, `VLLM_BASE_URL=…:8001/v1` (main.rs) |
| Conversion | `scripts/offline_ai/convert_model_to_gguf.sh` — HF dir → `convert_hf_to_gguf.py` (f16) → `llama-quantize` (default `Q4_K_M`) |
| Build staging | `build_macos.sh` / `build_windows.ps1` copy `$MODEL_GGUF` → `resources/model/astra.gguf` (model is **passed in** by the build host, not built in CI) |
| Client `llm.py` | **FIM-specialized**: NO system prompt; `_STOP_TOKENS = [<|fim_middle|>, <|endoftext|>, "\nAnalyze this", "\n```\n\nAnalyze"]`; `_clean_output()` hunts `"Vulnerability:"` and strips FIM markers; `temp=0.05`; `max_tokens=200` (now caller-overridable); `/chat/completions` with `messages=[user-only]` |

**Why this makes the swap cheap:** the Instruct sibling **`Qwen2.5-Coder-3B-Instruct`** is the *same architecture (qwen2), tokenizer, and ~size* — so conversion, llama-server, ctx, and bundling are unchanged. The only real code work is undoing the FIM-specific client hacks.

## 3. Candidate models

| Model | Lic | q8_0 / Q4_K_M size | Notes |
|---|---|---|---|
| **Qwen2.5-Coder-3B-Instruct** *(recommended)* | Apache-2.0 | ~3.3 GB / ~2.0 GB | Drop-in (same family/size as current); strong code awareness; JSON + chat template + 32k ctx. |
| Qwen2.5-Coder-7B-Instruct | Apache-2.0 | ~8 GB / ~4.7 GB | Better reasoning → better FP discrimination, but bigger app + slower on CPU. Fallback if 3B under-discriminates. |
| Llama-3.2-3B-Instruct | Llama community | ~3.4 GB / ~2.0 GB | Great instruction-following, weaker code specialization; only if Qwen disappoints. |

**Recommendation:** ⚠️ **SUPERSEDED by §9 (verified research).** The "3B-Instruct drop-in" is **NOT viable** — Qwen2.5-Coder-**3B** (every size we'd touch, incl. the base we currently ship) is under the **non-commercial `qwen-research` license**, confirmed on Hugging Face. Use the **Apache-2.0** sizes (1.5B/7B/14B) instead. See §9 for the corrected family, per-tier mapping, and the urgent license action.

## 4. Work breakdown

### 4a. Conversion (build host, ~1–2 h, needs network once)
- Download `Qwen/Qwen2.5-Coder-3B-Instruct` (HF) → run the **existing** `convert_model_to_gguf.sh` (point `MODEL_SRC` at it; produce both `Q4_K_M` and `Q8_0` to compare). No script change required.
- Confirm the GGUF carries the **chat template** + Qwen EOS `<|im_end|>` (Instruct GGUFs do; llama-server applies them automatically on `/chat/completions`).

### 4b. De-FIM the client — `server/scanner/rag/llm.py` (the real work, ~0.5 day)
- **Drop/relax the FIM hacks** (they will mangle clean instruct output): the FIM `_STOP_TOKENS` and `_clean_output()`'s `"Vulnerability:"` hunting + FIM stripping. Make `_clean_output` a near-no-op (just trim) for the instruct model.
- **Allow a system prompt** (the code comment literally says "NO system prompt — this FIM model ignores it"). Add a small one for JSON discipline: *"You are a security analysis assistant. Respond with only valid JSON."*
- **(High-value) JSON-constrained decoding:** pass llama-server `response_format: {"type":"json_object"}` (or a GBNF grammar) on the verifier/enricher calls → near-eliminates parse failures.
- Keep `temp` low (0.0–0.1) for stable JSON; `max_tokens` already overridable.
- **Validate the change against every call site** (verifier + enricher are the only ones) — `_clean_output` is shared.

### 4c. Prompts (~1–2 h)
- Verifier (`llm_verifier.py`): now that instructions are followed, re-introduce the "default to FP unless you can name a concrete exploit path" framing that *failed* on the FIM model.
- Enricher (`report_enricher.py`): keep the analyzer-note anchoring; the model should now parse far more often.

### 4d. Build / bundle (~minimal)
- Build scripts already stage `$MODEL_GGUF` → `astra.gguf`; just point `MODEL_GGUF` at the new GGUF. Optionally rename the alias `astra-code-reviewer` (cosmetic; touches main.rs + `VLLM_MODEL`).
- **Size:** 3B-Instruct `q8_0` ≈ current 3.1 GB (net ~0); `Q4_K_M` shrinks the app ~1 GB.

## 5. Validation plan (reuses the harness already built this session)

| Gate | How | Pass condition |
|---|---|---|
| Verifier discriminates | the safe/unsafe **A/B** (`/tmp/verifier_ab.py` pattern) | safe parameterized query → **FP**; unsafe concat → **TP** |
| Verifier on real code | DVB audit script | a non-zero, sane FP/suppress rate (not 0/32) |
| Enrichment parses | `enrich_sample.py` pattern over DVB | parse-rate **>80%** (vs ~34% now), accurate, no hallucination |
| Eval Tier 2 | `scripts/eval/run_eval.py --tier verifier` | vs §9: **F1 ≥ 0.70, FP ≤ 25%, recall ≥ 0.60** on curated |
| No regressions | `manage.py test scanner` | stays green |
| Live | re-freeze + in-place swap + DVB rescan | verdicts vary; richer reports appear |

## 6. Risks & mitigations

- **CPU latency** — instruct (no FIM speed tricks) + per-finding calls can be slow; 7B notably so. → keep 3B + `Q4_K_M`; pursue verifier/reporter **batching** (separate follow-up).
- **App size** — pick quant to hold ≈ current size (`q8_0`) or shrink (`Q4_K_M`).
- **Offline build** — must download the HF model once on a networked build host, then offline. Document in `BUILD_MACOS.md`.
- **Shared `_clean_output`** — used by all callers; de-FIM must be validated against verifier + enricher.
- **Chat template / EOS** — must be present in the GGUF or generation won't stop cleanly; verify post-convert.

## 7. Effort & rollout

**~1–1.5 days, no architectural change.** (1) convert 3B-Instruct → GGUF (both quants); (2) de-FIM client + system prompt + optional JSON grammar + prompt tweaks + tests; (3) validate via A/B + eval Tier 2 + enrichment sample (in-place swap); (4) escalate to 7B only if needed; (5) lock quant by size/latency, clean DMG/EXE rebuild, re-run eval baseline, commit.

## 8. Decisions needed

1. **Size/quality:** 3B-Instruct (drop-in, ~same size) vs 7B-Instruct (better, bigger/slower)?
2. **Quant:** `Q4_K_M` (~2 GB, smaller app) vs `Q8_0` (~3.3 GB, matches current, higher fidelity)?
3. **JSON-grammar-constrained decoding** — add it (more robust, a little more client work) or rely on prompt + lenient parser?

---

## 9. Verified research findings & corrected recommendation (2026-05-31)

Done via 3 parallel research agents + direct Hugging Face verification of the load-bearing license claims (the `/deep-research` workflow harness failed; this replaced it).

### 9.1 ⚠️ LICENSE ALERT (verified on Hugging Face — act on this regardless of the swap)
- **Qwen2.5-Coder-3B-Instruct → `qwen-research` (NON-COMMERCIAL)**, verbatim: *"...license ... FOR NON-COMMERCIAL PURPOSES ONLY"*; *"If you are commercially using the Materials, you shall request a license."* No MAU carve-out. The official **3B GGUF repo carries the same tag**, and the general **Qwen2.5-3B-Instruct is also `qwen-research`**.
- **We currently bundle a fine-tune of Qwen2.5-Coder-3B** in a shipped product → **almost certainly outside the license.** Treat as an urgent compliance item: move off the 3B (any quant) and get legal sign-off. *(The base-3B license should be confirmed too, but the 3B size is restricted across the 2.5 line, so assume non-commercial.)*
- **Apache-2.0 (commercial-OK), confirmed:** Coder-Instruct **0.5B / 1.5B / 7B / 14B / 32B**. Only the **3B** is restricted. (72B general = "Qwen License", commercial-OK under 100M MAU — irrelevant to us.)

### 9.2 Primary recommendation — stay in the Qwen2.5-Coder-Instruct family, **Apache sizes only**
Same ChatML template + tokenizer across the whole ladder → **one code path / one prompt**, code-specialized, first-class llama.cpp + GGUF (official + bartowski/unsloth imatrix quants). The swap is a model-file change; the real work is still de-FIM-ing `llm.py` (§4b). Official Pass@1: 7B HumanEval **88.4** / MBPP **83.5** / Aider **51.9**; 1.5B HumanEval 70.7.

### 9.3 Device-tier → variant + quant (all Apache-2.0, ChatML, GGUF; RAM = weights + 4k KV + overhead)
| Tier | Target device | Model | Quant | Disk | RAM to run | CPU tok/s (Apple / x86) |
|---|---|---|---|---|---|---|
| **Low** | old / ≤8 GB laptop | **Qwen2.5-Coder-1.5B-Instruct** | **Q5_K_M/Q6_K** (sub-2B: avoid Q4) | ~1.3 GB | ~2 GB | ~60–120 / ~15–30 |
| **Mid (default)** | typical 8–16 GB laptop | **Qwen2.5-Coder-7B-Instruct** | **Q4_K_M** | ~4.7 GB | ~6 GB | ~15–80 / ~8–15 |
| **High** | workstation 16 GB+ | **Qwen2.5-Coder-14B-Instruct** | Q4_K_M | ~9 GB | ~11 GB | (GPU recommended) |
| **GPU/Pro** | 24 GB+ / dGPU | Qwen2.5-Coder-32B-Instruct | Q4_K_M | ~20 GB | ~22 GB | GPU |

**The 3B-class gap (1.5B → 7B):** the comfortable ~3 GB-RAM "3B" tier is exactly the non-commercial hole. Options to fill it with a clean license: (a) **Qwen3-4B-Instruct (Apache-2.0, same ChatML)** — newest, fills mid-low cleanly, keeps one family; (b) accept a **second family** — **IBM Granite-3.3-2B-Instruct (Apache-2.0, HumanEval 80.5, IFEval 65.8)** is the strongest verified small option but adds a 2nd chat template; (c) just ship 1.5B-low / 7B-mid and skip 3B-class.

### 9.4 One model for BOTH calls? **Yes.** One instruct model serves the verifier and the report enricher — two different prompts, same model, both **grammar-constrained to JSON**. No need for two models.

### 9.5 Make JSON bulletproof (do this with whatever model) — verified llama.cpp support
- `llama-server` supports **GBNF grammars** (`grammar` param) and OpenAI-style **`response_format`** (`{"type":"json_object"}` and `json_schema`). `json_object` is the most build-stable; `json_schema` has been flakier across versions — pin the llama.cpp build and test.
- Grammar constrains *sampling only* — it is NOT injected into the prompt, so still describe the schema in the prompt; and a token-limit cutoff can still truncate JSON → keep generous `max_tokens` + a fail-open parser. Prefer **imatrix** quants (bartowski/unsloth), especially ≤Q4 and at small sizes.

### 9.6 Second-choice families (if Qwen is ruled out)
- **IBM Granite-3.x (Apache-2.0)** — cleanest license + best *verified on-card* small numbers (2B HumanEval 80.5; 8B 89.7), enterprise function-calling; has sub-1B-active MoE for weak hardware. Different template (not a drop-in).
- **Gemma-3 → Gemma-4** — best small-size IFEval (4B = 90.2), broadest ladder; but Gemma-2/3 use a custom license (commercial-OK with strings); **Gemma-4 reportedly moved to Apache-2.0** (verify before relying on it).
- **Phi-4-mini (MIT, 3.8B)** — most permissive license + strong code (HumanEval 74.4) + native function-calling, but **single size** (no ladder).
- **Llama-3.2/3.1** — great ecosystem; custom license (700M-MAU bar won't bite us) + "Built with Llama" attribution; 3B card omits code benchmarks, 1B too weak for tool-use.

### 9.7 Sources (key)
- Coder-3B-Instruct `qwen-research` (verified): https://huggingface.co/Qwen/Qwen2.5-Coder-3B-Instruct · 1.5B/7B Apache: https://huggingface.co/Qwen/Qwen2.5-Coder-1.5B-Instruct , https://huggingface.co/Qwen/Qwen2.5-Coder-7B-Instruct
- Qwen Coder family blog (size↔license): https://qwenlm.github.io/blog/qwen2.5-coder-family/ · Coder Tech Report (benchmarks): https://arxiv.org/abs/2409.12186
- llama.cpp grammars/JSON: https://github.com/ggml-org/llama.cpp/blob/master/grammars/README.md , server README: https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md
- GGUF sizes: bartowski repos (e.g. https://huggingface.co/bartowski/Qwen2.5-Coder-7B-Instruct-GGUF) · Apple-Silicon throughput: https://github.com/ggml-org/llama.cpp/discussions/4167 · quant quality: https://arxiv.org/abs/2409.11055
- Granite-3.3-8B (Apache): https://huggingface.co/ibm-granite/granite-3.3-8b-instruct · Phi-4-mini (MIT): https://huggingface.co/microsoft/Phi-4-mini-instruct · Qwen3 (Apache): https://qwenlm.github.io/blog/qwen3/
