#!/usr/bin/env python3
"""Find Together AI models that ACTUALLY work serverless (no dedicated endpoint required).

Many models in the catalog have $0/$0 pricing but require dedicated endpoints.
True serverless models have actual non-zero pricing.
"""
from __future__ import annotations
import json
import os
import sys

import requests

API = "https://api.together.xyz/v1"


def main() -> int:
    token = os.environ.get("TOGETHER_API_KEY")
    if not token:
        print("ERROR: TOGETHER_API_KEY not set.", file=sys.stderr)
        return 1

    r = requests.get(f"{API}/models", headers={"Authorization": f"Bearer {token}"}, timeout=30)
    r.raise_for_status()
    models = r.json()

    # Heuristic: serverless models have non-zero pricing.input
    serverless = []
    for m in models:
        pricing = m.get("pricing") or {}
        if not isinstance(pricing, dict):
            continue
        in_p = pricing.get("input")
        if in_p is None or in_p == 0:
            continue
        if any(t in m["id"].lower() for t in ("qwen", "deepseek", "llama")):
            serverless.append({
                "id": m["id"],
                "context": m.get("context_length", "?"),
                "in": in_p,
                "out": pricing.get("output", "?"),
                "type": m.get("type", "?"),
            })

    serverless.sort(key=lambda m: (m["in"], m["id"]))

    print(f"Serverless candidate teachers + base baselines (cost-effective):\n")
    print(f"{'Model':70s} {'ctx':>8s}  {'in/Mtok':>10s} {'out/Mtok':>10s}")
    print("-" * 105)
    for m in serverless:
        print(f"{m['id']:70s} {str(m['context']):>8s}  ${m['in']:>8.3f}  ${m['out']:>8.3f}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
