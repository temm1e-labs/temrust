#!/usr/bin/env python3
"""LoRA SFT a Qwen2.5-Coder model on our v4 SFT mix.

Designed to run on a RunPod pod with a single 24GB+ GPU. Loads
`data/clean/sft_wholefile_v4.jsonl`, applies the model's built-in chat
template, trains a LoRA adapter, merges into the base, saves the merged
model + tokenizer to `--out`. Then exits — the launcher script invokes
vllm separately.

Usage:
    python scripts/train_coder.py \
        --base Qwen/Qwen2.5-Coder-1.5B-Instruct \
        --data data/clean/sft_wholefile_v4.jsonl \
        --out /workspace/merged
"""
from __future__ import annotations
import argparse
import json
import os
import sys
from pathlib import Path

import torch
from datasets import Dataset
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from transformers import AutoModelForCausalLM, AutoTokenizer
from trl import SFTConfig, SFTTrainer


def load_dataset(path: str, tokenizer) -> Dataset:
    """Load JSONL with {"messages": [...]} rows. Apply the tokenizer's chat
    template to render each conversation as a single string."""
    rows = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            text = tokenizer.apply_chat_template(
                d["messages"],
                tokenize=False,
                add_generation_prompt=False,
            )
            rows.append({"text": text})
    return Dataset.from_list(rows)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="Qwen/Qwen2.5-Coder-1.5B-Instruct")
    ap.add_argument("--data", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--epochs", type=int, default=10)
    ap.add_argument("--batch-size", type=int, default=4)
    ap.add_argument("--grad-accum", type=int, default=2)  # effective bs=8
    ap.add_argument("--lr", type=float, default=2e-5)
    ap.add_argument("--lora-r", type=int, default=32)
    ap.add_argument("--lora-alpha", type=int, default=64)
    ap.add_argument("--max-seq-len", type=int, default=8192)
    args = ap.parse_args()

    print(f"=== Tem-Rust v5 SFT ===", flush=True)
    print(f"base:         {args.base}", flush=True)
    print(f"data:         {args.data}", flush=True)
    print(f"out:          {args.out}", flush=True)
    print(f"epochs:       {args.epochs}", flush=True)
    print(f"batch_size:   {args.batch_size} × grad_accum={args.grad_accum} = effective {args.batch_size * args.grad_accum}", flush=True)
    print(f"lr:           {args.lr}", flush=True)
    print(f"lora:         r={args.lora_r} alpha={args.lora_alpha}", flush=True)
    print(f"max_seq_len:  {args.max_seq_len}", flush=True)

    out_dir = Path(args.out)
    adapter_dir = out_dir.parent / "adapter"
    out_dir.mkdir(parents=True, exist_ok=True)
    adapter_dir.mkdir(parents=True, exist_ok=True)

    print("\n=== loading tokenizer + base ===", flush=True)
    tokenizer = AutoTokenizer.from_pretrained(args.base, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        args.base,
        torch_dtype=torch.bfloat16,
        device_map="auto",
        trust_remote_code=True,
    )
    model.config.use_cache = False  # incompatible with grad checkpointing

    print("\n=== loading dataset ===", flush=True)
    ds = load_dataset(args.data, tokenizer)
    print(f"  {len(ds)} examples", flush=True)
    print(f"  example[0] preview: {ds[0]['text'][:300]}...", flush=True)

    print("\n=== applying LoRA ===", flush=True)
    lora_cfg = LoraConfig(
        r=args.lora_r,
        lora_alpha=args.lora_alpha,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
    )
    model = get_peft_model(model, lora_cfg)
    model.print_trainable_parameters()

    n_steps_per_epoch = (len(ds) + (args.batch_size * args.grad_accum) - 1) // (args.batch_size * args.grad_accum)
    total_steps = n_steps_per_epoch * args.epochs
    print(f"\n=== training ({total_steps} steps over {args.epochs} epochs) ===", flush=True)

    sft_cfg = SFTConfig(
        output_dir=str(adapter_dir),
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        gradient_accumulation_steps=args.grad_accum,
        gradient_checkpointing=True,
        gradient_checkpointing_kwargs={"use_reentrant": False},
        learning_rate=args.lr,
        lr_scheduler_type="cosine",
        warmup_ratio=0.03,
        bf16=True,
        logging_steps=10,
        save_strategy="no",
        report_to="none",
        max_seq_length=args.max_seq_len,
        dataset_text_field="text",
        packing=False,
        optim="adamw_torch",
    )

    trainer = SFTTrainer(
        model=model,
        args=sft_cfg,
        train_dataset=ds,
        tokenizer=tokenizer,
    )
    trainer.train()

    print("\n=== merging LoRA into base + saving ===", flush=True)
    merged = model.merge_and_unload()
    merged.save_pretrained(out_dir, safe_serialization=True)
    tokenizer.save_pretrained(out_dir)
    print(f"  merged model saved to {out_dir}", flush=True)

    # Disk usage report
    total_size = sum(p.stat().st_size for p in out_dir.rglob("*") if p.is_file())
    print(f"  total size: {total_size / 1e9:.1f} GB", flush=True)
    print("\n=== done ===", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
