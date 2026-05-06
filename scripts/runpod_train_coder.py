#!/usr/bin/env python3
"""Provision a RunPod GPU pod that trains Tem-Rust v5 on Qwen2.5-Coder-1.5B,
then serves the merged model via vllm. Returns the proxy URL.

The dockerStartCmd installs deps, clones the temrust repo (private, via
GH_TOKEN), runs `scripts/train_coder.py`, then launches vllm.

Image: a CUDA-capable PyTorch image. We use `runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04`
which has bash as entrypoint (so we can run a multi-step shell command) and
PyTorch + CUDA preinstalled, keeping pip-install latency low.

Usage:
    source scripts/load_creds.sh
    python scripts/runpod_train_coder.py
        # → prints proxy URL once vllm is serving
"""
from __future__ import annotations
import os
import sys
import time

import requests

REST = "https://rest.runpod.io/v1"
GQL = "https://api.runpod.io/graphql"

# RTX 5090 SECURE — reliable boot (RTX 4090 SECURE pool was flaky in v0/v1).
GPU_TYPE_ID = "NVIDIA GeForce RTX 5090"
CLOUD_TYPE = "SECURE"
IMAGE = "runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04"
HOURLY_RATE = 0.99  # USD/hr

# Hard cap. Training (10 epochs × 355 ex) ≈ 30-60 min on a 5090; vllm
# serve adds 2-3 min model load. Eval from local takes another ~3 min.
# 75 min cap covers everything with margin.
MAX_WAIT_S = 75 * 60


def rest(method: str, path: str, body: dict | None = None) -> dict:
    token = os.environ["RUNPOD_API_KEY"]
    r = requests.request(
        method,
        f"{REST}{path}",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json=body,
        timeout=60,
    )
    if not r.ok:
        raise RuntimeError(f"RunPod REST {method} {path} HTTP {r.status_code}: {r.text[:300]}")
    if r.status_code == 204:
        return {}
    return r.json()


def gql_pod(pod_id: str) -> dict:
    token = os.environ["RUNPOD_API_KEY"]
    r = requests.post(
        GQL,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={
            "query": """
                query Pod($id: String!) {
                    pod(input: { podId: $id }) {
                        id
                        desiredStatus
                        runtime { uptimeInSeconds ports { privatePort publicPort type isIpPublic } }
                    }
                }
            """,
            "variables": {"id": pod_id},
        },
        timeout=30,
    )
    r.raise_for_status()
    return r.json().get("data", {}).get("pod") or {}


# Bash command run as the pod entrypoint. Single string passed to `bash -lc`.
# - Installs SFT deps (peft, trl, bitsandbytes, accelerate, datasets) and vllm
# - Clones the private temrust repo via GH_TOKEN
# - Runs the training script
# - Launches vllm serving the merged model
TRAIN_AND_SERVE = r"""
set -ex
cd /workspace
echo "[$(date +%H:%M:%S)] starting pod setup"
pip install --quiet --no-cache-dir transformers==4.46.0 peft==0.13.2 trl==0.12.0 accelerate==1.1.0 datasets==3.0.2 bitsandbytes
echo "[$(date +%H:%M:%S)] sft deps installed"
pip install --quiet --no-cache-dir vllm==0.6.3
echo "[$(date +%H:%M:%S)] vllm installed"

# Clone private temrust repo (data + scripts)
git clone "https://${GH_TOKEN}@github.com/temm1e-labs/temrust.git" /workspace/temrust
cd /workspace/temrust
echo "[$(date +%H:%M:%S)] repo cloned"

# Train (single GPU, ~30-60 min on a 5090 for 355 ex × 10 epochs)
python scripts/train_coder.py \
    --base Qwen/Qwen2.5-Coder-1.5B-Instruct \
    --data data/clean/sft_wholefile_v4.jsonl \
    --out /workspace/merged \
    --epochs 10 \
    --batch-size 4 \
    --grad-accum 2 \
    --lr 2e-5 \
    --lora-r 32 \
    --lora-alpha 64 \
    --max-seq-len 8192 2>&1 | tee /workspace/train.log

echo "[$(date +%H:%M:%S)] training done, starting vllm"

# Serve merged model — vllm without --enable-lora is more stable than the
# LoRA-enabled path. Trade-off: ~3GB extra disk, fine on 30GB containerDisk.
exec python -m vllm.entrypoints.openai.api_server \
    --model /workspace/merged \
    --served-model-name tem-rust-v5 \
    --host 0.0.0.0 \
    --port 8000 \
    --max-model-len 16384 \
    --dtype auto
"""


