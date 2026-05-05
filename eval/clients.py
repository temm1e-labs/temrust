"""Inference client abstraction.

Supports:
- Together AI (hosted serverless)
- Ollama (local, M-series Mac native via GGUF)
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
            timeout=240,
        )
        if not r.ok:
            raise RuntimeError(f"Together API HTTP {r.status_code}: {r.text[:300]}")
        data = r.json()
        text = data["choices"][0]["message"]["content"]
        return text, data


class OllamaClient:
    """Client for local Ollama daemon (default localhost:11434)."""

    def __init__(self, model: str, base: str = "http://localhost:11434"):
        self.model = model
        self.base = base

    def chat(
        self,
        messages: list[dict],
        max_tokens: int = 2048,
        temperature: float = 0.0,
        stop: Iterable[str] | None = None,
    ) -> tuple[str, dict]:
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        if stop:
            payload["options"]["stop"] = list(stop)

        r = requests.post(
            f"{self.base}/api/chat",
            json=payload,
            timeout=600,  # local inference of larger models can be slow
        )
        if not r.ok:
            raise RuntimeError(f"Ollama HTTP {r.status_code}: {r.text[:300]}")
        data = r.json()
        text = data["message"]["content"]
        return text, data


def make_client(provider: str, model: str):
    if provider == "together":
        return TogetherClient(model)
    if provider == "ollama":
        return OllamaClient(model)
    raise ValueError(f"unknown provider: {provider}")
