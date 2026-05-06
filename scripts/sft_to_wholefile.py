"""Convert raw PR candidates to whole-file SFT format.

Reads `data/raw/issue_candidates.jsonl`, picks the smallest changed .rs file
per PR, fetches its base-sha and merge-sha contents from raw.githubusercontent.com,
and writes Together-format SFT rows to `data/clean/sft_wholefile.jsonl`.

Output format per line:
  {"messages": [
     {"role": "system", "content": "..."},
     {"role": "user",   "content": "<issue context>\n\n```rust\n<pre-fix file>\n```"},
     {"role": "assistant", "content": "```rust\n<post-fix file>\n```"}
  ]}

Filters:
  - file must be .rs
  - both pre and post fetch must succeed (200)
  - combined size of pre + post within MAX_BYTES (default 12 KB)
  - post != pre (skip no-op patches)
"""
from __future__ import annotations
import json
import os
import sys
import time
from pathlib import Path

import requests

SYSTEM_PROMPT = (
    "You are Tem-Rust, a Rust coding assistant. When given a buggy Rust file and a description "
    "of the bug, return the complete corrected file in a single ```rust code block. "
    "Do not include any other code blocks or explanations outside the block."
)

MAX_BYTES = 80000  # combined pre + post ≤ 80KB; ~20K tokens, fits in 32K context with room for output

RAW = "https://raw.githubusercontent.com"


def fetch(repo: str, sha: str, path: str, token: str | None) -> str | None:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    url = f"{RAW}/{repo}/{sha}/{path}"
    try:
        r = requests.get(url, headers=headers, timeout=30)
    except requests.RequestException as e:
        print(f"  fetch error: {e}", file=sys.stderr)
        return None
    if r.status_code != 200:
        return None
    return r.text


def pick_file(pr: dict) -> dict | None:
    rs = [f for f in pr.get("files", []) if f["path"].endswith(".rs")]
    if not rs:
        return None
    rs.sort(key=lambda f: len(f.get("patch", "")))
    return rs[0]


def build_user_prompt(pr: dict, pre_content: str) -> str:
    title = pr.get("pr_title", "").strip()
    body = (pr.get("pr_body", "") or "").strip()
    body = body[:1500]  # cap body to avoid blowing context
    parts = [f"## Issue / fix: {title}"]
    if body:
        parts.append(f"\n## Description\n{body}")
    parts.append(f"\n## File to fix: `{pr['_chosen_file']['path']}`\n")
    parts.append(f"```rust\n{pre_content}```\n")
    parts.append("Return the complete corrected file.")
    return "\n".join(parts)


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="data/raw/issue_candidates.jsonl")
    ap.add_argument("--output", default="data/clean/sft_wholefile.jsonl")
    args = ap.parse_args()
    raw_path = Path(args.input)
    out_path = Path(args.output)
    token = os.environ.get("GH_TOKEN")
    if not token:
        print("WARNING: GH_TOKEN not set — public-only, rate-limited", file=sys.stderr)

    rows = [json.loads(l) for l in raw_path.read_text().splitlines() if l.strip()]
    print(f"loaded {len(rows)} PR candidates")

    out_lines: list[str] = []
    stats = {"no_rs": 0, "fetch_fail": 0, "too_big": 0, "no_change": 0, "ok": 0}

    for i, pr in enumerate(rows):
        chosen = pick_file(pr)
        if not chosen:
            stats["no_rs"] += 1
            continue
        pr["_chosen_file"] = chosen
        path = chosen["path"]
        repo = pr["repo"]
        base = pr["base_sha"]
        merge = pr["merge_commit_sha"]

        pre = fetch(repo, base, path, token)
        if pre is None:
            stats["fetch_fail"] += 1
            continue
        post = fetch(repo, merge, path, token)
        if post is None:
            stats["fetch_fail"] += 1
            continue

        if len(pre) + len(post) > MAX_BYTES:
            stats["too_big"] += 1
            continue
        if pre == post:
            stats["no_change"] += 1
            continue

        user = build_user_prompt(pr, pre)
        assistant = f"```rust\n{post}```"
        row = {
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user},
                {"role": "assistant", "content": assistant},
            ]
        }
        out_lines.append(json.dumps(row, ensure_ascii=False))
        stats["ok"] += 1
        if (i + 1) % 20 == 0:
            print(f"  [{i+1}/{len(rows)}] kept={stats['ok']} fail={stats['fetch_fail']} big={stats['too_big']}")
        # Be polite to GitHub raw
        time.sleep(0.05)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(out_lines) + "\n" if out_lines else "")
    print(f"\nwrote {len(out_lines)} rows to {out_path}")
    print(f"stats: {stats}")
    return 0 if out_lines else 1


if __name__ == "__main__":
    sys.exit(main())
