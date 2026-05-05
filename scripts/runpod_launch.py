#!/usr/bin/env python3
"""Launch a RunPod GPU instance with auto-shutdown for training/inference.

Pattern:
1. Provision pod via API with a startup script (runs as docker entrypoint)
2. Startup script: clones repo, runs work, pushes results, terminates self
3. Local script polls every 5 min via GraphQL until pod is gone or output is ready
4. All transactions logged to BUDGET_LOG.md

Usage:
    python scripts/runpod_launch.py \\
        --gpu "RTX 4090" \\
        --bid 0.20 \\
        --hours-max 4 \\
        --task scripts/cloud_init_train_v0.sh
"""
from __future__ import annotations
import argparse
import json
import os
import sys
import time
from pathlib import Path

import requests

API = "https://api.runpod.io/graphql"


def gql(query: str, variables: dict | None = None) -> dict:
    token = os.environ["RUNPOD_API_KEY"]
    r = requests.post(
        API,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"query": query, "variables": variables or {}},
        timeout=60,
    )
    if not r.ok:
        raise RuntimeError(f"RunPod HTTP {r.status_code}: {r.text[:300]}")
    data = r.json()
    if "errors" in data:
        raise RuntimeError(data["errors"])
    return data["data"]


def find_gpu_id(display_name: str) -> str:
    """Return the RunPod GPU type id for a given display name."""
    gpus = gql("""
        query { gpuTypes { id displayName memoryInGb communityCloud secureCloud } }
    """)["gpuTypes"]
    matches = [g for g in gpus if g["displayName"] == display_name]
    if not matches:
        raise ValueError(f"No GPU matching '{display_name}'. Available: {[g['displayName'] for g in gpus[:10]]}...")
    return matches[0]["id"]


def launch_spot(gpu_id: str, max_bid: float, image: str, env: dict, name: str) -> str:
    """Launch a community-cloud spot pod. Returns pod id."""
    mutation = """
    mutation Launch($input: PodRentInterruptableInput!) {
        podRentInterruptable(input: $input) { id desiredStatus machineId costPerHr imageName }
    }
    """
    env_list = [{"key": k, "value": v} for k, v in env.items()]
    variables = {
        "input": {
            "name": name,
            "imageName": image,
            "gpuTypeId": gpu_id,
            "gpuCount": 1,
            "containerDiskInGb": 50,
            "volumeInGb": 0,
            "minMemoryInGb": 16,
            "minVcpuCount": 4,
            "ports": "22/tcp",
            "bidPerGpu": max_bid,
            "cloudType": "COMMUNITY",
            "env": env_list,
        }
    }
    result = gql(mutation, variables)
    return result["podRentInterruptable"]["id"]


def get_pod_status(pod_id: str) -> dict:
    return gql(
        """query Pod($id: String!) { pod(input: {podId: $id}) { id desiredStatus runtime { uptimeInSeconds } costPerHr } }""",
        {"id": pod_id},
    )["pod"]


def terminate(pod_id: str) -> None:
    gql(
        """mutation Term($id: String!) { podTerminate(input: {podId: $id}) }""",
        {"id": pod_id},
    )


def append_budget_log(line: str) -> None:
    p = Path("BUDGET_LOG.md")
    if p.exists():
        p.write_text(p.read_text().rstrip() + "\n" + line + "\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gpu", default="RTX 4090", help="Display name from runpod_check.py")
    ap.add_argument("--bid", type=float, default=0.20, help="Max bid $/hr")
    ap.add_argument("--hours-max", type=float, default=2.0, help="Hard wall-clock limit")
    ap.add_argument("--task-script", required=True, help="Cloud-init bash script path (local)")
    ap.add_argument("--name", default="temrust", help="Pod name prefix")
    ap.add_argument("--image", default="runpod/pytorch:2.6.0-py3.11-cuda12.4.1-devel-ubuntu22.04",
                    help="Docker image")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not os.environ.get("RUNPOD_API_KEY"):
        print("ERROR: RUNPOD_API_KEY not set.", file=sys.stderr)
        return 1

    task_script_path = Path(args.task_script)
    if not task_script_path.exists():
        print(f"ERROR: task script {task_script_path} not found", file=sys.stderr)
        return 1

    if args.dry_run:
        print(f"[DRY RUN] Would launch {args.gpu} at ${args.bid}/hr max for {args.hours_max}hr")
        print(f"  task: {task_script_path}")
        return 0

    gpu_id = find_gpu_id(args.gpu)
    print(f"GPU id: {gpu_id} ({args.gpu})")

    # Pass the cloud-init script content via env var (or use a public gist URL)
    task_content = task_script_path.read_text()
    env = {
        "HF_TOKEN": os.environ["HF_TOKEN"],
        "GH_TOKEN": os.environ["GH_TOKEN"],
        "TOGETHER_API_KEY": os.environ.get("TOGETHER_API_KEY", ""),
        "TASK_SCRIPT_B64": __import__("base64").b64encode(task_content.encode()).decode(),
    }
    pod_id = launch_spot(gpu_id, args.bid, args.image, env, args.name)
    print(f"Launched pod: {pod_id}")

    # Append to budget log
    append_budget_log(
        f"| {time.strftime('%Y-%m-%d')} | 0 | RunPod {args.gpu} spot pod {pod_id[:12]} | (running) | ${args.bid:.2f}/hr | TBD | TBD |"
    )

    # Poll until done or hard limit
    t0 = time.time()
    poll_interval = 30
    while time.time() - t0 < args.hours_max * 3600:
        try:
            status = get_pod_status(pod_id)
        except Exception as e:
            print(f"  poll error: {e}", file=sys.stderr)
            time.sleep(poll_interval)
            continue
        desired = status.get("desiredStatus")
        runtime = (status.get("runtime") or {}).get("uptimeInSeconds", 0)
        elapsed = time.time() - t0
        print(f"  [{elapsed/60:>5.1f}min] status={desired} uptime={runtime}s")
        if desired == "EXITED" or desired is None:
            print(f"Pod terminated. Wall-clock: {elapsed/60:.1f} min")
            return 0
        time.sleep(poll_interval)

    # Hit hard limit; terminate
    print(f"Hard limit {args.hours_max}h reached — terminating pod {pod_id}")
    terminate(pod_id)
    return 1


if __name__ == "__main__":
    sys.exit(main())
