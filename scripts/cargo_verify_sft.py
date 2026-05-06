#!/usr/bin/env python3
"""Lightly filter the v3 PR-fix SFT corpus to drop no-ops and obviously
broken examples. Does NOT cargo-check the post file — most of our PR-fix
files reference crate-internal types via `use crate::foo` and won't
type-check in isolation. A first pass with full rustc dropped 90% of
legitimate examples — too aggressive.

Filters applied (cumulative):
  - drop if pre == post (whitespace + comment normalized) — formatting-only PRs
  - drop if post is suspiciously short (<50 chars after normalize)
  - drop if post lacks ANY rust structure (no `fn `, `struct`, `enum`, `impl`,
    `trait`, `mod`, `use`, `pub`) — must have some code shape
  - drop if post has gross brace imbalance ({ vs } off by >2)

Empirically this drops ~5-15% of rows. Keeps everything else. The remaining
quality lever is the size of the corpus + targeted synthetic data.

Output:
  data/clean/sft_wholefile_v5_clean.jsonl  — kept rows
  data/clean/sft_wholefile_v5_dropped.jsonl  — dropped rows (with reason)
"""
from __future__ import annotations
import argparse
import json
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path


def extract_rust_block(text: str) -> str | None:
    m = re.search(r"```rust\n(.*?)```", text, re.DOTALL)
    if not m:
        return None
    return m.group(1)


def normalize(code: str) -> str:
    # Drop comments + collapse whitespace for no-op detection
    code = re.sub(r"//[^\n]*", "", code)
    code = re.sub(r"/\*.*?\*/", "", code, flags=re.DOTALL)
    return re.sub(r"\s+", " ", code).strip()


RUST_STRUCTURE_RE = re.compile(r"\b(fn|struct|enum|impl|trait|mod|use|pub|const|static|type)\b")


def has_rust_structure(code: str) -> bool:
    return bool(RUST_STRUCTURE_RE.search(code))


def brace_imbalance(code: str) -> int:
    # Strip strings + comments first to avoid braces-in-strings throwing off the count.
    s = re.sub(r"//[^\n]*", "", code)
    s = re.sub(r"/\*.*?\*/", "", s, flags=re.DOTALL)
    s = re.sub(r'"(?:\\.|[^"\\])*"', "", s)
    s = re.sub(r"'(?:\\.|[^'\\])*'", "", s)
    return s.count("{") - s.count("}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="data/clean/sft_wholefile_v3.jsonl")
    ap.add_argument("--output", default="data/clean/sft_wholefile_v5_clean.jsonl")
    ap.add_argument("--dropped", default="data/clean/sft_wholefile_v5_dropped.jsonl")
    args = ap.parse_args()

    rows = []
    with open(args.input) as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))

    print(f"Processing {len(rows)} rows from {args.input}", flush=True)

    kept_rows: list[dict] = []
    dropped_rows: list[dict] = []
    n_noop = 0
    n_too_short = 0
    n_no_structure = 0
    n_brace_bad = 0
    n_no_block = 0

    t0 = time.time()
    for i, row in enumerate(rows):
        msgs = row["messages"]
        user_content = next((m["content"] for m in msgs if m["role"] == "user"), "")
        assistant_content = next((m["content"] for m in msgs if m["role"] == "assistant"), "")

        pre = extract_rust_block(user_content)
        post = extract_rust_block(assistant_content)

        if pre is None or post is None:
            n_no_block += 1
            dropped_rows.append({**row, "_drop_reason": "missing_rust_block"})
            continue

        post_norm = normalize(post)
        if normalize(pre) == post_norm:
            n_noop += 1
            dropped_rows.append({**row, "_drop_reason": "noop_after_whitespace_norm"})
            continue

        if len(post_norm) < 50:
            n_too_short += 1
            dropped_rows.append({**row, "_drop_reason": "too_short"})
            continue

        if not has_rust_structure(post):
            n_no_structure += 1
            dropped_rows.append({**row, "_drop_reason": "no_rust_structure"})
            continue

        bi = brace_imbalance(post)
        if abs(bi) > 2:
            n_brace_bad += 1
            dropped_rows.append({**row, "_drop_reason": f"brace_imbalance:{bi}"})
            continue

        kept_rows.append(row)

    el = time.time() - t0
    print(f"\nFINAL [{len(rows)}]: kept={len(kept_rows)} noop={n_noop} short={n_too_short} no_struct={n_no_structure} brace={n_brace_bad} no_block={n_no_block} ({el:.1f}s)", flush=True)
    print(f"  drop rate: {(len(rows)-len(kept_rows))/len(rows)*100:.1f}%", flush=True)

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w") as f:
        for r in kept_rows:
            f.write(json.dumps(r) + "\n")
    with open(args.dropped, "w") as f:
        for r in dropped_rows:
            f.write(json.dumps(r) + "\n")

    print(f"  wrote {args.output} ({len(kept_rows)} rows)")
    print(f"  wrote {args.dropped} ({len(dropped_rows)} rows)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
