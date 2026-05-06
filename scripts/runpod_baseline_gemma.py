#!/usr/bin/env python3
"""Baseline Gemma 4 4B (google/gemma-4-E4B-it) on the TemRust-* benchmark.

Different from our v5/v6 launchers because Gemma 4 was released May 2026
and isn't supported by our pinned transformers==4.45.2. We use a newer
base image + latest transformers, no LoRA/peft/trl needed (inference only).

The pod runs train_coder.py with --skip-train --out google/gemma-4-E4B-it
which downloads from HF Hub and starts the FastAPI serve mode. We then
hit it with eval/runner from our local box.

H100 SXM5 80GB SECURE @ ~$3.49/hr. Cap 25 min wall clock (no training,
just model load + serve, ~5-8 min boot).
"""
from __future__ import annotations
import os
import sys

import requests

REST = "https://rest.runpod.io/v1"

GPU_TYPE_ID = "NVIDIA H100 80GB HBM3"
CLOUD_TYPE = "SECURE"
# Newer image — Gemma 4 needs transformers >= ~4.55 which needs torch >= 2.5.
IMAGE = "runpod/pytorch:2.8.0-py3.11-cuda12.8.1-cudnn-devel-ubuntu22.04"
HOURLY_RATE = 3.49

GEMMA_MODEL = "google/gemma-4-E4B-it"


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


SERVE_ONLY = r"""
mkdir -p /workspace
cd /workspace
touch /workspace/setup.log

(cd /workspace && python3 -m http.server 8001) >> /workspace/logserver.log 2>&1 &

(
    set -x
    echo "[$(date +%H:%M:%S)] starting Gemma baseline pod setup"
    pip install --no-cache-dir \
        "transformers>=4.55" \
        "accelerate>=1.0" \
        sentencepiece protobuf \
        fastapi uvicorn
    echo "[$(date +%H:%M:%S)] deps installed"
    git clone "https://${GH_TOKEN}@github.com/temm1e-labs/temrust.git" /workspace/temrust
    cd /workspace/temrust
    echo "[$(date +%H:%M:%S)] repo cloned, loading + serving Gemma"
    export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
    # --skip-train + --out points at HF Hub model id, train_coder.py downloads + serves.
    python scripts/train_coder.py \
        --base """ + GEMMA_MODEL + r""" \
        --out """ + GEMMA_MODEL + r""" \
        --data data/clean/sft_wholefile_v4.jsonl \
        --skip-train \
        --serve-after-train \
        --served-name gemma-4-E4B-it
    echo "[$(date +%H:%M:%S)] serve script exited"
) > /workspace/setup.log 2>&1 &

exec tail -f /dev/null
"""


def build_payload() -> dict:
    return {
        "name": "gemma-baseline-4b",
        "imageName": IMAGE,
        "gpuTypeIds": [GPU_TYPE_ID],
        "gpuCount": 1,
        "vcpuCount": 16,
        "containerDiskInGb": 50,
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
        "dockerStartCmd": ["bash", "-lc", SERVE_ONLY],
    }


def main() -> int:
    payload = build_payload()
    print(f"GPU:    {GPU_TYPE_ID} {CLOUD_TYPE}", flush=True)
    print(f"Model:  {GEMMA_MODEL}", flush=True)
    print(f"Image:  {IMAGE}", flush=True)
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
