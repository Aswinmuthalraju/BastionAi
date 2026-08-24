import json
import time
from typing import Any, Dict, List, Optional

import httpx

from app import config


class LLMUnavailableError(RuntimeError):
    """Raised when the configured model endpoint cannot be reached or errors out."""


class LLMProvider:
    """
    Thin client over an OpenAI-compatible /v1/chat/completions endpoint.

    The endpoint is whatever models_manifest.yaml declares for the routed model.
    Locally that is Ollama (verified: it implements the OpenAI chat schema).
    In production it is a vLLM cluster serving the same schema — no code here
    changes, only the manifest's `endpoint`/`served_model` fields.
    """

    def __init__(self, timeout: float = config.LLM_TIMEOUT_SECONDS):
        self._timeout = timeout

    def chat(
        self,
        endpoint: str,
        served_model: str,
        messages: List[Dict[str, str]],
        max_tokens: int = 500,
        temperature: float = 0.2,
        json_mode: bool = False,
    ) -> Dict[str, Any]:
        """
        Makes a real HTTP call and returns text + real usage/latency, or raises
        LLMUnavailableError. Callers must handle the error explicitly — this
        function never fabricates a response.
        """
        url = endpoint.rstrip("/") + "/chat/completions"
        payload: Dict[str, Any] = {
            "model": served_model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if json_mode:
            payload["format"] = "json"  # honored by Ollama; ignored harmlessly by others

        start = time.monotonic()
        try:
            with httpx.Client(timeout=self._timeout) as client:
                resp = client.post(url, json=payload)
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as exc:
            raise LLMUnavailableError(f"Model endpoint {url} unreachable: {exc}") from exc

        latency_s = round(time.monotonic() - start, 3)
        choice = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})

        return {
            "content": choice,
            "latency_s": latency_s,
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
            "served_model": served_model,
            "endpoint": endpoint,
        }

    def chat_json(
        self,
        endpoint: str,
        served_model: str,
        system: str,
        user: str,
        max_tokens: int = 200,
    ) -> Optional[Dict[str, Any]]:
        """Constrained-JSON call used by the injection-classification rail. Returns None on parse failure."""
        result = self.chat(
            endpoint=endpoint,
            served_model=served_model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            max_tokens=max_tokens,
            temperature=0.0,
            json_mode=True,
        )
        try:
            parsed = json.loads(result["content"])
        except (json.JSONDecodeError, TypeError):
            # Model didn't honor JSON mode — try to salvage a {...} block.
            text = result["content"]
            start_idx, end_idx = text.find("{"), text.rfind("}")
            if start_idx == -1 or end_idx == -1:
                return None
            try:
                parsed = json.loads(text[start_idx:end_idx + 1])
            except json.JSONDecodeError:
                return None
        parsed["_latency_s"] = result["latency_s"]
        parsed["_served_model"] = result["served_model"]
        return parsed


llm_provider = LLMProvider()
