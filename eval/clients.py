"""Inference client abstraction.

Supports Together AI (hosted) for baselines and free-tier models.
Local llama.cpp / vllm support added in Phase 5.
"""
from __future__ import annotations
import os
from typing import Iterable

import requests


class TogetherClient:
    """Client for Together AI's OpenAI-compatible chat-completions endpoint."""

    def __init__(self, model: str, api_key: str | None = None):
        self.model = model
        self.api_key = api_key or os.environ["TOGETHER_API_KEY"]
        self.base = "https://api.together.xyz/v1"

    def chat(
        self,
        messages: list[dict],
        max_tokens: int = 2048,
        temperature: float = 0.0,
        stop: Iterable[str] | None = None,
    ) -> tuple[str, dict]:
        """Returns (text, full_response_json)."""
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if stop:
            payload["stop"] = list(stop)

        r = requests.post(
            f"{self.base}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json=payload,
            timeout=180,
        )
        if not r.ok:
            raise RuntimeError(f"Together API HTTP {r.status_code}: {r.text[:300]}")
        data = r.json()
        text = data["choices"][0]["message"]["content"]
        return text, data
