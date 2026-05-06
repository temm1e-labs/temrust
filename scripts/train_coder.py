#!/usr/bin/env python3
"""LoRA SFT a Qwen2.5-Coder model on our v4 SFT mix, then serve via FastAPI.

Designed to run on a RunPod pod with a single 24GB+ GPU. Loads
`data/clean/sft_wholefile_v4.jsonl`, applies the model's built-in chat
template, trains a LoRA adapter, merges into the base, then optionally
starts a minimal OpenAI-compatible HTTP server (transformers-based, no
vllm dependency) so the eval can hit it from outside.

Usage:
    python scripts/train_coder.py \
        --base Qwen/Qwen2.5-Coder-1.5B-Instruct \
        --data data/clean/sft_wholefile_v4.jsonl \
        --out /workspace/merged \
        --serve-after-train
"""
from __future__ import annotations
import argparse
import json
import os
import sys
import threading
from pathlib import Path

import torch


def load_dataset_for_sft(path: str, tokenizer):
    """Load JSONL with {"messages": [...]} rows. Apply the tokenizer's chat
    template to render each conversation as a single string."""
    from datasets import Dataset
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


def train(args, tokenizer, model):
    from peft import LoraConfig, get_peft_model
    from trl import SFTConfig, SFTTrainer

    print("\n=== applying LoRA ===", flush=True)
    # Gemma 4 wraps each projection in Gemma4ClippableLinear; peft only
    # adapts plain nn.Linear, so target the inner `.linear` submodule.
    # Other architectures (Qwen, Mistral, Llama) expose nn.Linear directly.
    is_gemma4 = getattr(model.config, "model_type", "") == "gemma4"
    if is_gemma4:
        target_modules = [
            "q_proj.linear", "k_proj.linear", "v_proj.linear", "o_proj.linear",
            "gate_proj.linear", "up_proj.linear", "down_proj.linear",
        ]
    else:
        target_modules = ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]
    lora_cfg = LoraConfig(
        r=args.lora_r,
        lora_alpha=args.lora_alpha,
        target_modules=target_modules,
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
    )
    model = get_peft_model(model, lora_cfg)
    model.print_trainable_parameters()

    print("\n=== loading dataset ===", flush=True)
    ds = load_dataset_for_sft(args.data, tokenizer)
    print(f"  {len(ds)} examples", flush=True)

    sft_cfg = SFTConfig(
        output_dir=str(Path(args.out).parent / "adapter"),
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        gradient_accumulation_steps=args.grad_accum,
        gradient_checkpointing=args.grad_ckpt,
        gradient_checkpointing_kwargs={"use_reentrant": False} if args.grad_ckpt else None,
        learning_rate=args.lr,
        lr_scheduler_type="cosine",
        warmup_ratio=0.03,
        bf16=True,
        logging_steps=10,
        save_strategy="no",
        report_to="none",
        max_seq_length=args.max_seq_len,
        dataset_text_field="text",
        packing=args.packing,
        optim="adamw_torch",
    )

    n_steps = (len(ds) + (args.batch_size * args.grad_accum) - 1) // (args.batch_size * args.grad_accum) * args.epochs
    print(f"\n=== training (~{n_steps} steps over {args.epochs} epochs) ===", flush=True)
    # trl 1.x renamed `tokenizer=` to `processing_class=`. Try the new
    # name first; fall back for trl 0.x (used by v5/v6 launchers).
    try:
        trainer = SFTTrainer(
            model=model,
            args=sft_cfg,
            train_dataset=ds,
            processing_class=tokenizer,
        )
    except TypeError:
        trainer = SFTTrainer(
            model=model,
            args=sft_cfg,
            train_dataset=ds,
            tokenizer=tokenizer,
        )
    trainer.train()

    print("\n=== merging LoRA into base + saving ===", flush=True)
    merged = model.merge_and_unload()
    Path(args.out).mkdir(parents=True, exist_ok=True)
    merged.save_pretrained(args.out, safe_serialization=True)
    tokenizer.save_pretrained(args.out)
    return merged


