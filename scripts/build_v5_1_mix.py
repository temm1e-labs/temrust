#!/usr/bin/env python3
"""Combine cleaned PR corpus + v4 synthetic + v5.1 broader synthetic into the
v5.1 training mix. Dedupes by message-content hash.

Inputs:
  data/clean/sft_wholefile_v5_clean.jsonl   — 236 rows (v3 PR data, no-op filtered)
  data/clean/sft_synthetic.jsonl            — 92 rows (v4 synthetic, kept)
  data/clean/sft_synthetic_v5_1.jsonl       — ~70 rows (new broader synthetic)

Output:
  data/clean/sft_wholefile_v5_1.jsonl       — combined, shuffled
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
        print(f"  [WARN] {path} does not exist, skipping", file=sys.stderr)
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
    ap.add_argument("--clean", default="data/clean/sft_wholefile_v5_clean.jsonl")
    ap.add_argument("--synth-v4", default="data/clean/sft_synthetic.jsonl")
    ap.add_argument("--synth-v5-1", default="data/clean/sft_synthetic_v5_1.jsonl")
    ap.add_argument("--out", default="data/clean/sft_wholefile_v5_1.jsonl")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    sources = [
        ("clean PR", args.clean),
        ("v4 synth", args.synth_v4),
        ("v5.1 synth", args.synth_v5_1),
    ]

    seen: set[str] = set()
    combined: list[dict] = []
    for label, path in sources:
        rows = load_jsonl(path)
        before = len(combined)
        for r in rows:
            h = row_hash(r)
            if h in seen:
                continue
            seen.add(h)
            combined.append(r)
        print(f"  {label:12s}: {len(rows)} loaded, {len(combined)-before} new (dedup)")

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
