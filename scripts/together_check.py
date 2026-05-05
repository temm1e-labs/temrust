#!/usr/bin/env python3
"""Check Together AI account access and identify candidate teachers."""
from __future__ import annotations
import os
import sys

import requests

API = "https://api.together.xyz/v1"


def main() -> int:
    token = os.environ.get("TOGETHER_API_KEY")
    if not token:
        print("ERROR: TOGETHER_API_KEY not set. Source scripts/load_creds.sh first.", file=sys.stderr)
        return 1

    r = requests.get(f"{API}/models", headers={"Authorization": f"Bearer {token}"}, timeout=30)
    if not r.ok:
        print(f"HTTP {r.status_code}: {r.text[:500]}", file=sys.stderr)
        r.raise_for_status()
    models = r.json()

    targets = ["qwen", "deepseek"]
    relevant = [m for m in models if any(t in m["id"].lower() for t in targets)]
    relevant.sort(key=lambda m: m["id"])

    print(f"Found {len(models)} total models, {len(relevant)} relevant.\n")
    print("Candidate teacher models (Qwen / DeepSeek):")
    print("-" * 110)
    for m in relevant:
        ctx = m.get("context_length", "?")
        pricing = m.get("pricing", {}) or {}
        in_p = pricing.get("input", "?") if isinstance(pricing, dict) else "?"
        out_p = pricing.get("output", "?") if isinstance(pricing, dict) else "?"
        print(f"  {m['id']:70s} ctx={str(ctx):>7s}  in=${in_p}  out=${out_p}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
