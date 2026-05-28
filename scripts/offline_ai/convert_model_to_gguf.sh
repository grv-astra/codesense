#!/usr/bin/env bash
# Convert the Astra code-review model (HuggingFace format) to a CPU-friendly,
# quantized GGUF for offline inference via llama.cpp's llama-server.
#
# Run this on a BUILD machine that has llama.cpp checked out and built. The
# resulting .gguf is shipped inside the Tauri bundle; the Django backend never
# loads it directly — it talks to llama-server over HTTP (see README.md).
#
# Usage:
#   LLAMA_CPP=~/llama.cpp QUANT=Q4_K_M \
#     scripts/offline_ai/convert_model_to_gguf.sh \
#     Astra_Code_reviewer_full/Astra_Code_reviewer_full dist/model
set -euo pipefail

MODEL_SRC="${1:-Astra_Code_reviewer_full/Astra_Code_reviewer_full}"   # HF-format dir (config.json + safetensors)
OUT_DIR="${2:-dist/model}"
LLAMA_CPP="${LLAMA_CPP:-$HOME/llama.cpp}"
QUANT="${QUANT:-Q4_K_M}"     # ~2 GB for a 3B model; good CPU quality/size tradeoff

if [ ! -f "$MODEL_SRC/config.json" ]; then
  echo "ERROR: $MODEL_SRC does not look like a HuggingFace model dir (no config.json)" >&2
  exit 1
fi
if [ ! -f "$LLAMA_CPP/convert_hf_to_gguf.py" ]; then
  echo "ERROR: set LLAMA_CPP to a built llama.cpp checkout (convert_hf_to_gguf.py not found)" >&2
  exit 1
fi

mkdir -p "$OUT_DIR"

echo "[1/2] HuggingFace -> GGUF (f16)"
python "$LLAMA_CPP/convert_hf_to_gguf.py" "$MODEL_SRC" \
  --outfile "$OUT_DIR/astra-f16.gguf" --outtype f16

echo "[2/2] Quantize -> $QUANT"
"$LLAMA_CPP/build/bin/llama-quantize" \
  "$OUT_DIR/astra-f16.gguf" "$OUT_DIR/astra-${QUANT}.gguf" "$QUANT"
rm -f "$OUT_DIR/astra-f16.gguf"

echo "GGUF ready: $OUT_DIR/astra-${QUANT}.gguf"
