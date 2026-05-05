#!/usr/bin/env python3
"""Crawl Rust GitHub issues with closing PRs that add tests.

Pulls (issue, fix-PR diff, added test) triples from popular Rust repos.
These are candidates for Phase 1 SFT training data — and for TemRust-Issue
eval tasks (held-out, no overlap).

Strategy:
1. Search popular Rust repos (stars > 200, recent activity)
2. For each repo: list closed PRs that mention "fixes #N" or "closes #N"
3. For each candidate PR: pull the diff, check if a `#[test]` was added
4. Save metadata to data/raw/issue_candidates.jsonl
   (cargo verification is a separate step; this script just gathers metadata)

Usage:
    python scripts/crawl_rust_issues.py --max-repos 50 --max-prs-per-repo 10
"""
from __future__ import annotations
import argparse
import json
import os
import sys
import time
from pathlib import Path

import requests


GH_API = "https://api.github.com"


def gh_get(path: str, params: dict | None = None) -> dict | list:
    """GitHub API GET with auth + retry on rate limit."""
    token = os.environ["GH_TOKEN"]
    url = f"{GH_API}{path}" if path.startswith("/") else path
    for attempt in range(3):
        r = requests.get(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "tem-rust-build",
            },
            params=params,
            timeout=30,
        )
        if r.status_code == 403 and "rate limit" in r.text.lower():
            reset = int(r.headers.get("X-RateLimit-Reset", time.time() + 60))
            wait = max(1, reset - int(time.time()) + 1)
            print(f"  rate limited; waiting {wait}s...", file=sys.stderr)
            time.sleep(min(wait, 600))
            continue
        if r.status_code in (502, 503, 504):
            time.sleep(2 ** attempt)
            continue
        if not r.ok:
            print(f"  HTTP {r.status_code}: {r.text[:200]}", file=sys.stderr)
            return {} if isinstance({}, dict) else []
        return r.json()
    return {}


def find_rust_repos(max_repos: int) -> list[dict]:
    """Search top Rust repos by stars."""
    out: list[dict] = []
    page = 1
    while len(out) < max_repos and page <= 10:
        data = gh_get(
            "/search/repositories",
            params={
                "q": "language:Rust stars:>500 archived:false pushed:>2025-09-01",
                "sort": "stars",
                "order": "desc",
                "per_page": 100,
                "page": page,
            },
        )
        items = data.get("items", []) if isinstance(data, dict) else []
        if not items:
            break
        out.extend(items)
        page += 1
    return out[:max_repos]


def list_recent_closed_prs(owner: str, name: str, max_prs: int) -> list[dict]:
    """Closed PRs that mention 'fix' / 'close' / 'resolve' in title or body."""
    prs = gh_get(
        f"/repos/{owner}/{name}/pulls",
        params={"state": "closed", "per_page": 100, "sort": "updated", "direction": "desc"},
    )
    if not isinstance(prs, list):
        return []
    candidates = []
    for pr in prs:
        if pr.get("merged_at") is None:
            continue
        title = (pr.get("title") or "").lower()
        body = (pr.get("body") or "").lower()
        if not any(k in title or k in body for k in ("fix", "close", "resolve")):
            continue
        candidates.append(pr)
        if len(candidates) >= max_prs:
            break
    return candidates


def get_pr_files(owner: str, name: str, pr_number: int) -> list[dict]:
    files = gh_get(f"/repos/{owner}/{name}/pulls/{pr_number}/files", params={"per_page": 100})
    return files if isinstance(files, list) else []


def has_test_addition(files: list[dict]) -> bool:
    """Heuristic: PR adds a `#[test]` block somewhere."""
    for f in files:
        patch = f.get("patch") or ""
        # Looking for added (+) lines containing #[test]
        for line in patch.splitlines():
            if line.startswith("+") and "#[test]" in line:
                return True
    return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-repos", type=int, default=20)
    ap.add_argument("--max-prs-per-repo", type=int, default=10)
    ap.add_argument("--out", default="data/raw/issue_candidates.jsonl")
    args = ap.parse_args()

    if not os.environ.get("GH_TOKEN"):
        print("ERROR: GH_TOKEN not set. Source scripts/load_creds.sh first.", file=sys.stderr)
        return 1

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Finding top {args.max_repos} Rust repos...")
    repos = find_rust_repos(args.max_repos)
    print(f"  {len(repos)} repos found.\n")

    n_candidates = 0
    with out_path.open("w") as fh:
        for repo in repos:
            owner = repo["owner"]["login"]
            name = repo["name"]
            print(f"[{repo['stargazers_count']:>6} ★] {owner}/{name}")

            prs = list_recent_closed_prs(owner, name, args.max_prs_per_repo)
            for pr in prs:
                files = get_pr_files(owner, name, pr["number"])
                if not has_test_addition(files):
                    continue
                rust_files = [f for f in files if f["filename"].endswith(".rs")]
                if not rust_files:
                    continue

                record = {
                    "repo": f"{owner}/{name}",
                    "pr_number": pr["number"],
                    "pr_title": pr["title"],
                    "pr_body": pr.get("body", ""),
                    "merged_at": pr["merged_at"],
                    "merge_commit_sha": pr["merge_commit_sha"],
                    "base_sha": pr["base"]["sha"],
                    "files": [
                        {"path": f["filename"], "patch": f.get("patch", "")[:8000]}
                        for f in rust_files[:10]
                    ],
                }
                fh.write(json.dumps(record) + "\n")
                n_candidates += 1
                print(f"  ✓ PR #{pr['number']}: {pr['title'][:60]}")

    print(f"\nDone. {n_candidates} candidates saved to {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
