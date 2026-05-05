#!/usr/bin/env python3
"""Convert crawled issue candidates → chat-format SFT training data.

Reads data/raw/issue_candidates.jsonl
Produces data/clean/sft_issues.jsonl in OpenAI chat format:
    {"messages": [{"role":"system",...}, {"role":"user",...}, {"role":"assistant",...}]}

For each candidate:
- system: brief Rust-assistant instruction
- user: PR title + body (the issue context) + relevant Rust file diff context
- assistant: the merged-PR diff (the fix), normalised to a structure-aware format

This is just metadata-level conversion. Phase 1 will add cargo-test verification
on top to filter out candidates whose patches don't actually pass tests.
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path


SYSTEM = (
    "You are Tem-Rust, a Rust coding assistant. When given a GitHub issue and "
    "the relevant Rust files, produce a patch that fixes the issue and passes "
    "the test suite. Output the patch as a unified diff."
)


def candidate_to_messages(c: dict) -> dict | None:
    """Convert one crawler record to a chat-format example."""
    files = c.get("files") or []
    if not files:
        return None

    # Skip patches that are too large (>10K chars total) — keeps SFT focused
    total_patch_size = sum(len(f.get("patch") or "") for f in files)
    if total_patch_size > 10_000:
        return None
    if total_patch_size < 50:
        return None

    pr_title = c.get("pr_title") or ""
    pr_body = c.get("pr_body") or ""
    repo = c.get("repo") or ""

    user_content = (
        f"Repository: {repo}\n"
        f"Issue / PR: {pr_title}\n\n"
        f"{pr_body[:1500]}\n\n"
        f"Files in this fix: {', '.join(f['path'] for f in files)}"
    )

    diff_blocks = []
    for f in files:
        patch = (f.get("patch") or "").strip()
        if not patch:
            continue
        diff_blocks.append(f"--- a/{f['path']}\n+++ b/{f['path']}\n{patch}")
    if not diff_blocks:
        return None

    assistant_content = "```diff\n" + "\n\n".join(diff_blocks) + "\n```"

    return {
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user_content},
            {"role": "assistant", "content": assistant_content},
        ],
        "metadata": {
            "repo": repo,
            "pr_number": c.get("pr_number"),
            "merged_at": c.get("merged_at"),
            "n_files": len(files),
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in-file", default="data/raw/issue_candidates.jsonl")
    ap.add_argument("--out-file", default="data/clean/sft_issues.jsonl")
    args = ap.parse_args()

    in_path = Path(args.in_file)
    out_path = Path(args.out_file)
    if not in_path.exists():
        print(f"ERROR: {in_path} not found. Run scripts/crawl_rust_issues.py first.", file=sys.stderr)
        return 1
    out_path.parent.mkdir(parents=True, exist_ok=True)

    n_in = 0
    n_out = 0
    with in_path.open() as fin, out_path.open("w") as fout:
        for line in fin:
            line = line.strip()
            if not line:
                continue
            n_in += 1
            try:
                cand = json.loads(line)
            except json.JSONDecodeError:
                continue
            ex = candidate_to_messages(cand)
            if ex is None:
                continue
            fout.write(json.dumps(ex) + "\n")
            n_out += 1

    print(f"Read {n_in} candidates, wrote {n_out} SFT examples to {out_path}")
    print(f"Filter rate: {100*n_out/max(n_in,1):.1f}% passed (size + content checks)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
