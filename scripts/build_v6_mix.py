#!/usr/bin/env python3
"""Combine v5 SFT mix + iqmax synthetic into v6 (TemRust-SMOL-IQmax-1.5B) training set.

Inputs:
  data/clean/sft_wholefile_v4.jsonl   — 355-row v5 corpus (PR + v4 synth)
  data/clean/sft_iqmax.jsonl          — ~170-row iqmax dense reasoning Q&A

Output:
  data/clean/sft_v6_iqmax.jsonl       — combined, dedupe by message hash, shuffled
"""
from __future__ import annotations
import argparse
import hashlib
import json
import random
import sys
from pathlib import Path


def load_jsonl(path: str) -> list[dict]:
    rows = []
    if not Path(path).exists():
        print(f"  [WARN] {path} missing", file=sys.stderr)
        return rows
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def row_hash(row: dict) -> str:
    msgs = row.get("messages", [])
    txt = "".join(m.get("content", "") for m in msgs)
    return hashlib.sha256(txt.encode()).hexdigest()[:16]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--v5", default="data/clean/sft_wholefile_v4.jsonl")
    ap.add_argument("--iqmax", default="data/clean/sft_iqmax.jsonl")
    ap.add_argument("--out", default="data/clean/sft_v6_iqmax.jsonl")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    seen: set[str] = set()
    combined: list[dict] = []
    for label, path in [("v5 mix", args.v5), ("iqmax", args.iqmax)]:
        rows = load_jsonl(path)
        before = len(combined)
        for r in rows:
            h = row_hash(r)
            if h in seen:
                continue
            seen.add(h)
            combined.append(r)
        print(f"  {label:10s}: {len(rows)} loaded, {len(combined)-before} new")

    random.seed(args.seed)
    random.shuffle(combined)

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w") as f:
        for r in combined:
            f.write(json.dumps(r) + "\n")
    print(f"\n  TOTAL: {len(combined)} rows → {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
