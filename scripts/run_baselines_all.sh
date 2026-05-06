#!/bin/bash
# Run all Phase 0 baselines in sequence, one RunPod pod per model.
#
# Each model gets a fresh pod because vllm loads only one model at a time.
# Pod auto-terminates on completion, success, or 18-min wall cap.
#
# Usage:
#   bash scripts/run_baselines_all.sh
#
# Stop early: Ctrl-C — the active pod will be terminated by the launcher's
# finally block. To skip a model, set SKIP="<model1> <model2>" env var.
set -e

cd "$(dirname "$0")/.."
source scripts/load_creds.sh || true   # ignore rc=1 false-positive in load_creds.sh

# 1.7B / 1.5B class — primary comparison set for Tem-Rust-1.7B
MODELS_24GB=(
    "Qwen/Qwen3-1.7B"
    "Qwen/Qwen3-1.7B-Base"
    "Qwen/Qwen2.5-Coder-1.5B"
    "Qwen/Qwen2.5-Coder-1.5B-Instruct"
    "deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B"
)

# 3B class — Qwen2.5-Coder-3B-Instruct is the bar to beat
MODELS_3B=(
    "Qwen/Qwen2.5-Coder-3B-Instruct"
    "Qwen/Qwen2.5-Coder-3B"
)

# 7B class — stretch comparison; needs more VRAM but RTX 4090 has 24GB
MODELS_7B=(
    "Qwen/Qwen2.5-Coder-7B-Instruct"
)

ALL_MODELS=("${MODELS_24GB[@]}" "${MODELS_3B[@]}" "${MODELS_7B[@]}")

PASS=()
FAIL=()
for m in "${ALL_MODELS[@]}"; do
    if [[ " $SKIP " == *" $m "* ]]; then
        echo ">>> SKIP $m"
        continue
    fi
    echo "================================================================="
    echo ">>> Baseline: $m"
    echo "================================================================="
    if .venv/bin/python scripts/runpod_baseline.py \
        --model "$m" \
        --gpu-type-id "NVIDIA GeForce RTX 4090" \
        --bid 0.69 \
        --max-runtime-min 18 \
        --max-cost-cap 0.25 \
        --cloud-type SECURE \
        --stuck-fail-s 480; then
        PASS+=("$m")
    else
        FAIL+=("$m")
        echo ">>> Baseline FAILED for $m, continuing to next..."
    fi
    # Pause between pods to let RunPod settle
    sleep 5
done

echo
echo "================================================================="
echo "BASELINES SUMMARY"
echo "================================================================="
echo "PASSED (${#PASS[@]}):"
for m in "${PASS[@]}"; do echo "  ✓ $m"; done
echo "FAILED (${#FAIL[@]}):"
for m in "${FAIL[@]}"; do echo "  ✗ $m"; done
