#!/usr/bin/env python3
"""H100 SXM5 80GB variant of runpod_train_coder.py.

Differences from the 5090 launcher:
1. GPU: H100 SXM5 80GB SECURE @ ~$3.49/hr — ~2-3x faster bf16 throughput,
   80GB lets us drop gradient_checkpointing for another ~30% speedup.
2. SFT config: --packing + --no-grad-ckpt — concatenates examples to fill
   4096-token sequences (no padding waste). Total wall time target: ~10-15
   min for the same 355-row corpus.
3. **Log server**: a tiny Python http.server runs BEFORE training on port
   8001, serving /workspace/. This means even if training crashes silently,
   we can fetch /workspace/setup.log via
   `https://<podId>-8001.proxy.runpod.net/setup.log` to debug.

Usage:
    source scripts/load_creds.sh
    python scripts/runpod_train_coder_h100.py
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

# H100 should finish training in 10-15 min with packing enabled. Cap at 30
# min so we fail fast if something goes wrong (vs. the 5090 v1 which sat
# silent for 75 min).
MAX_WAIT_S = 30 * 60


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
# Three concurrent things start:
# 1. Log server on :8001 (Python http.server, serving /workspace/) — starts
#    BEFORE anything else so we can read setup.log even if training crashes.
# 2. Training subshell — pip install, clone, train, merge, serve.
# 3. `exec tail -f /dev/null` keeps the entrypoint alive.
TRAIN_AND_SERVE = r"""
mkdir -p /workspace
cd /workspace
touch /workspace/setup.log

# Log server — runs forever, serves /workspace/ on :8001 so we can fetch
# setup.log via the runpod proxy regardless of training outcome.
(cd /workspace && python3 -m http.server 8001) >> /workspace/logserver.log 2>&1 &

# Training subshell — output to setup.log for retrieval via :8001.
(
    set -x
    echo "[$(date +%H:%M:%S)] starting pod setup"
    pip install --no-cache-dir peft trl accelerate datasets fastapi uvicorn
    echo "[$(date +%H:%M:%S)] deps installed"
    git clone "https://${GH_TOKEN}@github.com/temm1e-labs/temrust.git" /workspace/temrust
    cd /workspace/temrust
    echo "[$(date +%H:%M:%S)] repo cloned, starting training"
    python scripts/train_coder.py \
        --base Qwen/Qwen2.5-Coder-1.5B-Instruct \
        --data data/clean/sft_wholefile_v4.jsonl \
        --out /workspace/merged \
        --epochs 10 \
        --batch-size 8 \
        --grad-accum 1 \
        --lr 2e-5 \
        --lora-r 32 \
        --lora-alpha 64 \
        --max-seq-len 4096 \
        --packing \
        --no-grad-ckpt \
        --serve-after-train
    echo "[$(date +%H:%M:%S)] training script exited"
) > /workspace/setup.log 2>&1 &

# Keep the entrypoint alive regardless of subshell outcome.
exec tail -f /dev/null
"""


def build_payload() -> dict:
    return {
        "name": "temrust-v5-h100",
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


def fetch_log(pod_id: str, max_lines: int = 30) -> str:
    """Pull last N lines of setup.log via the :8001 log server."""
    url = f"https://{pod_id}-8001.proxy.runpod.net/setup.log"
    try:
        r = requests.get(url, timeout=15)
        if r.ok:
            lines = r.text.splitlines()
            return "\n".join(lines[-max_lines:])
    except Exception as e:
        return f"<log fetch err: {e}>"
    return f"<log fetch HTTP {r.status_code}>"


def wait_for_serve(pod_id: str) -> str:
    proxy_url = f"https://{pod_id}-8000.proxy.runpod.net"
    log_url = f"https://{pod_id}-8001.proxy.runpod.net/setup.log"
    t0 = time.time()
    last_log_dump = 0
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
            uptime = runtime_obj.get("uptimeInSeconds", 0)
            ports = runtime_obj.get("ports") or []
            print(f"  [{elapsed}s] status={status} uptime={uptime}s ports={[p.get('privatePort') for p in ports]}", flush=True)
        else:
            print(f"  [{elapsed}s] status={status} runtime=null (image pull / boot)", flush=True)

        # Probe FastAPI directly — /v1/models is the success signal.
        try:
            r = requests.get(f"{proxy_url}/v1/models", timeout=10)
            if r.ok:
                print(f"  FastAPI serving at {proxy_url}", flush=True)
                return proxy_url
        except Exception:
            pass

        # Every 2 min, dump last 10 lines of setup.log via the log server.
        if elapsed - last_log_dump >= 120 and runtime_obj is not None:
            tail = fetch_log(pod_id, max_lines=10)
            print(f"  --- setup.log tail ---\n{tail}\n  --- end tail ---", flush=True)
            last_log_dump = elapsed

        # Fast-fail on stuck image pull (no runtime after 8 min)
        if elapsed >= 8 * 60 and runtime_obj is None:
            raise RuntimeError(f"STUCK: pod {pod_id} runtime=null after {elapsed}s; aborting.")

        time.sleep(30)

    # Timeout — grab final log dump for diagnosis
    final_log = fetch_log(pod_id, max_lines=50)
    raise RuntimeError(f"TIMEOUT: FastAPI never came up within {MAX_WAIT_S}s.\nFinal log:\n{final_log}")


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
    print(f"  pod id:      {pod_id}", flush=True)
    print(f"  api proxy:   https://{pod_id}-8000.proxy.runpod.net", flush=True)
    print(f"  log server:  https://{pod_id}-8001.proxy.runpod.net/setup.log", flush=True)

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
