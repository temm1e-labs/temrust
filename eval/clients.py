"""Inference client abstraction.

Supports:
- Together AI (hosted serverless)
- Ollama (local, M-series Mac native via GGUF) — Phase 5 deployment validation only
- vLLM OpenAI-compatible (RunPod-hosted, our own checkpoints + non-serverless baselines)
"""
from __future__ import annotations
import os
from typing import Iterable

import requests


class _OpenAICompatClient:
    """Generic OpenAI-compatible chat-completions client."""

    def __init__(self, model: str, base_url: str, api_key: str | None = None, timeout: int = 240):
        self.model = model
        self.base = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    def chat(
        self,
        messages: list[dict],
        max_tokens: int = 2048,
        temperature: float = 0.0,
        stop: Iterable[str] | None = None,
    ) -> tuple[str, dict]:
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if stop:
            payload["stop"] = list(stop)
        r = requests.post(f"{self.base}/v1/chat/completions", headers=headers, json=payload, timeout=self.timeout)
        if not r.ok:
            raise RuntimeError(f"{type(self).__name__} HTTP {r.status_code}: {r.text[:300]}")
        data = r.json()
        text = data["choices"][0]["message"]["content"]
        return text, data


class TogetherClient(_OpenAICompatClient):
    def __init__(self, model: str, api_key: str | None = None):
        super().__init__(
            model,
            base_url="https://api.together.xyz",
            api_key=api_key or os.environ["TOGETHER_API_KEY"],
            timeout=240,
        )


class TogetherBaseClient:
    """Together AI base-model client. Uses /v1/completions with a manual Qwen3
    ChatML template, since base models have no built-in chat template and the
    chat-completions endpoint just echoes the prompt back.
    """

    def __init__(self, model: str, api_key: str | None = None, timeout: int = 240):
        self.model = model
        self.base = "https://api.together.xyz"
        self.api_key = api_key or os.environ["TOGETHER_API_KEY"]
        self.timeout = timeout

    @staticmethod
    def _format_qwen3_chatml(messages: list[dict]) -> str:
        parts: list[str] = []
        for m in messages:
            parts.append(f"<|im_start|>{m['role']}\n{m['content']}<|im_end|>\n")
        parts.append("<|im_start|>assistant\n")
        return "".join(parts)

    def chat(self, messages, max_tokens: int = 2048, temperature: float = 0.0, stop=None):
        prompt = self._format_qwen3_chatml(messages)
        stops = list(stop) if stop else []
        if "<|im_end|>" not in stops:
            stops.append("<|im_end|>")
        payload = {
            "model": self.model,
            "prompt": prompt,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stop": stops,
        }
        # Together's dedicated endpoints occasionally flap mid-eval — `dedicated_endpoint_not_running`
        # comes back even when the autoscaling reports STARTED|ready=1/1. Retry transient 400s.
        last_err: str = ""
        for attempt in range(5):
            r = requests.post(
                f"{self.base}/v1/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=payload,
                timeout=self.timeout,
            )
            if r.ok:
                data = r.json()
                return data["choices"][0]["text"], data
            text = r.text
            last_err = f"HTTP {r.status_code}: {text[:300]}"
            if "dedicated_endpoint_not_running" in text or r.status_code in (502, 503, 504):
                import time
                time.sleep(2 ** attempt)  # 1, 2, 4, 8, 16 s
                continue
            break
        raise RuntimeError(f"TogetherBaseClient {last_err}")


class VllmClient(_OpenAICompatClient):
    """For our RunPod-hosted vllm endpoints. URL passed via env or arg."""

    def __init__(self, model: str, base_url: str | None = None):
        super().__init__(
            model,
            base_url=base_url or os.environ["VLLM_BASE_URL"],
            api_key=None,
            timeout=600,
        )


class OllamaClient:
    """Phase 5 deployment validation only — not for Phase 0-4 baselines."""

    def __init__(self, model: str, base: str = "http://localhost:11434"):
        self.model = model
        self.base = base

    def chat(self, messages, max_tokens=2048, temperature=0.0, stop=None):
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        if stop:
            payload["options"]["stop"] = list(stop)
        r = requests.post(f"{self.base}/api/chat", json=payload, timeout=600)
        if not r.ok:
            raise RuntimeError(f"Ollama HTTP {r.status_code}: {r.text[:300]}")
        data = r.json()
        return data["message"]["content"], data


def make_client(provider: str, model: str, base_url: str | None = None):
    if provider == "together":
        return TogetherClient(model)
    if provider == "together-base":
        return TogetherBaseClient(model)
    if provider == "vllm":
        return VllmClient(model, base_url=base_url)
    if provider == "ollama":
        return OllamaClient(model)
    raise ValueError(f"unknown provider: {provider}")
