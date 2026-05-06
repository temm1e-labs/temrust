#!/usr/bin/env python3
"""Spin up a RunPod pod (REST API, on-demand), serve a model with vllm,
run our eval, shut down.

Hardened against spend mistakes:
- Every launch requires explicit --gpu, --bid, --model
- Dry-run prints the FULL JSON payload that would be sent
- Hard 30-min wall-clock cap with auto-terminate
- Auto-terminate on any unhandled exception
- Logs launch + termination to BUDGET_LOG.md
"""
from __future__ import annotations
import argparse
import json
import os
import subprocess
import sys
import time
import traceback
from pathlib import Path

import requests

REST = "https://rest.runpod.io/v1"
SCRIPT = Path(__file__).resolve().parent / "cloud_init_eval_vllm.sh"


def rest(method: str, path: str, body: dict | None = None) -> dict | list:
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


def append_budget_log(model: str, hours: float, rate: float, cost: float, prev_total: float, note: str = "") -> None:
    p = Path("BUDGET_LOG.md")
    if not p.exists():
        return
    new_line = (
        f"| {time.strftime('%Y-%m-%d')} | 0 | RunPod baseline {model} ({hours*60:.1f} min){' — ' + note if note else ''} | "
        f"{hours:.3f}h | ${rate:.2f}/hr | ${cost:.3f} | **${prev_total + cost:.3f}** |"
    )
    text = p.read_text().rstrip()
    p.write_text(text + "\n" + new_line + "\n")


def parse_running_total() -> float:
    p = Path("BUDGET_LOG.md")
    if not p.exists():
        return 0.0
    last_total = 0.0
    for line in p.read_text().splitlines():
        if "**$" not in line:
            continue
        try:
            last_total = float(line.split("**$")[1].split("**")[0])
        except Exception:
            continue
    return last_total


def build_payload(args) -> dict:
    """Construct the explicit REST POST /v1/pods payload using vllm/vllm-openai image."""
    extra_args = args.vllm_args.split() if args.vllm_args else []
    return {
        "name": f"temrust-{args.model.replace('/', '__')[:30]}",
        "imageName": args.image,
        "gpuTypeIds": [args.gpu_type_id],
        "gpuCount": 1,
        "vcpuCount": 4,
        # 30GB tight but enough: vllm/vllm-openai uncompressed ~25GB + Qwen3-1.7B ~3.5GB.
        # Community hosts often reject 50GB containerDisk; 30GB widens the host pool.
        "containerDiskInGb": 30,
        "volumeInGb": 0,
        "ports": ["8000/http"],
        "interruptible": False,
        "cloudType": args.cloud_type,
        "supportPublicIp": True,
        "env": {
            "HF_TOKEN": os.environ["HF_TOKEN"],
            "HUGGING_FACE_HUB_TOKEN": os.environ["HF_TOKEN"],
        },
        # vllm/vllm-openai image: ENTRYPOINT is `python -m vllm.entrypoints.openai.api_server`
        # Args after that go via dockerStartCmd.
        "dockerStartCmd": [
            "--model", args.model,
            "--host", "0.0.0.0",
            "--port", "8000",
            # 16384 leaves headroom for prompt + 8K-token thinking + final answer.
            # Qwen3-1.7B supports up to ~40K natively; 16K is the sweet spot for KV-cache size.
            "--max-model-len", "16384",
            "--dtype", "auto",
            *extra_args,
        ],
    }


GQL = "https://api.runpod.io/graphql"


def gql_pod(pod_id: str) -> dict:
    """Read pod state via GraphQL — REST's `runtime` field lags / can stay null
    even after the container is up. GraphQL reflects current container state correctly."""
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
                        machineId
                        machine { gpuDisplayName }
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


