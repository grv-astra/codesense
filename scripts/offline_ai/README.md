# Offline AI engine (Phase 2)

The code-review scanner does NOT load the model in-process. It calls an
OpenAI-compatible HTTP endpoint (`server/scanner/rag/llm.py` → `POST /v1/chat/completions`),
driven entirely by environment variables. For the offline Windows build we
replace the cloud vLLM server with a bundled **llama.cpp `llama-server`** serving
a quantized GGUF of the Astra model. **No backend code change is required.**

What Phase 2 changed in the repo:
- Deleted dead code: `scanner/rag/embeddings.py` (Ollama/LangChain) and
  `scanner/rag/kb.py` (FAISS), plus the tracked `scanner/index.faiss` /
  `scanner/index.pkl` (~41 MB) — none were on the live scan path.
- Dropped `langchain-community` from `requirements.txt`.

## Build-host steps (not runnable in CI sandbox — needs llama.cpp)

1. Build llama.cpp (CPU build is fine): <https://github.com/ggml-org/llama.cpp>
2. Convert + quantize the model:
   ```bash
   LLAMA_CPP=~/llama.cpp QUANT=Q4_K_M \
     scripts/offline_ai/convert_model_to_gguf.sh \
     Astra_Code_reviewer_full/Astra_Code_reviewer_full dist/model
   # -> dist/model/astra-Q4_K_M.gguf  (~2 GB)
   ```
3. Bundle `llama-server(.exe)` + `astra-Q4_K_M.gguf` into the Tauri app
   (`src-tauri/binaries/`, see Phase 6). The Tauri launcher starts it as a sidecar:
   ```
   llama-server --model astra-Q4_K_M.gguf --host 127.0.0.1 --port 8001 \
                --ctx-size 4096 --threads <n_physical_cores> \
                --api-key EMPTY --alias astra-code-reviewer
   ```
4. The launcher sets these env vars for the Django backend (it reads them in `llm.py`):
   ```
   VLLM_BASE_URL=http://127.0.0.1:8001/v1
   VLLM_MODEL=astra-code-reviewer
   VLLM_API_KEY=EMPTY
   VLLM_MAX_MODEL_LEN=4096
   ```

## Performance note
CPU-only inference of a 3B model is slow (minutes for a large repo). Scans run on
background threads with progress polling, and the Tauri tray exposes a
"Pause AI engine" action to free the model's RAM when idle (Phase 6).
