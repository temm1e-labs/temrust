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


def write_model_card(repo_id: str, dest: Path, eval_score: str = "23/37 = 62.2%") -> None:
    base_name = repo_id.split("/", 1)[1] if "/" in repo_id else repo_id
    card = f"""---
license: apache-2.0
language:
- en
- rust
base_model: Qwen/Qwen2.5-Coder-1.5B-Instruct
tags:
- code
- rust
- fine-tune
- lora
- sft
---

# {base_name}

A Rust-specialized fine-tune of `Qwen/Qwen2.5-Coder-1.5B-Instruct`, trained on
the **TemRust SFT mix** of 397 curated Rust examples (real merged-PR fixes +
hand-curated borrow/lifetime archetypes + teacher-distilled type/test slices).

## Benchmark — TemRust-* (n=37 hand-curated, cargo-graded)

| Model | Class | Pass rate |
|---|---|---|
| Qwen3-1.7B (base, fixed methodology) | 1.7B chat | 35.1% |
| Qwen2.5-Coder-1.5B-Instruct (this base) | 1.5B coder | 51.4% |
| **{base_name}** | **1.5B coder + LoRA** | **{eval_score}** |
| Qwen2.5-Coder-3B-Instruct | 3B coder (bar to beat) | 73.0% |

The benchmark covers four sub-evals in ~equal proportion:
- **borrow** (10): borrow-checker / lifetime / move errors
- **issue** (9): "fix this documented bug"
- **test** (9): write passing #[test] cases for given function
- **type** (9): type-system / trait-bound errors

All graded by `cargo check`, `cargo test`, or `cargo run` in a fresh tempdir
per task. No mocks.

## Training

- **Method**: LoRA r=64 alpha=128 on q/k/v/o/gate/up/down
- **Data**: 397 examples = 236 cleaned PR-fix file pairs + 92 v4 synthetic +
  69 v5.1 synthetic (broader Rust idioms: closure capture, RefCell/Rc, Cow,
  generic bounds, partial moves, coverage-style tests, type-error fixes)
- **Hyperparameters**: 15 epochs, lr 1e-5 cosine, warmup 3%, batch 4 with
  grad_accum 2 (effective 8), bf16, gradient checkpointing, packing=True,
  max_seq_len 4096
- **Compute**: RunPod H100 SXM5 80GB, ~25-30 min wall time
- **Stack** (pinned for torch 2.4 compat in `runpod/pytorch:2.4.0`):
  `transformers==4.45.2`, `peft==0.13.2`, `trl==0.11.4`,
  `accelerate==1.0.1`, `datasets==3.0.2`

## Usage

```python
from transformers import AutoTokenizer, AutoModelForCausalLM
import torch

tok = AutoTokenizer.from_pretrained("{repo_id}")
model = AutoModelForCausalLM.from_pretrained("{repo_id}", torch_dtype=torch.bfloat16, device_map="auto")

messages = [
    {{"role": "system", "content": "You are Tem-Rust, a Rust coding assistant. Return the complete fixed Rust file in a single ```rust code block."}},
    {{"role": "user", "content": "```rust\\nfn longest(x: &str, y: &str) -> &str {{\\n    if x.len() > y.len() {{ x }} else {{ y }}\\n}}\\n```"}},
]
prompt = tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
inputs = tok(prompt, return_tensors="pt").to(model.device)
out = model.generate(**inputs, max_new_tokens=512, temperature=0.0, do_sample=False)
print(tok.decode(out[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True))
```

## Limitations

- Trained on whole-file SFT format; longer context (>4096 tokens) gets
  truncated during training, so multi-file refactoring is out of scope.
- Issue/borrow/type/test categories balanced for the eval, but real Rust
  code has a much wider distribution.
- No safety / RLHF post-training.

## Source

Pipeline + data: <https://github.com/temm1e-labs/temrust>
"""
    (dest / "README.md").write_text(card)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pod-id", required=True, help="RunPod pod ID with merged model in /workspace/merged")
    ap.add_argument("--repo-id", required=True, help="HF Hub repo id, e.g. quanduong/Qwen2.5-Coder-1.5B-Tem-Rust-v5_1")
    ap.add_argument("--staging", default="/tmp/tem_rust_upload")
    ap.add_argument("--eval-score", default="23/37 = 62.2%", help="Score string used in the model card.")
    ap.add_argument("--private", action="store_true", help="Create private repo on HF Hub.")
    args = ap.parse_args()

    from huggingface_hub import HfApi, create_repo

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

    write_model_card(args.repo_id, staging, args.eval_score)

    print(f"\n=== creating HF Hub repo {args.repo_id} ===", flush=True)
    api = HfApi(token=os.environ["HF_TOKEN"])
    create_repo(args.repo_id, token=os.environ["HF_TOKEN"], private=args.private, exist_ok=True)

    print(f"\n=== uploading {staging} → {args.repo_id} ===", flush=True)
    api.upload_folder(
        folder_path=str(staging),
        repo_id=args.repo_id,
        commit_message=f"upload tem-rust merged checkpoint, eval {args.eval_score}",
    )
    print(f"\n=== DONE ===", flush=True)
    print(f"  https://huggingface.co/{args.repo_id}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
