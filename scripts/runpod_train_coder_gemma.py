#!/usr/bin/env python3
"""v7-Gemma launcher — train Gemma 4 E4B (4B params) with v5 SFT pipeline.

Different stack from v5/v6 launchers because Gemma 4 was released May 2026
and isn't supported by transformers 4.45.2. Newer compatible pin:

  transformers>=4.55  (Gemma 4 architecture support)
  peft>=0.14          (compat with new transformers)
  trl>=0.13           (compat with new transformers, supports tokenizer/processing_class union)
  accelerate>=1.5
  datasets>=3.5

Image: runpod/pytorch:2.8.0 (torch 2.8 needed for transformers 4.55+).

Hyperparameters identical to v5 (r=32 alpha=64, 10 epochs, lr=2e-5,
packing, max_seq_len=4096) — controlled comparison: only the base changes.

H100 SXM5 80GB SECURE @ ~$3.49/hr. Cap 60 min wall (Gemma 4B is ~2.7x v5's
1.5B in compute).
"""
from __future__ import annotations
import os
import sys

import requests

REST = "https://rest.runpod.io/v1"

GPU_TYPE_ID = "NVIDIA H100 80GB HBM3"
CLOUD_TYPE = "SECURE"
IMAGE = "runpod/pytorch:2.8.0-py3.11-cuda12.8.1-cudnn-devel-ubuntu22.04"
HOURLY_RATE = 3.49
MAX_WAIT_S = 60 * 60

GEMMA_BASE = "google/gemma-4-E4B-it"


def rest(method: str, path: str, body: dict | None = None) -> dict:
    token = os.environ["RUNPOD_API_KEY"]
    r = requests.request(
        method, f"{REST}{path}",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json=body, timeout=60,
    )
    if not r.ok:
        raise RuntimeError(f"RunPod REST {method} {path} HTTP {r.status_code}: {r.text[:300]}")
    if r.status_code == 204:
        return {}
    return r.json()


TRAIN_AND_SERVE = r"""
mkdir -p /workspace
cd /workspace
touch /workspace/setup.log

(cd /workspace && python3 -m http.server 8001) >> /workspace/logserver.log 2>&1 &

(
    set -x
    echo "[$(date +%H:%M:%S)] starting v7-Gemma pod setup"
    pip install --no-cache-dir \
        "transformers>=4.55,<4.60" \
        "peft>=0.14" \
        "trl>=0.13" \
        "accelerate>=1.5" \
        "datasets>=3.5" \
        "rich>=13" \
        sentencepiece protobuf \
        fastapi uvicorn
    echo "[$(date +%H:%M:%S)] deps installed"
    git clone "https://${GH_TOKEN}@github.com/temm1e-labs/temrust.git" /workspace/temrust
    cd /workspace/temrust
    echo "[$(date +%H:%M:%S)] repo cloned, starting v7-Gemma training"
    export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
    python scripts/train_coder.py \
        --base """ + GEMMA_BASE + r""" \
        --data data/clean/sft_wholefile_v4.jsonl \
        --out /workspace/merged \
        --epochs 10 \
        --batch-size 2 \
        --grad-accum 4 \
        --lr 2e-5 \
        --lora-r 32 \
        --lora-alpha 64 \
        --max-seq-len 4096 \
        --packing \
        --served-name temrust-gemma-4b \
        --serve-after-train
    echo "[$(date +%H:%M:%S)] training script exited"
) > /workspace/setup.log 2>&1 &

exec tail -f /dev/null
"""


def build_payload() -> dict:
    return {
        "name": "temrust-gemma-4b",
        "imageName": IMAGE,
        "gpuTypeIds": [GPU_TYPE_ID],
        "gpuCount": 1,
        "vcpuCount": 16,
        "containerDiskInGb": 60,  # Gemma weights ~8GB + working space
        "volumeInGb": 0,
        "ports": ["8000/http", "8001/http"],
        "interruptible": False,
        "cloudType": CLOUD_TYPE,
        "supportPublicIp": True,
        "env": {
            "HF_TOKEN": os.environ["HF_TOKEN"],
            "HUGGING_FACE_HUB_TOKEN": os.environ["HF_TOKEN"],
            "GH_TOKEN": os.environ["GH_TOKEN"],
        },
        "dockerStartCmd": ["bash", "-lc", TRAIN_AND_SERVE],
    }


def main() -> int:
    payload = build_payload()
    print(f"GPU:    {GPU_TYPE_ID} {CLOUD_TYPE}", flush=True)
    print(f"Base:   {GEMMA_BASE}", flush=True)
    print(f"Image:  {IMAGE}", flush=True)
    print(f"Cap:    {MAX_WAIT_S//60} min wall = ~${HOURLY_RATE * MAX_WAIT_S/3600:.2f}", flush=True)
    print("=== launching pod ===", flush=True)
    pod = rest("POST", "/pods", payload)
    pod_id = pod.get("id")
    if not pod_id:
        raise RuntimeError(f"no pod id: {pod}")
    print(f"  pod id:      {pod_id}", flush=True)
    print(f"  api proxy:   https://{pod_id}-8000.proxy.runpod.net", flush=True)
    print(f"  log server:  https://{pod_id}-8001.proxy.runpod.net/setup.log", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
