#!/usr/bin/env python3
"""V2 Rust issue-fix PR crawler — looser filters, more scale.

Differences from v1:
- `has_test_addition` becomes a *scoring signal*, not a hard gate (most real
  bug fixes don't add tests in the same PR — they rely on existing tests).
- Paginates the closed-PR list (multiple pages per repo) so we don't only see
  the most recent ~100 PRs in active repos.
- Larger defaults: 60 repos × 20 PRs/repo (was 20×10).
- Patch-size sanity filter: 30 ≤ total_diff_lines ≤ 1500 (drop 1-line typos
  and giant rewrites — neither teaches a useful fix pattern).
- Skip auto-generated paths.
- Keep the same "fixes #N / closes #N + linked issue" requirement (real fix
  signal).

Usage:
    python scripts/crawl_rust_issues_v2.py --max-repos 60 --max-prs-per-repo 20
"""
from __future__ import annotations
import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

import requests


GH_API = "https://api.github.com"

ISSUE_LINK = re.compile(r"(?:fix|fixes|fixed|close|closes|closed|resolve|resolves|resolved)\s*[:\-]?\s*#\d+", re.I)
GENERATED_HINTS = ("generated/", "/vendor/", "third_party/", ".pb.rs", "bindings.rs")


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
            return {} if path.endswith(("repositories", "files", "pulls")) else {}
        return r.json()
    return {}


def find_rust_repos(max_repos: int) -> list[dict]:
    out: list[dict] = []
    page = 1
    while len(out) < max_repos and page <= 10:
        data = gh_get(
            "/search/repositories",
            params={
                "q": "language:Rust stars:>300 archived:false pushed:>2024-06-01",
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


def list_closed_prs(owner: str, name: str, max_prs: int, pages: int = 3) -> list[dict]:
    NOISE = (
        "rollup", "merge ", "version bump", "bump version", "release ",
        "dependabot", "[bot]", "release-plz", "weekly", "auto-update",
        "ci: ", "chore(deps", "chore: bump",
    )
    candidates: list[dict] = []
    for page in range(1, pages + 1):
        prs = gh_get(
            f"/repos/{owner}/{name}/pulls",
            params={"state": "closed", "per_page": 100, "sort": "updated", "direction": "desc", "page": page},
        )
        if not isinstance(prs, list) or not prs:
            break
        for pr in prs:
            if pr.get("merged_at") is None:
                continue
            title = (pr.get("title") or "").lower()
            body = (pr.get("body") or "")
            author = (pr.get("user") or {}).get("login", "").lower()
            if any(n in title for n in NOISE) or any(n in author for n in ("dependabot", "renovate", "bot")):
                continue
            # Real fix signal: must reference an issue with fix/close/resolve verb
            if not ISSUE_LINK.search(title + " " + body):
                continue
            candidates.append(pr)
            if len(candidates) >= max_prs:
                return candidates
    return candidates


def get_pr_files(owner: str, name: str, pr_number: int) -> list[dict]:
    files = gh_get(f"/repos/{owner}/{name}/pulls/{pr_number}/files", params={"per_page": 100})
    return files if isinstance(files, list) else []


def has_test_addition(files: list[dict]) -> bool:
    for f in files:
        patch = f.get("patch") or ""
        for line in patch.splitlines():
            if line.startswith("+") and "#[test]" in line:
                return True
    return False


def total_diff_lines(files: list[dict]) -> int:
    n = 0
    for f in files:
        patch = f.get("patch") or ""
        for line in patch.splitlines():
            if line.startswith(("+", "-")) and not line.startswith(("+++", "---")):
                n += 1
    return n


def is_generated(path: str) -> bool:
    p = path.lower()
    return any(h in p for h in GENERATED_HINTS)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-repos", type=int, default=60)
    ap.add_argument("--max-prs-per-repo", type=int, default=20)
    ap.add_argument("--pages", type=int, default=3, help="PR list pages per repo (each page = 100 PRs)")
    ap.add_argument("--min-diff-lines", type=int, default=30)
    ap.add_argument("--max-diff-lines", type=int, default=1500)
    ap.add_argument("--out", default="data/raw/issue_candidates_v2.jsonl")
    args = ap.parse_args()

    if not os.environ.get("GH_TOKEN"):
        print("ERROR: GH_TOKEN not set. Source scripts/load_creds.sh first.", file=sys.stderr)
        return 1

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Finding top {args.max_repos} Rust repos (stars>300, pushed>2024-06)...")
    repos = find_rust_repos(args.max_repos)
    print(f"  {len(repos)} repos found.\n")

    n_candidates = 0
    n_with_tests = 0
    stats = {"no_rs": 0, "too_small": 0, "too_big": 0, "all_generated": 0, "kept": 0}
    with out_path.open("w") as fh:
        for repo in repos:
            owner = repo["owner"]["login"]
            name = repo["name"]
            stars = repo["stargazers_count"]
            print(f"[{stars:>6} ★] {owner}/{name}")

            try:
                prs = list_closed_prs(owner, name, args.max_prs_per_repo, pages=args.pages)
            except Exception as e:
                print(f"  list error: {e}", file=sys.stderr)
                continue

            for pr in prs:
                try:
                    files = get_pr_files(owner, name, pr["number"])
                except Exception as e:
                    continue

                rust_files = [f for f in files if f["filename"].endswith(".rs") and not is_generated(f["filename"])]
                if not rust_files:
                    if any(f["filename"].endswith(".rs") for f in files):
                        stats["all_generated"] += 1
                    else:
                        stats["no_rs"] += 1
                    continue

                n_diff = total_diff_lines(rust_files)
                if n_diff < args.min_diff_lines:
                    stats["too_small"] += 1
                    continue
                if n_diff > args.max_diff_lines:
                    stats["too_big"] += 1
                    continue

                added_test = has_test_addition(rust_files)
                if added_test:
                    n_with_tests += 1

                record = {
                    "repo": f"{owner}/{name}",
                    "stars": stars,
                    "pr_number": pr["number"],
                    "pr_title": pr["title"],
                    "pr_body": pr.get("body", ""),
                    "merged_at": pr["merged_at"],
                    "merge_commit_sha": pr["merge_commit_sha"],
                    "base_sha": pr["base"]["sha"],
                    "added_test": added_test,
                    "diff_lines": n_diff,
                    "files": [
                        {"path": f["filename"], "patch": f.get("patch", "")[:8000]}
                        for f in rust_files[:10]
                    ],
                }
                fh.write(json.dumps(record) + "\n")
                fh.flush()
                n_candidates += 1
                stats["kept"] += 1
                if n_candidates % 25 == 0:
                    print(f"  ... {n_candidates} candidates, {n_with_tests} with tests", flush=True)

    print(f"\n=== done ===")
    print(f"candidates: {n_candidates}")
    print(f"with #[test] additions: {n_with_tests}")
    print(f"stats: {stats}")
    print(f"output: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
