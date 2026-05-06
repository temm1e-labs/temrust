#!/usr/bin/env python3
"""For each row in the SFT corpus, query a model endpoint with the user
prompt and save its response. Used to collect ensemble outputs for the
distill mix.

Usage:
    python scripts/collect_distill_targets.py \
        --base-url https://<pod>-8000.proxy.runpod.net \
        --input data/clean/sft_wholefile_v4.jsonl \
        --output data/distill/v5_outputs.jsonl \
        --tag v5

Output rows have shape:
    {"task_idx": <int>, "tag": "<tag>", "messages": [...input messages],
     "candidate": "<model response, raw>", "model": "<served name>"}
"""
from __future__ import annotations
import argparse
import json
import os
import sys
import time
from pathlib import Path

import requests


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", required=True, help="OpenAI-compat endpoint base URL")
    ap.add_argument("--input", required=True, help="JSONL with {messages: [...]} rows")
    ap.add_argument("--output", required=True)
    ap.add_argument("--tag", required=True, help="Label for the candidate (e.g. v4, v5)")
    ap.add_argument("--max-tokens", type=int, default=4096)
    ap.add_argument("--limit", type=int, default=0, help="Stop after N rows (0 = all)")
    ap.add_argument("--skip", type=int, default=0, help="Skip first N rows (resume after partial run)")
    ap.add_argument("--bearer-env", default="", help="If set, send Authorization: Bearer $$ENV_VAR with each request")
    ap.add_argument("--model-id", default="", help="If non-empty, use this string as the `model` field in the body (overrides --tag).")
    args = ap.parse_args()
    headers = {"Content-Type": "application/json"}
    if args.bearer_env:
        token = os.environ.get(args.bearer_env)
        if not token:
            raise SystemExit(f"--bearer-env {args.bearer_env} is empty")
        headers["Authorization"] = f"Bearer {token}"

    base = args.base_url.rstrip("/")
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)

    rows = []
    with open(args.input) as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    if args.limit:
        rows = rows[: args.limit]

    sink = open(args.output, "a")  # append so we can resume
    n_done = 0
    n_err = 0
    t0 = time.time()

    for i, row in enumerate(rows):
        if i < args.skip:
            continue
        msgs = row["messages"]
        # Strip the assistant message — we want the model to GENERATE the
        # response from the system+user prompt.
        prompt_msgs = [m for m in msgs if m["role"] != "assistant"]

        try:
            r = requests.post(
                f"{base}/v1/chat/completions",
                headers=headers,
                json={
                    "model": args.model_id or args.tag,
                    "messages": prompt_msgs,
                    "max_tokens": args.max_tokens,
                    "temperature": 0.0,
                },
                timeout=300,
            )
            r.raise_for_status()
            data = r.json()
            text = data["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"  [{i}] ERR: {e}", flush=True)
            n_err += 1
            continue

        sink.write(json.dumps({
            "task_idx": i,
            "tag": args.tag,
            "messages": prompt_msgs,
            "candidate": text,
            "model": data.get("model", args.tag),
        }) + "\n")
        sink.flush()
        n_done += 1

        if (i + 1) % 25 == 0:
            el = time.time() - t0
            print(f"  [{i+1}/{len(rows)}] done={n_done} err={n_err} ({el:.0f}s; {el/(n_done or 1):.1f}s/row)", flush=True)

    sink.close()
    el = time.time() - t0
    print(f"\nFINAL: done={n_done} err={n_err} ({el:.0f}s)", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
