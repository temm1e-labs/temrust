"""Extract Rust code from model output.

Models return prose + code blocks. We need just the code block.
For thinking models (Qwen3 chat), strip <think>...</think> first.
"""
from __future__ import annotations
import re


_CODE_FENCE = re.compile(
    r"```(?:rust|rs)?\s*\n(.*?)```",
    re.DOTALL | re.IGNORECASE,
)
_THINK_BLOCK = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_THINK_OPEN_UNCLOSED = re.compile(r"<think>.*", re.DOTALL | re.IGNORECASE)


def extract_rust_code(model_output: str) -> str:
    """Pull the first / largest Rust code block out of model output.

    Pre-step for thinking models: strip <think>...</think>. If <think> opens
    and never closes (model hit max_tokens during thinking), drop the rest —
    there's no real answer to extract; better to return empty than to feed
    thinking prose to the Rust compiler.

    Falls back to the raw text if no fence found."""
    text = model_output

    # Strip any closed <think>...</think> blocks (Qwen3 thinking models)
    text = _THINK_BLOCK.sub("", text)

    # If a <think> opens but never closes, the model ran out of tokens —
    # drop everything from the open onward; there's no real answer.
    if "<think>" in text.lower():
        text = _THINK_OPEN_UNCLOSED.sub("", text)

    matches = _CODE_FENCE.findall(text)
    if matches:
        # Prefer longest match (most likely the complete fix)
        return max(matches, key=len).strip()

    return text.strip()
