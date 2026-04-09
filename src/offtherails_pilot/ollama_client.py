"""Minimal Ollama chat client using the local HTTP API."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Dict, Optional, Tuple


class OllamaClient:
    def __init__(self, base_url: str = "http://127.0.0.1:11434", timeout: int = 600):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _post_json(self, path: str, payload: Dict[str, object]) -> Dict[str, object]:
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            return json.load(response)

    def chat_json(
        self,
        model: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        top_p: float,
        seed: int,
        max_tokens: int,
    ) -> Tuple[str, Dict[str, object]]:
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            "format": "json",
            "options": {
                "temperature": temperature,
                "top_p": top_p,
                "seed": seed,
                "num_predict": max_tokens,
            },
        }
        body = self._post_json("/api/chat", payload)
        message = body.get("message", {})
        return str(message.get("content", "")).strip(), body

    def resolve_model_version(self, model: str) -> str:
        try:
            body = self._post_json("/api/show", {"model": model})
            details = body.get("details", {})
            digest = body.get("digest", "")
            family = details.get("family", "")
            parameter_size = details.get("parameter_size", "")
            parts = [model]
            if digest:
                parts.append(digest[:12])
            if family:
                parts.append(family)
            if parameter_size:
                parts.append(parameter_size)
            return "|".join(parts)
        except urllib.error.URLError:
            return model
