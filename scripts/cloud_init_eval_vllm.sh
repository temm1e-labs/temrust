#!/bin/bash
# Cloud-init for a RunPod baseline-eval pod.
#
# Pod startup:
#   1. Install vllm + dependencies
#   2. Serve $MODEL_ID on port 8000 (OpenAI-compatible)
#   3. Pod stays alive serving until terminated externally
#
# The local-side eval/runner.py hits the public IP. When the eval is done,
# the launcher script terminates the pod via RunPod API.
#
# Required env vars:
#   MODEL_ID  — HF model id (e.g. Qwen/Qwen3-1.7B-Base)
#   HF_TOKEN  — for downloading gated/private models
#
# Optional:
#   VLLM_ARGS — extra args (e.g. --quantization bitsandbytes)

set -e

apt-get update -qq && apt-get install -qq -y curl

pip install --quiet --upgrade pip
pip install --quiet "vllm>=0.7" "huggingface_hub>=0.27"

huggingface-cli login --token "$HF_TOKEN" --add-to-git-credential 2>/dev/null || true

echo "=== Tem-Rust eval pod: serving $MODEL_ID ==="
nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv,noheader

# Serve. --max-model-len 8192 keeps memory low for small models.
# vllm exits if it can't allocate; that's OK — we'll see in logs.
exec python -m vllm.entrypoints.openai.api_server \
    --model "$MODEL_ID" \
    --host 0.0.0.0 \
    --port 8000 \
    --max-model-len 8192 \
    --dtype auto \
    $VLLM_ARGS
