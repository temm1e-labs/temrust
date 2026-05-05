#!/bin/bash
# Cloud-init smoke test: print hello, push a marker file to HF, terminate.
# Total runtime should be < 1 minute.
set -e

echo "=== Tem-Rust cloud-init smoke test ==="
echo "Pod uptime: $(uptime)"
echo "Disk: $(df -h / | tail -1)"
echo "GPU:"
nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv,noheader || echo "no GPU?"

# Optional: validate HF token works
if [ -n "$HF_TOKEN" ]; then
    curl -s -H "Authorization: Bearer $HF_TOKEN" \
        https://huggingface.co/api/whoami-v2 | head -c 200
    echo ""
fi

echo "=== smoke test complete; terminating ==="
# RunPod will track shutdown if pod kernel halts:
shutdown -h now