def build_payload() -> dict:
    return {
        "name": "temrust-v5-train",
        "imageName": IMAGE,
        "gpuTypeIds": [GPU_TYPE_ID],
        "gpuCount": 1,
        "vcpuCount": 8,
        "containerDiskInGb": 50,  # need room for: vllm install ~6GB + base model ~3GB + merged ~3GB + cache
        "volumeInGb": 0,
        "ports": ["8000/http"],
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


def wait_for_serve(pod_id: str) -> str:
    proxy_url = f"https://{pod_id}-8000.proxy.runpod.net"
    t0 = time.time()
    last_uptime = 0
    while time.time() - t0 < MAX_WAIT_S:
        elapsed = int(time.time() - t0)
        try:
            pod = gql_pod(pod_id)
        except Exception as e:
            print(f"  [{elapsed}s] poll err: {e}", file=sys.stderr, flush=True)
            time.sleep(20)
            continue

        runtime_obj = pod.get("runtime")
        status = pod.get("desiredStatus", "?")
        if runtime_obj is not None:
            last_uptime = runtime_obj.get("uptimeInSeconds", 0)
            ports = runtime_obj.get("ports") or []
            print(f"  [{elapsed}s] status={status} uptime={last_uptime}s ports={[p.get('privatePort') for p in ports]}", flush=True)
        else:
            print(f"  [{elapsed}s] status={status} runtime=null (image pull / boot)", flush=True)

        # Probe proxy directly — vllm's /v1/models is the success signal.
        try:
            r = requests.get(f"{proxy_url}/v1/models", timeout=10)
            if r.ok:
                print(f"  vllm serving at {proxy_url}", flush=True)
                return proxy_url
        except Exception:
            pass

        # Fast-fail on stuck image pull (no runtime after 8 min)
        if elapsed >= 8 * 60 and runtime_obj is None:
            raise RuntimeError(f"STUCK: pod {pod_id} runtime=null after {elapsed}s; aborting.")

        time.sleep(30)

    raise RuntimeError(f"TIMEOUT: vllm never came up within {MAX_WAIT_S}s")


def main() -> int:
    payload = build_payload()
    print(f"GPU:    {GPU_TYPE_ID} {CLOUD_TYPE}", flush=True)
    print(f"Image:  {IMAGE}", flush=True)
    print(f"Rate:   ${HOURLY_RATE}/hr", flush=True)
    print(f"Cap:    {MAX_WAIT_S//60} min wall clock = ~${HOURLY_RATE * MAX_WAIT_S/3600:.2f}", flush=True)
    print(flush=True)

    print("=== launching pod ===", flush=True)
    pod = rest("POST", "/pods", payload)
    pod_id = pod.get("id")
    if not pod_id:
        raise RuntimeError(f"no pod id in response: {pod}")
    print(f"  pod id: {pod_id}", flush=True)
    print(f"  proxy:  https://{pod_id}-8000.proxy.runpod.net", flush=True)

    try:
        proxy_url = wait_for_serve(pod_id)
        print(f"\n=== READY ===", flush=True)
        print(f"pod_id={pod_id}", flush=True)
        print(f"proxy_url={proxy_url}", flush=True)
        print(f"\nNow run:", flush=True)
        print(f"  python -m eval.runner --model tem-rust-v5 --provider vllm --base-url {proxy_url} \\", flush=True)
        print(f"    --out eval/results/tem-rust-v5__$(date +%s).json", flush=True)
        print(f"\nWhen done:", flush=True)
        print(f"  curl -X POST -H 'Authorization: Bearer $RUNPOD_API_KEY' {REST}/pods/{pod_id}/stop", flush=True)
        return 0
    except Exception as e:
        print(f"\nFAIL: {e}", file=sys.stderr, flush=True)
        print(f"  terminating pod {pod_id}", file=sys.stderr, flush=True)
        try:
            rest("POST", f"/pods/{pod_id}/stop")
        except Exception as e2:
            print(f"  stop failed: {e2}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
