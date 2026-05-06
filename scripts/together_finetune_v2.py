"""Kick off Together fine-tune v2: Qwen3-1.7B (chat) + LoRA + many steps.

Differences from v0/v1:
- Base = `Qwen/Qwen3-1.7B` (chat) — already 35.1% on the eval; LoRA spends
  capacity on fix signal instead of re-learning ChatML on tiny data.
- batch_size=4 with no explicit grad accum (Together's API doesn't expose
  it directly, but lower bs still gives more steps for the same data).
  Steps = (n_examples / batch_size) × n_epochs. With bs=4, 500 ex × 5 epochs
  = 625 steps (vs v0/v1's 9).
- n_epochs=5 (was 3) for more total exposure.

Usage:
    python scripts/together_finetune_v2.py --data data/clean/sft_wholefile_v2.jsonl
"""
from __future__ import annotations
import argparse
import json
import os
import sys

from together import Together


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True, help="Path to JSONL training file")
    ap.add_argument("--base", default="Qwen/Qwen3-1.7B", help="Base model on Together")
    ap.add_argument("--epochs", type=int, default=5)
    ap.add_argument("--batch-size", type=int, default=4)
    ap.add_argument("--lr", type=float, default=2e-5)
    ap.add_argument("--lora-r", type=int, default=16)
    ap.add_argument("--lora-alpha", type=int, default=32)
    ap.add_argument("--suffix", default="tem-rust-v2")
    args = ap.parse_args()

    if not os.path.exists(args.data):
        print(f"ERROR: {args.data} not found", file=sys.stderr)
        return 1

    n_lines = sum(1 for _ in open(args.data))
    chars = sum(len(line) for line in open(args.data))
    approx_tokens = chars / 4
    steps_est = (n_lines + args.batch_size - 1) // args.batch_size * args.epochs

    print(f"=== Tem-Rust v2 fine-tune ===")
    print(f"data:        {args.data}")
    print(f"  examples:  {n_lines}")
    print(f"  ~tokens:   {approx_tokens:.0f}")
    print(f"  ~tok×epoch:{approx_tokens * args.epochs:.0f}")
    print(f"base:        {args.base}")
    print(f"epochs:      {args.epochs}")
    print(f"batch_size:  {args.batch_size}")
    print(f"steps est:   {steps_est}")
    print(f"lr:          {args.lr}")
    print(f"lora:        r={args.lora_r}, alpha={args.lora_alpha}")
    print(f"suffix:      {args.suffix}")
    print()

    client = Together(api_key=os.environ["TOGETHER_API_KEY"])

    print("=== upload ===")
    f = client.files.upload(file=args.data, check=True)
    print(f"file_id: {f.id} ({f.bytes} bytes)")

    print("\n=== fine-tune ===")
    ft = client.fine_tuning.create(
        model=args.base,
        training_file=f.id,
        n_epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.lr,
        lora=True,
        lora_r=args.lora_r,
        lora_alpha=args.lora_alpha,
        n_evals=0,
        suffix=args.suffix,
    )
    print(f"job id:        {ft.id}")
    print(f"status:        {ft.status}")
    print(f"output model:  {getattr(ft, 'model_output_name', '?')}")
    print(f"total_price:   {getattr(ft, 'total_price', '?')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
