#!/usr/bin/env python3
"""Build the v5 ensemble-distill SFT mix.

For each example in the v4 SFT corpus:
  - read v4's candidate response and v5's candidate response
  - try a lightweight rustc parse-check on each candidate's extracted code
  - prefer the candidate that compiles syntactically (rustc-light passes)
  - if BOTH pass, prefer v4 for issue-tagged tasks (v4 is stronger on
    instruction-following) and v5 for type/test/borrow (v5 is stronger
    on coder-base reasoning); fall back to v5 for unclassified
  - if NEITHER passes, fall back to the original human-written PR fix

This produces a 1-to-1 distilled corpus of the same size as the input
where each assistant message is the strongest available answer
(ensemble proxy) per example.

Usage:
    python scripts/build_distill_mix.py \
        --input data/clean/sft_wholefile_v4.jsonl \
        --v4-outs data/distill/v4_outputs.jsonl \
        --v5-outs data/distill/v5_outputs.jsonl \
        --output data/clean/sft_distill_v5.jsonl
"""
from __future__ import annotations
import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path


def extract_rust_block(text: str) -> str | None:
    m = re.search(r"```rust\n(.*?)```", text, re.DOTALL)
    if m:
        return m.group(1).rstrip() + "\n"
    return None


def rustc_light(code: str) -> bool:
    """Parse + lightweight type-check via rustc. Returns True if no errors."""
    if not code or len(code.strip()) < 30:
        return False
    with tempfile.TemporaryDirectory() as td:
        f = Path(td) / "lib.rs"
        f.write_text(code)
        out = Path(td) / "out"
        out.mkdir(exist_ok=True)
        try:
            r = subprocess.run(
                ["rustc", "--edition=2021", "--emit=metadata", "--crate-type=lib",
                 "--out-dir", str(out), "-A", "warnings", str(f)],
                capture_output=True, text=True, timeout=30,
            )
            return r.returncode == 0
        except subprocess.TimeoutExpired:
            return False


def classify_task(user_msg: str) -> str:
    """Best-effort topic classifier from the user prompt's keywords."""
    low = user_msg.lower()
    # Check borrow first since the SFT prompt for borrow archetypes uses
    # "borrow-checker, lifetime, or ownership"
    for kw, tag in [
        ("borrow", "borrow"),
        ("lifetime", "borrow"),
        ("ownership", "borrow"),
        ("test", "test"),
        ("type-system", "type"),
        ("trait-bound", "type"),
        ("issue", "issue"),
        ("bug", "issue"),
    ]:
        if kw in low:
            return tag
    return "issue"


def load_outs(path: str) -> dict[int, str]:
    """Load distill outputs keyed by task_idx → candidate text."""
    out: dict[int, str] = {}
    if not Path(path).exists():
        print(f"  [WARN] {path} missing", file=sys.stderr)
        return out
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                d = json.loads(line)
                out[d["task_idx"]] = d.get("candidate", "")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="v4 SFT mix")
    ap.add_argument("--v4-outs", required=True)
    ap.add_argument("--v5-outs", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    v4_outs = load_outs(args.v4_outs)
    v5_outs = load_outs(args.v5_outs)
    print(f"  loaded v4={len(v4_outs)} v5={len(v5_outs)} candidates", flush=True)

    rows = []
    with open(args.input) as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    print(f"  {len(rows)} input examples", flush=True)

    counts = {"v4_chosen": 0, "v5_chosen": 0, "v4_only": 0, "v5_only": 0,
              "fallback_orig": 0, "missing_outs": 0}
    out_rows = []
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)

    for i, row in enumerate(rows):
        msgs = row["messages"]
        user_msg = next((m["content"] for m in msgs if m["role"] == "user"), "")
        orig_assistant = next((m["content"] for m in msgs if m["role"] == "assistant"), "")

        v4_cand = v4_outs.get(i)
        v5_cand = v5_outs.get(i)

        if v4_cand is None or v5_cand is None:
            counts["missing_outs"] += 1
            chosen = orig_assistant
            tag = "fallback_orig"
        else:
            v4_code = extract_rust_block(v4_cand)
            v5_code = extract_rust_block(v5_cand)
            v4_ok = rustc_light(v4_code) if v4_code else False
            v5_ok = rustc_light(v5_code) if v5_code else False

            if v4_ok and v5_ok:
                # both pass — pick by category
                cat = classify_task(user_msg)
                if cat == "issue":
                    chosen = v4_cand
                    counts["v4_chosen"] += 1
                else:
                    chosen = v5_cand
                    counts["v5_chosen"] += 1
                tag = f"both_ok_{cat}"
            elif v5_ok:
                chosen = v5_cand
                counts["v5_only"] += 1
                tag = "v5_only_ok"
            elif v4_ok:
                chosen = v4_cand
                counts["v4_only"] += 1
                tag = "v4_only_ok"
            else:
                chosen = orig_assistant
                counts["fallback_orig"] += 1
                tag = "neither_ok"

        new_msgs = [m for m in msgs if m["role"] != "assistant"] + \
                   [{"role": "assistant", "content": chosen}]
        out_rows.append({"messages": new_msgs, "_distill_tag": tag})

        if (i + 1) % 50 == 0:
            print(f"  [{i+1}/{len(rows)}] {counts}", flush=True)

    with open(args.output, "w") as f:
        for r in out_rows:
            # strip the debug tag from the actual training file format
            f.write(json.dumps({"messages": r["messages"]}) + "\n")

    print(f"\nFINAL counts: {counts}", flush=True)
    print(f"  wrote {args.output} ({len(out_rows)} rows)", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
