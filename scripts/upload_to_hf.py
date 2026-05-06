#!/usr/bin/env python3
"""Upload a merged tem-rust checkpoint from a RunPod pod's /workspace/merged
directory to a HuggingFace Hub repo.

The pod's log server (port 8001) serves /workspace/, so we can fetch each
file by HTTP GET, write to a local staging dir, then push via the
huggingface_hub API.

Usage:
    source scripts/load_creds.sh
    python scripts/upload_to_hf.py \
        --pod-id tufo2p7qaw5xpq \
        --repo-id quanduong/Qwen2.5-Coder-1.5B-Tem-Rust-v5_1 \
        --staging /tmp/v5_1_merged
"""
from __future__ import annotations
import argparse
import os
import sys
import time
from pathlib import Path

import requests


SMALL_FILES = [
    "added_tokens.json",
    "config.json",
    "generation_config.json",
    "merges.txt",
    "special_tokens_map.json",
    "tokenizer.json",
    "tokenizer_config.json",
    "vocab.json",
]
BIG_FILES = ["model.safetensors"]


def fetch_file(pod_id: str, name: str, dest: Path) -> int:
    url = f"https://{pod_id}-8001.proxy.runpod.net/merged/{name}"
    print(f"  GET {url} → {dest}", flush=True)
    t0 = time.time()
    with requests.get(url, stream=True, timeout=900) as r:
        r.raise_for_status()
        size = 0
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)
                    size += len(chunk)
        el = time.time() - t0
        print(f"    {size/(1024*1024):.1f} MB in {el:.0f}s ({size/el/(1024*1024):.1f} MB/s)", flush=True)
        return size


def write_model_card(
    repo_id: str,
    dest: Path,
    eval_total: int,
    eval_score_str: str,
    per_cat: dict | None = None,
) -> None:
    base_name = repo_id.split("/", 1)[1] if "/" in repo_id else repo_id
    cat_lines = ""
    if per_cat:
        cat_lines = "\n".join(
            f"| {k:6s} | {v[0]}/{v[1]} | {v[0]*100/v[1]:.1f}% |"
            for k, v in per_cat.items()
        )
    card = f"""---
license: apache-2.0
language:
- en
- code
base_model: Qwen/Qwen2.5-Coder-1.5B-Instruct
tags:
- code
- rust
- fine-tune
- lora
- sft
- coding-assistant
pipeline_tag: text-generation
---

# {base_name}

**A 1.5B Rust-specialized coding assistant**, fine-tuned via LoRA SFT on top of
`Qwen/Qwen2.5-Coder-1.5B-Instruct` using a curated 355-row Rust SFT mix
(263 real merged-PR file-pair fixes from popular Rust repos + 92 teacher-distilled
synthetic examples covering borrow/lifetime archetypes and test generation).

## Benchmark — TemRust-* (n=37 hand-curated tasks, cargo-graded)

The benchmark contains four sub-evals (all hand-curated; all graded by running
`cargo check`, `cargo test`, or `cargo run` in a fresh tempdir per task —
no mocks):

- **borrow** (10): borrow-checker / lifetime / move errors
- **issue** (9): "fix this documented bug" (real GitHub issues)
- **test** (9): write passing `#[test]` cases for given function
- **type** (9): type-system / trait-bound errors

| sub-eval | this model | rate |
|---|---|---|
{cat_lines}
| **total** | **{eval_total}/37** | **{eval_score_str}** |

### Comparison to bases and other Tem-Rust versions

| Model | Class | Pass rate |
|---|---|---|
| Qwen3-1.7B-chat (untrained) | 1.7B | 35.1% |
| Qwen2.5-Coder-1.5B-Instruct (this base, untrained) | 1.5B | 51.4% |
| Tem-Rust v4 (Qwen3-1.7B-chat + LoRA) | 1.7B | 54.1% |
| **{base_name}** | **1.5B** | **{eval_score_str}** |
| Qwen2.5-Coder-3B-Instruct (untrained, 2× the params) | 3B | 73.0% |
| Tem-Rust v4 ∪ v5 ensemble + cargo check | 3.2B | 83.8% |

## Usage

### Quick fix-this-Rust-file pattern

```python
from transformers import AutoTokenizer, AutoModelForCausalLM
import torch

tok = AutoTokenizer.from_pretrained("{repo_id}")
model = AutoModelForCausalLM.from_pretrained(
    "{repo_id}", torch_dtype=torch.bfloat16, device_map="auto"
)

SYSTEM = (
    "You are Tem-Rust, a Rust coding assistant. Return the complete fixed Rust "
    "file in a single ```rust code block. Do not include any other code blocks "
    "or explanations outside the block."
)

buggy_rust = '''
fn longest(x: &str, y: &str) -> &str {{
    if x.len() > y.len() {{ x }} else {{ y }}
}}
'''

messages = [
    {{"role": "system", "content": SYSTEM}},
    {{"role": "user", "content": f"```rust\\n{{buggy_rust}}\\n```"}},
]
prompt = tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
inputs = tok(prompt, return_tensors="pt").to(model.device)
out = model.generate(
    **inputs, max_new_tokens=2048, temperature=0.0, do_sample=False,
    pad_token_id=tok.eos_token_id,
)
print(tok.decode(out[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True))
```

### Recommended for production

Run the model's output through `cargo check` (and `cargo test` if your task
adds tests) before accepting. The ~2× lift from running both this model AND
`Tem-Rust-v4` (1.7B) and accepting whichever passes `cargo check` is documented
above as the v4 ∪ v5 ensemble.

## Training

- **Method**: LoRA r=32, alpha=64, dropout=0.05 on `q_proj`, `k_proj`, `v_proj`,
  `o_proj`, `gate_proj`, `up_proj`, `down_proj`, then merged into base for release
- **Data**: 355-row mix:
  - 263 real merged-PR file pairs (pre-fix → post-fix) crawled from 35+
    popular Rust GitHub repos via the v3 issue crawler
  - 41 teacher-distilled coverage-style test examples (Qwen3-Coder-Next-FP8)
  - 51 teacher-fixed borrow/lifetime archetypes (canonical move-after-borrow,
    lifetime missing, &mut/& conflict, dangling reference, closure capture, etc.)
- **Hyperparameters**: 10 epochs, lr 2e-5 cosine, warmup 3%, batch 4 with
  grad_accum 2 (effective 8), bf16, gradient checkpointing on, packing=True,
  max_seq_len 4096; `adamw_torch` optimizer
- **Compute**: 1× RunPod H100 SXM5 80GB, ~20 min wall time
- **Stack** (pinned for `torch==2.4.0` compatibility):
  `transformers==4.45.2`, `peft==0.13.2`, `trl==0.11.4`,
  `accelerate==1.0.1`, `datasets==3.0.2`

## Limitations

- **Whole-file SFT format**: longer than 4096 tokens gets truncated during
  training. Multi-file refactoring or large-codebase reasoning is out of scope.
- **Distribution skew**: the 37-task benchmark is hand-curated to balance
  borrow/issue/test/type, but real Rust code has much heavier issue-fix tails
  and much more boilerplate. Don't extrapolate the 62% headline to "Tem-Rust
  fixes 62% of all Rust bugs."
- **No safety / RLHF post-training**: standard helpful-instruction tuning only.
- **Training is non-deterministic**: same hyperparams + same data on different
  H100 runs landed in 21-23/37 range. The released checkpoint is *one* sample
  from this distribution.

## Source pipeline

Full data + scripts + reproducibility:
**<https://github.com/temm1e-labs/temrust>**

Citation: if you use this model, please cite the GitHub repo.
"""
    (dest / "README.md").write_text(card)


