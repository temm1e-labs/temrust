"""Extract Rust code from model output.

Models return prose + code blocks. We need just the code block.
"""
from __future__ import annotations
import re


_CODE_FENCE = re.compile(
    r"```(?:rust|rs)?\s*\n(.*?)```",
    re.DOTALL | re.IGNORECASE,
)


def extract_rust_code(model_output: str) -> str:
    """Pull the first / largest Rust code block out of model output.

    Falls back to the raw text if no fence found (some models forget fences)."""
    matches = _CODE_FENCE.findall(model_output)
    if matches:
        # Prefer longest match (most likely the complete fix)
        return max(matches, key=len).strip()

    # No fence — return the raw output (it may already be valid Rust)
    return model_output.strip()
