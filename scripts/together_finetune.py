#!/usr/bin/env python3
"""Kick off a Together AI fine-tune of Qwen3-1.7B-Base on our SFT data.

Steps:
1. Upload data/clean/sft_issues.jsonl as a fine-tune training file
2. Create a fine-tune job
3. Print job ID + polling instructions

Together fine-tune cost (approx): $0.0008/Mtok training × ~150K tok × 3 epochs ≈ $0.36
Actual cost is shown in /v1/fine-tunes/{id}/events.
"""
from __future__ import annotations
import argparse
import json
import os
import sys
import time

import requests


API = "https://api.together.xyz"


def hdr() -> dict:
    return {"Authorization": f"Bearer {os.environ['TOGETHER_API_KEY']}"}


def upload_file(path: str) -> str:
    """Upload JSONL file. Returns file_id."""
    with open(path, "rb") as fh:
        files = {"file": (os.path.basename(path), fh, "application/jsonl")}
        data = {"purpose": "fine-tune"}
        r = requests.post(f"{API}/v1/files", headers=hdr(), files=files, data=data, timeout=300)
    if not r.ok:
        raise RuntimeError(f"Upload failed HTTP {r.status_code}: {r.text[:500]}")
    j = r.json()
    print(f"Uploaded: {j}")
    return j["id"]


def create_finetune(model: str, training_file_id: str, n_epochs: int, lr: float, suffix: str | None) -> dict:
    body = {
        "model": model,
        "training_file": training_file_id,
        "n_epochs": n_epochs,
        "learning_rate": lr,
        "lora": True,
        "lora_r": 16,
        "lora_alpha": 32,
        "n_evals": 0,
    }
    if suffix:
        body["suffix"] = suffix
    r = requests.post(f"{API}/v1/fine-tunes", headers={**hdr(), "Content-Type": "application/json"},
                       json=body, timeout=60)
    if not r.ok:
        raise RuntimeError(f"Create fine-tune failed HTTP {r.status_code}: {r.text[:500]}")
    return r.json()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/clean/sft_issues.jsonl")
    ap.add_argument("--model", default="Qwen/Qwen3-1.7B-Base",
                    help="Base model on Together. Use Qwen3-1.7B-Base for the actual training base.")
    ap.add_argument("--epochs", type=int, default=3)
    ap.add_argument("--lr", type=float, default=2e-5)
    ap.add_argument("--suffix", default="tem-rust-v0",
                    help="Suffix appended to fine-tuned model name")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    data_path = args.data
    if not os.path.exists(data_path):
        print(f"ERROR: {data_path} not found", file=sys.stderr)
        return 1

    n_lines = sum(1 for _ in open(data_path))
    total_chars = sum(len(line) for line in open(data_path))
    approx_tokens = total_chars / 4
    print(f"Data: {data_path}")
    print(f"  examples: {n_lines}")
    print(f"  ~tokens (rough): {approx_tokens:.0f}")
    print(f"  ~training tokens (×{args.epochs} epochs): {approx_tokens * args.epochs:.0f}")
    print(f"Model:   {args.model}")
    print(f"Epochs:  {args.epochs}")
    print(f"LR:      {args.lr}")
    print(f"LoRA:    r=16 alpha=32")
    print(f"Suffix:  {args.suffix}")

    if args.dry_run:
        print("[DRY RUN] not uploading or creating fine-tune")
        return 0

    print("\nUploading training file...")
    file_id = upload_file(data_path)
    print(f"file_id = {file_id}")

    # Brief sanity wait — Together needs a few seconds to validate the file
    time.sleep(3)

    print("\nCreating fine-tune job...")
    job = create_finetune(args.model, file_id, args.epochs, args.lr, args.suffix)
    print(json.dumps(job, indent=2))

    job_id = job.get("id")
    if job_id:
        print(f"\nJOB ID: {job_id}")
        print(f"Poll status: curl -H 'Authorization: Bearer $TOGETHER_API_KEY' {API}/v1/fine-tunes/{job_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