def wait_for_endpoint(pod_id: str, max_wait_s: int = 1500, stuck_after_s: int = 480) -> str:
    """Poll pod until vllm is up; return RunPod proxy URL.

    RunPod exposes HTTP ports via `https://<podId>-<privatePort>.proxy.runpod.net`,
    NOT via the (CGNAT) IP shown in the pod state. The REST endpoint's `runtime` field
    is unreliable (can stay null after container is up); use GraphQL.

    Fast-fail: if `runtime` is still null after ``stuck_after_s``, abort. With a known-good
    image tag, image pull + boot completes within ~6 min on RunPod SECURE.
    """
    proxy_url = f"https://{pod_id}-8000.proxy.runpod.net"
    t0 = time.time()
    while time.time() - t0 < max_wait_s:
        try:
            pod = gql_pod(pod_id)
        except Exception as e:
            print(f"  poll err: {e}", file=sys.stderr)
            time.sleep(15)
            continue

        runtime_obj = pod.get("runtime")
        elapsed = int(time.time() - t0)
        status = pod.get("desiredStatus", "?")

        if runtime_obj is not None:
            uptime_s = runtime_obj.get("uptimeInSeconds", 0)
            ports = runtime_obj.get("ports") or []
            print(f"  [{elapsed}s] status={status} uptime={uptime_s}s ports={[p.get('privatePort') for p in ports]} (proxy)", flush=True)
        else:
            print(f"  [{elapsed}s] status={status} runtime=null (image pulling / container starting)", flush=True)

        # Probe the proxy DIRECTLY regardless of GraphQL port state. RunPod's
        # `runtime.ports` and `uptimeInSeconds` can lag or report incorrectly,
        # but if the proxy returns 200 on /v1/models, vllm is genuinely up.
        try:
            r = requests.get(f"{proxy_url}/v1/models", timeout=10)
            if r.ok:
                return proxy_url
        except Exception:
            pass  # 404/502/timeout — vllm not ready yet, keep waiting

        # Fast-fail (image pull): runtime never populated
        if elapsed >= stuck_after_s and runtime_obj is None:
            raise RuntimeError(
                f"STUCK: pod {pod_id} runtime still null after {elapsed}s "
                f"(status={status}). Image pull or container boot failed; aborting."
            )

        # Fast-fail (container crashloop): runtime is set but uptime stays 0 and ports stays null.
        # Healthy containers on RTX 4090 bind port 8000 within ~120s of runtime appearing
        # (model download + vllm load). 240s is generous. This catches "bad host" allocations
        # where the container is created but never actually starts vllm.
        if (
            runtime_obj is not None
            and elapsed >= stuck_after_s // 2  # half the image-pull cap; runtime is up by now
            and runtime_obj.get("uptimeInSeconds", 0) == 0
            and runtime_obj.get("ports") in (None, [])
        ):
            raise RuntimeError(
                f"STUCK: pod {pod_id} runtime set but uptime=0 and ports=null after {elapsed}s. "
                f"Container is crashlooping or never started vllm; aborting."
            )

        time.sleep(20)
    raise TimeoutError(f"vllm proxy not responding at {proxy_url} after {max_wait_s}s")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, help="HF model id, e.g. Qwen/Qwen3-1.7B")
    ap.add_argument("--gpu-type-id", default="NVIDIA GeForce RTX 3090",
                    help="Exact RunPod GPU type id (use scripts/runpod_check.py)")
    ap.add_argument("--bid", type=float, default=0.30, help="Max $/hr (informational; on-demand uses fixed price)")
    ap.add_argument("--min-vram-gb", type=int, default=24)
    ap.add_argument("--vllm-args", default="")
    ap.add_argument("--image", default="vllm/vllm-openai:v0.20.1",
                    help="Docker image with vllm pre-installed; entrypoint is the OpenAI server. "
                         "v0.20.1 is the latest verified tag on dockerhub as of 2026-05-04.")
    ap.add_argument("--max-runtime-min", type=int, default=20,
                    help="Hard wall-clock cap; pod terminated even if eval not done")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--dry-run", action="store_true",
                    help="Print payload that would be sent; no API call")
    ap.add_argument("--max-cost-cap", type=float, default=1.0,
                    help="Refuse to launch if pod could exceed this many $ at max-runtime")
    ap.add_argument("--cloud-type", default="SECURE", choices=["SECURE", "COMMUNITY"],
                    help="RunPod cloud pool. SECURE = datacenter, COMMUNITY = individual hosts")
    ap.add_argument("--stuck-fail-s", type=int, default=240,
                    help="Abort if pod has no runtime/publicIp after this many seconds")
    args = ap.parse_args()

    if not os.environ.get("RUNPOD_API_KEY"):
        print("ERROR: RUNPOD_API_KEY not set.", file=sys.stderr)
        return 1
    if not os.environ.get("HF_TOKEN"):
        print("ERROR: HF_TOKEN not set.", file=sys.stderr)
        return 1
    if not SCRIPT.exists():
        print(f"ERROR: {SCRIPT} not found", file=sys.stderr)
        return 1

    payload = build_payload(args)
    # Don't print HF_TOKEN to stdout
    safe_payload = json.loads(json.dumps(payload))
    for k in list(safe_payload.get("env", {}).keys()):
        if "TOKEN" in k:
            safe_payload["env"][k] = "<redacted>"
    print("=== Payload ===")
    print(json.dumps(safe_payload, indent=2))

    # Cost cap check
    max_cost = (args.max_runtime_min / 60) * args.bid
    if max_cost > args.max_cost_cap:
        print(f"ABORT: max possible cost ${max_cost:.2f} > cap ${args.max_cost_cap:.2f}", file=sys.stderr)
        return 1
    print(f"Max possible spend at cap: ${max_cost:.2f}")

    if args.dry_run:
        print("[DRY RUN] no API call made")
        return 0

    pod = rest("POST", "/pods", payload)
    pod_id = pod["id"]
    cost_per_hr = pod.get("costPerHr") or args.bid
    print(f"\nLaunched pod: {pod_id} (cost ${cost_per_hr}/hr)")

    # Re-check cost cap against the ACTUAL price (not the bid). RunPod sometimes
    # charges more than the catalog "lowest price" for a given GPU type. If the
    # real rate × max-runtime exceeds the cap, terminate now and abort.
    actual_max_cost = (args.max_runtime_min / 60) * float(cost_per_hr)
    if actual_max_cost > args.max_cost_cap * 1.20:  # 20% headroom; otherwise abort
        print(
            f"ABORT (post-launch): real rate ${cost_per_hr}/hr × {args.max_runtime_min}min "
            f"= ${actual_max_cost:.2f} exceeds cap ${args.max_cost_cap:.2f}. Terminating.",
            file=sys.stderr,
        )
        try:
            rest("DELETE", f"/pods/{pod_id}")
        except Exception:
            pass
        return 1

    t0 = time.time()
    eval_ok = False
    try:
        base_url = wait_for_endpoint(pod_id, max_wait_s=args.max_runtime_min * 60, stuck_after_s=args.stuck_fail_s)
        print(f"vllm endpoint: {base_url}")

        out_path = Path("eval/results") / f"{args.model.replace('/', '__')}__{int(time.time())}.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)

        cmd = [
            sys.executable, "-m", "eval.runner",
            "--model", args.model,
            "--provider", "vllm",
            "--base-url", base_url,
            "--out", str(out_path),
        ]
        if args.limit:
            cmd.extend(["--limit", str(args.limit)])
        print(f"Running: {' '.join(cmd)}")
        result = subprocess.run(cmd, env={**os.environ, "VLLM_BASE_URL": base_url})
        eval_ok = result.returncode == 0
    except Exception:
        print("ERROR during eval — terminating pod:", file=sys.stderr)
        traceback.print_exc()
    finally:
        elapsed_h = (time.time() - t0) / 3600
        try:
            rest("DELETE", f"/pods/{pod_id}")
            print(f"Pod {pod_id} terminated. Wall: {elapsed_h*60:.1f} min")
        except Exception as e:
            print(f"WARN: terminate failed: {e}", file=sys.stderr)
        cost = elapsed_h * cost_per_hr
        prev = parse_running_total()
        append_budget_log(args.model, elapsed_h, cost_per_hr, cost, prev,
                          note="OK" if eval_ok else "FAILED")

    return 0 if eval_ok else 1


if __name__ == "__main__":
    sys.exit(main())
