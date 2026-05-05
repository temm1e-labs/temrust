"""Cargo-based verifiers for TemRust-* tasks.

Each verifier:
1. Materialises a fresh cargo project in a tempdir
2. Writes the model's output (a full src/main.rs or src/lib.rs) into it
3. Runs the cargo command
4. Returns pass/fail + stdout/stderr
"""
from __future__ import annotations
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from eval.schema import EvalTask


DEFAULT_CARGO_TOML = """[package]
name = "temrust_eval"
version = "0.1.0"
edition = "2021"

[dependencies]
"""


def _write_project(tempdir: Path, task: EvalTask, model_code: str) -> None:
    """Set up a fresh cargo project. Model code goes in src/main.rs by default."""
    src = tempdir / "src"
    src.mkdir(exist_ok=True)
    (tempdir / "Cargo.toml").write_text(
        task.extra_files.get("Cargo.toml", DEFAULT_CARGO_TOML)
    )
    (src / "main.rs").write_text(model_code)
    for path, content in task.extra_files.items():
        if path == "Cargo.toml":
            continue
        target = tempdir / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)


def run_verifier(task: EvalTask, model_code: str, timeout_s: int = 60) -> tuple[bool, str, str]:
    """Returns (passed, stdout, stderr)."""
    with tempfile.TemporaryDirectory(prefix="temrust_") as td:
        td_path = Path(td)
        _write_project(td_path, task, model_code)

        cmd = task.verifier_cmd.split()
        try:
            res = subprocess.run(
                cmd,
                cwd=td_path,
                capture_output=True,
                text=True,
                timeout=timeout_s,
            )
        except subprocess.TimeoutExpired as e:
            return False, e.stdout or "", f"TIMEOUT after {timeout_s}s\n{e.stderr or ''}"

        passed = res.returncode == 0
        return passed, res.stdout, res.stderr


def have_cargo() -> bool:
    """Check that the cargo toolchain is available."""
    return shutil.which("cargo") is not None
