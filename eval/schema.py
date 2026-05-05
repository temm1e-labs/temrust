"""Data types for TemRust-* eval tasks.

Each task is a self-contained, cargo-verifiable Rust problem.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Literal


SubEval = Literal["borrow", "type", "test", "issue"]
"""The four sub-evals (Clippy deferred to v1.1)."""


VerifierCmd = Literal["cargo check", "cargo test", "cargo build", "cargo clippy"]


@dataclass
class EvalTask:
    """One TemRust-* task. Self-contained Rust source + grading recipe."""

    id: str
    sub_eval: SubEval
    task_prompt: str           # Natural-language task description
    input_code: str            # Rust source the model sees
    verifier_cmd: VerifierCmd  # Command run on model output
    expected_outcome: Literal["compiles", "tests_pass", "warnings_clean"]
    difficulty: Literal["easy", "medium", "hard"] = "medium"
    source: str = "hand-curated"
    notes: str = ""
    # Optional: extra files needed for the cargo project (e.g., Cargo.toml override)
    extra_files: dict[str, str] = field(default_factory=dict)
    # Where to write model output. Default src/main.rs; lib tasks need src/lib.rs.
    target_file: str = "src/main.rs"


@dataclass
class EvalResult:
    """Result of running one task on one model."""

    task_id: str
    model_id: str
    passed: bool
    error_msg: str | None = None
    raw_output: str = ""
    extracted_patch: str = ""
    verifier_stdout: str = ""
    verifier_stderr: str = ""
    duration_seconds: float = 0.0