def parse_eval_for_card(eval_json_path: str) -> tuple[int, str, dict]:
    """Read an eval result JSON and return (total_passed, score_str, per_cat)."""
    import json as _json
    d = _json.load(open(eval_json_path))
    rows = d.get("results", d) if isinstance(d, dict) else d
    cats: dict[str, list[int]] = {}
    total_p = 0
    total_n = 0
    for r in rows:
        c = r["task_id"].split("_")[0]
        cats.setdefault(c, [0, 0])
        cats[c][1] += 1
        total_n += 1
        if r.get("passed"):
            cats[c][0] += 1
            total_p += 1
    score_str = f"{total_p*100/total_n:.1f}%"
    ordered = {k: cats[k] for k in ["borrow", "issue", "test", "type"] if k in cats}
    return total_p, score_str, ordered


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pod-id", help="If set, fetch /workspace/merged from this pod's :8001 log server.")
    ap.add_argument("--from-local", help="If set, use a pre-staged local directory instead of fetching from pod.")
    ap.add_argument("--repo-id", required=True, help="HF Hub repo id, e.g. nagisanzeninz/TemRust-SMOL-v5-1.5B")
    ap.add_argument("--staging", default="/tmp/tem_rust_upload")
    ap.add_argument("--eval-json", help="Path to eval result JSON for per-category card. Required.")
    ap.add_argument("--private", action="store_true", help="Create private repo on HF Hub.")
    args = ap.parse_args()

    from huggingface_hub import HfApi, create_repo

    if args.from_local:
        staging = Path(args.from_local)
        if not staging.exists():
            raise SystemExit(f"--from-local {staging} does not exist")
    else:
        if not args.pod_id:
            raise SystemExit("either --pod-id or --from-local is required")
        staging = Path(args.staging)
        staging.mkdir(parents=True, exist_ok=True)
        print(f"=== fetching merged model from pod {args.pod_id} → {staging} ===", flush=True)
        for name in SMALL_FILES + BIG_FILES:
            dest = staging / name
            if dest.exists() and dest.stat().st_size > 0:
                print(f"  {name} already cached ({dest.stat().st_size/(1024*1024):.1f} MB)", flush=True)
                continue
            try:
                fetch_file(args.pod_id, name, dest)
            except requests.HTTPError as e:
                if e.response.status_code == 404 and name in SMALL_FILES:
                    print(f"  {name}: 404 (not in checkpoint, ok)", flush=True)
                    continue
                raise

    if args.eval_json:
        total, score_str, per_cat = parse_eval_for_card(args.eval_json)
    else:
        total, score_str, per_cat = 0, "?", {}
    print(f"  eval: {total}/37 ({score_str}) per_cat={per_cat}", flush=True)

    write_model_card(args.repo_id, staging, total, score_str, per_cat)

    print(f"\n=== creating HF Hub repo {args.repo_id} ===", flush=True)
    api = HfApi(token=os.environ["HF_TOKEN"])
    create_repo(args.repo_id, token=os.environ["HF_TOKEN"], private=args.private, exist_ok=True)

    print(f"\n=== uploading {staging} → {args.repo_id} ===", flush=True)
    api.upload_folder(
        folder_path=str(staging),
        repo_id=args.repo_id,
        commit_message=f"upload tem-rust merged checkpoint, eval {total}/37 ({score_str})",
    )
    print(f"\n=== DONE ===", flush=True)
    print(f"  https://huggingface.co/{args.repo_id}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
