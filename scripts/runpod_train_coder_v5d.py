#!/usr/bin/env python3
"""v5d (distill) launcher — trains on ensemble-distilled SFT mix.

Identical hyperparams to v5 (r=32, 10 epochs, lr=2e-5) — the ONLY change is
the training data file: sft_distill_v5_mix.jsonl instead of sft_wholefile_v4.jsonl.
The mix has 13 rows where v4-or-v5's cargo-verified output replaces the original
(unverified) PR-fix target. The other 342 rows are unchanged. Controlled
comparison.

H100 SXM5 80GB SECURE @ ~$3.49/hr. Cap 30 min wall clock.
"""
from __future__ import annotations
import os
import sys
import time

import requests

REST = "https://rest.runpod.io/v1"
GQL = "https://api.runpod.io/graphql"

GPU_TYPE_ID = "NVIDIA H100 80GB HBM3"
CLOUD_TYPE = "SECURE"
IMAGE = "runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04"
HOURLY_RATE = 3.49
MAX_WAIT_S = 30 * 60


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


def gql_pod(pod_id: str) -> dict:
    token = os.environ["RUNPOD_API_KEY"]
    r = requests.post(GQL,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={
            "query": "query Pod($id: String!) { pod(input: { podId: $id }) { id desiredStatus runtime { uptimeInSeconds ports { privatePort publicPort type isIpPublic } } } }",
            "variables": {"id": pod_id},
        }, timeout=30,
    )
    r.raise_for_status()
    return r.json().get("data", {}).get("pod") or {}


TRAIN_AND_SERVE = r"""
mkdir -p /workspace
cd /workspace
touch /workspace/setup.log

(cd /workspace && python3 -m http.server 8001) >> /workspace/logserver.log 2>&1 &

(
    set -x
    echo "[$(date +%H:%M:%S)] starting v5d pod setup"
    pip install --no-cache-dir \
        "transformers==4.45.2" \
        "peft==0.13.2" \
        "trl==0.11.4" \
        "accelerate==1.0.1" \
        "datasets==3.0.2" \
        "rich>=13" \
        sentencepiece protobuf \
        fastapi uvicorn
    echo "[$(date +%H:%M:%S)] deps installed"
    git clone "https://${GH_TOKEN}@github.com/temm1e-labs/temrust.git" /workspace/temrust
    cd /workspace/temrust
    echo "[$(date +%H:%M:%S)] repo cloned, starting v5d training"
    export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
    python scripts/train_coder.py \
        --base Qwen/Qwen2.5-Coder-1.5B-Instruct \
        --data data/clean/sft_distill_v5_mix.jsonl \
        --out /workspace/merged \
        --epochs 10 \
        --batch-size 4 \
        --grad-accum 2 \
        --lr 2e-5 \
        --lora-r 32 \
        --lora-alpha 64 \
        --max-seq-len 4096 \
        --packing \
        --served-name tem-rust-v5d \
        --serve-after-train
    echo "[$(date +%H:%M:%S)] training script exited"
) > /workspace/setup.log 2>&1 &

exec tail -f /dev/null
"""


def build_payload() -> dict:
    return {
        "name": "temrust-v5d",
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
        "dockerStartCmd": ["bash", "-lc", TRAIN_AND_SERVE],
    }


def main() -> int:
    payload = build_payload()
    print(f"GPU:    {GPU_TYPE_ID} {CLOUD_TYPE}", flush=True)
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
