#!/usr/bin/env python3
"""Check RunPod GPU availability and current account state.

Free — only queries the API catalog and account info, never launches pods.
"""
from __future__ import annotations
import os
import sys

import requests

API = "https://api.runpod.io/graphql"


def gql(query: str, variables: dict | None = None) -> dict:
    token = os.environ["RUNPOD_API_KEY"]
    r = requests.post(
        API,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"query": query, "variables": variables or {}},
        timeout=30,
    )
    if not r.ok:
        print(f"HTTP {r.status_code}: {r.text[:500]}", file=sys.stderr)
        r.raise_for_status()
    data = r.json()
    if "errors" in data:
        raise RuntimeError(data["errors"])
    return data["data"]


def main() -> int:
    if not os.environ.get("RUNPOD_API_KEY"):
        print("ERROR: RUNPOD_API_KEY not set. Source scripts/load_creds.sh first.", file=sys.stderr)
        return 1

    me = gql("query { myself { id email currentSpendPerHr machineQuota } }")["myself"]
    print(f"Account: {me['email']}")
    print(f"  Current spend/hr: ${me['currentSpendPerHr']}")
    print(f"  Machine quota:    {me['machineQuota']}")
    print()

    gpus = gql("""
        query {
            gpuTypes {
                id
                displayName
                memoryInGb
                secureCloud
                communityCloud
                lowestPrice(input: { gpuCount: 1 }) {
                    minimumBidPrice
                    uninterruptablePrice
                }
            }
        }
    """)["gpuTypes"]

    candidates = [g for g in gpus if any(x in g["displayName"] for x in ["A100", "H100", "L40", "RTX 4090"])]
    candidates.sort(key=lambda g: (g["lowestPrice"]["minimumBidPrice"] or 999.0))

    print(f"{'Display Name':40s} {'VRAM':>8s} {'Spot':>8s} {'On-Dem':>8s} {'Cloud':>8s}")
    print("-" * 80)
    for g in candidates[:15]:
        spot = g["lowestPrice"]["minimumBidPrice"]
        ondem = g["lowestPrice"]["uninterruptablePrice"]
        cloud = []
        if g["communityCloud"]: cloud.append("Comm")
        if g["secureCloud"]: cloud.append("Sec")
        cloud_str = "/".join(cloud) or "-"
        spot_s = f"${spot:.2f}" if spot is not None else "N/A"
        ondem_s = f"${ondem:.2f}" if ondem is not None else "N/A"
        print(f"{g['displayName']:40s} {g['memoryInGb']:>6d}GB {spot_s:>8s} {ondem_s:>8s} {cloud_str:>8s}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
