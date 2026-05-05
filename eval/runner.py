"""Run eval tasks against a model and score them.

Usage:
    python -m eval.runner --model Qwen/Qwen3-1.7B --tasks eval/tasks --provider together
"""
from __future__ import annotations
import argparse
import json
import sys
import time
from pathlib import Path

from eval.clients import make_client
from eval.extractors import extract_rust_code
from eval.schema import EvalResult, EvalTask
from eval.verifiers import have_cargo, run_verifier


SYSTEM_PROMPT = (
    "You are a Rust coding assistant. When given a Rust file with a problem, "
    "respond with the complete corrected program in a single ```rust code block. "
    "Do not include any other code blocks or explanations outside the block."
)


def load_tasks(tasks_dir: Path) -> list[EvalTask]:
    out: list[EvalTask] = []
    for p in sorted(tasks_dir.glob("*.json")):
        d = json.loads(p.read_text())
        out.append(EvalTask(**d))
    return out


def run_one(client, task: EvalTask) -> EvalResult:
    t0 = time.time()
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"{task.task_prompt}\n\n```rust\n{task.input_code}```"},
    ]
    try:
        text, _ = client.chat(messages, max_tokens=2048, temperature=0.0)
    except Exception as e:
        return EvalResult(
            task_id=task.id, model_id=client.model, passed=False,
            error_msg=f"inference: {e}", duration_seconds=time.time() - t0,
        )

    code = extract_rust_code(text)
    passed, stdout, stderr = run_verifier(task, code, timeout_s=60)

    return EvalResult(
        task_id=task.id, model_id=client.model, passed=passed,
        raw_output=text, extracted_patch=code,
        verifier_stdout=stdout, verifier_stderr=stderr,
        duration_seconds=time.time() - t0,
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, help="Model id, e.g. Qwen/Qwen3-1.7B")
    ap.add_argument("--tasks", default="eval/tasks", help="Path to tasks directory")
    ap.add_argument("--provider", default="together", choices=["together", "ollama"], help="Inference backend")
    ap.add_argument("--out", default=None, help="Output JSON file (default: eval/results/<model>__<ts>.json)")
    ap.add_argument("--limit", type=int, default=0, help="Run only first N tasks (0=all)")
    args = ap.parse_args()

    if not have_cargo():
        print("ERROR: cargo not found in PATH. Install Rust toolchain.", file=sys.stderr)
        return 1

    tasks_dir = Path(args.tasks)
    if not tasks_dir.exists():
        print(f"ERROR: tasks dir {tasks_dir} not found", file=sys.stderr)
        return 1

    tasks = load_tasks(tasks_dir)
    if args.limit:
        tasks = tasks[: args.limit]
    if not tasks:
        print(f"ERROR: no tasks loaded from {tasks_dir}", file=sys.stderr)
        return 1

    print(f"Running {len(tasks)} tasks on {args.model} via {args.provider}")

    client = make_client(args.provider, args.model)

    results: list[EvalResult] = []
    pass_count = 0
    for task in tasks:
        print(f"  [{task.sub_eval}/{task.id}] ", end="", flush=True)
        res = run_one(client, task)
        results.append(res)
        if res.error_msg:
            print(f"ERROR ({res.error_msg})")
        else:
            tick = "✓" if res.passed else "✗"
            print(f"{tick} ({res.duration_seconds:.1f}s)")
            if res.passed:
                pass_count += 1

    n = len(results)
    print(f"\nResult: {pass_count}/{n} passed ({100*pass_count/n:.1f}%)")

    # Save results
    out_path = Path(args.out) if args.out else (
        Path("eval/results") / f"{args.model.replace('/', '__')}__{int(time.time())}.json"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(
        {
            "model": args.model,
            "provider": args.provider,
            "n_tasks": n,
            "n_passed": pass_count,
            "pass_rate": pass_count / n,
            "results": [r.__dict__ for r in results],
        },
        indent=2,
    ))
    print(f"Saved to {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
