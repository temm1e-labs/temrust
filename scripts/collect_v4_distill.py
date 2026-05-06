#!/usr/bin/env python3
"""Collect v4 candidate outputs from a Together AI dedicated endpoint, using
the TogetherBaseClient pattern (`/v1/completions` + manual Qwen3 ChatML
template). v4's chat-completions endpoint 400s — known issue documented in
eval/clients.py.

Usage:
    source scripts/load_creds.sh
    python scripts/collect_v4_distill.py \
        --model quanduong/Qwen3-1.7B-tem-rust-v4-f65a2ac9 \
        --input data/clean/sft_wholefile_v4.jsonl \
        --output data/distill/v4_outputs.jsonl \
        --limit 80
"""
from __future__ import annotations
import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from eval.clients import TogetherBaseClient  # type: ignore


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, help="Together fine-tune model id")
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--max-tokens", type=int, default=2048)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--skip", type=int, default=0)
    args = ap.parse_args()

    client = TogetherBaseClient(args.model, timeout=240)

    rows = []
    with open(args.input) as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    if args.limit:
        rows = rows[: args.limit]

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    sink = open(args.output, "a")
    n_done = 0
    n_err = 0
    t0 = time.time()

    for i, row in enumerate(rows):
        if i < args.skip:
            continue
        msgs = row["messages"]
        prompt_msgs = [m for m in msgs if m["role"] != "assistant"]
        try:
            text, _ = client.chat(prompt_msgs, max_tokens=args.max_tokens, temperature=0.0)
        except Exception as e:
            print(f"  [{i}] ERR: {e}", flush=True)
            n_err += 1
            continue
        sink.write(json.dumps({
            "task_idx": i,
            "tag": "v4",
            "messages": prompt_msgs,
            "candidate": text,
            "model": args.model,
        }) + "\n")
        sink.flush()
        n_done += 1
        if (i + 1) % 10 == 0:
            el = time.time() - t0
            print(f"  [{i+1}/{len(rows)}] done={n_done} err={n_err} ({el:.0f}s; {el/(n_done or 1):.1f}s/row)", flush=True)

    sink.close()
    el = time.time() - t0
    print(f"\nFINAL: done={n_done} err={n_err} ({el:.0f}s)", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