def serve(args, tokenizer, model):
    """Minimal OpenAI-compatible HTTP server using transformers.

    Implements:
    - GET  /v1/models — required by the eval client probe
    - POST /v1/chat/completions — used by `eval/clients.py:TogetherClient`-style
    - POST /v1/completions — used by `eval/clients.py:TogetherBaseClient`-style
    """
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse
    import uvicorn

    model.eval()
    device = next(model.parameters()).device

    app = FastAPI()
    served_name = args.served_name

    @app.get("/v1/models")
    def list_models():
        return {"object": "list", "data": [{"id": served_name, "object": "model"}]}

    # Use `body: dict` rather than `req: Request` — some pinned FastAPI/pydantic
    # combinations misinterpret the Request annotation as a query-param contract.
    @app.post("/v1/chat/completions")
    async def chat(body: dict):
        messages = body.get("messages", [])
        max_new = int(body.get("max_tokens", 1024))
        temp = float(body.get("temperature", 0.0))
        prompt = tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        inputs = tokenizer(prompt, return_tensors="pt").to(device)
        with torch.no_grad():
            out = model.generate(
                **inputs,
                max_new_tokens=max_new,
                temperature=temp if temp > 0 else 1.0,
                do_sample=temp > 0,
                pad_token_id=tokenizer.eos_token_id,
            )
        gen_tokens = out[0][inputs["input_ids"].shape[1]:]
        text = tokenizer.decode(gen_tokens, skip_special_tokens=True)
        return JSONResponse({
            "id": f"chatcmpl-{served_name}",
            "object": "chat.completion",
            "model": served_name,
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": text},
                "finish_reason": "stop",
            }],
            "usage": {"prompt_tokens": int(inputs["input_ids"].shape[1]),
                       "completion_tokens": int(gen_tokens.shape[0]),
                       "total_tokens": int(out[0].shape[0])},
        })

    @app.post("/v1/completions")
    async def completion(body: dict):
        prompt = body.get("prompt", "")
        max_new = int(body.get("max_tokens", 1024))
        temp = float(body.get("temperature", 0.0))
        stop = body.get("stop") or []
        inputs = tokenizer(prompt, return_tensors="pt").to(device)
        with torch.no_grad():
            out = model.generate(
                **inputs,
                max_new_tokens=max_new,
                temperature=temp if temp > 0 else 1.0,
                do_sample=temp > 0,
                pad_token_id=tokenizer.eos_token_id,
            )
        gen_tokens = out[0][inputs["input_ids"].shape[1]:]
        text = tokenizer.decode(gen_tokens, skip_special_tokens=True)
        for s in stop:
            if s in text:
                text = text.split(s)[0]
                break
        return JSONResponse({
            "id": f"cmpl-{served_name}",
            "object": "text_completion",
            "model": served_name,
            "choices": [{"index": 0, "text": text, "finish_reason": "stop"}],
        })

    print(f"\n=== serving on 0.0.0.0:8000 ===", flush=True)
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="Qwen/Qwen2.5-Coder-1.5B-Instruct")
    ap.add_argument("--data", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--epochs", type=int, default=10)
    ap.add_argument("--batch-size", type=int, default=4)
    ap.add_argument("--grad-accum", type=int, default=2)
    ap.add_argument("--lr", type=float, default=2e-5)
    ap.add_argument("--lora-r", type=int, default=32)
    ap.add_argument("--lora-alpha", type=int, default=64)
    ap.add_argument("--max-seq-len", type=int, default=8192)
    ap.add_argument("--packing", action="store_true",
                    help="Enable SFTTrainer packing — concatenates examples to fill max_seq_len. ~3-5x faster on mixed-length corpora.")
    ap.add_argument("--no-grad-ckpt", dest="grad_ckpt", action="store_false",
                    help="Disable gradient checkpointing — only safe with 80GB+ VRAM. ~30%% faster.")
    ap.set_defaults(grad_ckpt=True)
    ap.add_argument("--serve-after-train", action="store_true",
                    help="After training+merge, start a FastAPI server on :8000.")
    ap.add_argument("--skip-train", action="store_true",
                    help="Skip training; load --out as a pre-trained model and serve.")
    ap.add_argument("--served-name", default="tem-rust-v5",
                    help="Model id surfaced via /v1/models. Defaults to tem-rust-v5.")
    args = ap.parse_args()

    print(f"=== Tem-Rust v5 SFT ===", flush=True)
    print(f"base:         {args.base}", flush=True)
    print(f"data:         {args.data}", flush=True)
    print(f"out:          {args.out}", flush=True)
    print(f"epochs:       {args.epochs}", flush=True)
    print(f"effective bs: {args.batch_size * args.grad_accum}", flush=True)
    print(f"lr:           {args.lr}", flush=True)
    print(f"lora:         r={args.lora_r} alpha={args.lora_alpha}", flush=True)

    from transformers import AutoModelForCausalLM, AutoTokenizer

    # transformers 4.55–4.57 regression: Gemma 4's tokenizer_config sets
    # extra_special_tokens as a list, but _set_model_specific_special_tokens
    # calls .keys() on it. Coerce to dict so the fast tokenizer can load.
    # (Slow tokenizer is not an option — Gemma 4 ships only tokenizer.json,
    # no SentencePiece .model file.)
    import transformers.tokenization_utils_base as _tub
    _orig_set_special = _tub.PreTrainedTokenizerBase._set_model_specific_special_tokens

    def _patched_set_special(self, special_tokens):
        if isinstance(special_tokens, list):
            # Token strings act as their own values — older transformers
            # later setattr(self, name, value) and the value must be str/AddedToken.
            special_tokens = {t: t for t in special_tokens}
        return _orig_set_special(self, special_tokens)

    _tub.PreTrainedTokenizerBase._set_model_specific_special_tokens = _patched_set_special

    print("\n=== loading tokenizer ===", flush=True)
    # In skip-train mode, the merged checkpoint at --out has its own
    # tokenizer files (saved during the original train run). Loading from
    # there preserves any tokenizer fixups, special tokens, etc.
    tok_src = args.out if args.skip_train else args.base
    tokenizer = AutoTokenizer.from_pretrained(tok_src, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    if args.skip_train:
        print(f"\n=== loading pre-trained merged model from {args.out} ===", flush=True)
        merged = AutoModelForCausalLM.from_pretrained(
            args.out, torch_dtype=torch.bfloat16, device_map="auto", trust_remote_code=True,
        )
    else:
        print("\n=== loading base ===", flush=True)
        model = AutoModelForCausalLM.from_pretrained(
            args.base, torch_dtype=torch.bfloat16, device_map="auto", trust_remote_code=True,
        )
        model.config.use_cache = False
        merged = train(args, tokenizer, model)
        # After merge, set use_cache back for inference
        merged.config.use_cache = True

    if args.serve_after_train:
        serve(args, tokenizer, merged)
    else:
        print("\n=== done (use --serve-after-train to keep alive as HTTP server) ===", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
