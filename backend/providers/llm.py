"""LLM adapters: Anthropic (Claude), OpenAI, and the offline marker provider."""
from __future__ import annotations

import base64
import mimetypes
from pathlib import Path

from .. import config
from .base import LLMProvider, ProviderError, http


def _b64(path: Path) -> tuple[str, str]:
    mime = mimetypes.guess_type(str(path))[0] or "image/jpeg"
    return mime, base64.b64encode(Path(path).read_bytes()).decode()


class AnthropicLLM(LLMProvider):
    name = "anthropic"
    label = "Anthropic Claude"
    env_keys = ("ANTHROPIC_API_KEY",)
    note = "Messages API. Model via ANTHROPIC_MODEL (default claude-sonnet-5-5). Supports image input for reference analysis."

    def generate(self, system, user, *, images=None, json_mode=True, temperature=0.9, max_tokens=8000) -> str:
        self.require()
        content: list[dict] = []
        for img in images or []:
            mime, data = _b64(img)
            content.append({"type": "image", "source": {"type": "base64", "media_type": mime, "data": data}})
        content.append({"type": "text", "text": user})
        body = {
            "model": config.env("ANTHROPIC_MODEL", "claude-sonnet-5-5"),
            "max_tokens": max_tokens,
            "system": system + ("\n\nReply with a single valid JSON value and nothing else." if json_mode else ""),
            "messages": [{"role": "user", "content": content}],
            "temperature": temperature,
        }
        headers = {"x-api-key": config.env("ANTHROPIC_API_KEY"), "anthropic-version": "2023-06-01",
                   "content-type": "application/json"}
        url = config.env("ANTHROPIC_BASE_URL", "https://api.anthropic.com") + "/v1/messages"
        try:
            r = http("POST", url, headers=headers, json_body=body, timeout=240)
        except ProviderError as exc:
            if "temperature" in str(exc):          # some models reject a temperature override
                body.pop("temperature")
                r = http("POST", url, headers=headers, json_body=body, timeout=240)
            else:
                raise
        data = r.json()
        return "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")


class OpenAILLM(LLMProvider):
    name = "openai"
    label = "OpenAI"
    env_keys = ("OPENAI_API_KEY",)
    note = "Chat Completions API with JSON mode. Model via OPENAI_MODEL (default gpt-4.1)."

    def generate(self, system, user, *, images=None, json_mode=True, temperature=0.9, max_tokens=8000) -> str:
        self.require()
        model = config.env("OPENAI_MODEL", "gpt-4.1")
        content: list[dict] = [{"type": "text", "text": user}]
        for img in images or []:
            mime, data = _b64(img)
            content.append({"type": "image_url", "image_url": {"url": f"data:{mime};base64,{data}"}})
        body: dict = {"model": model, "max_completion_tokens": max_tokens,
                      "messages": [{"role": "system", "content": system},
                                   {"role": "user", "content": content if images else user}]}
        if not model.startswith(("o1", "o3", "o4", "gpt-5")):
            body["temperature"] = temperature
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        r = http("POST", config.env("OPENAI_BASE_URL", "https://api.openai.com") + "/v1/chat/completions",
                 headers={"Authorization": f"Bearer {config.env('OPENAI_API_KEY')}"}, json_body=body, timeout=240)
        return r.json()["choices"][0]["message"]["content"] or ""


class OfflineLLM(LLMProvider):
    """Marker provider: engines see offline=True and use their built-in generators."""
    name = "offline"
    label = "Offline generator (no LLM)"
    offline = True
    verified = True
    note = ("Built-in combinatorial story engine. Works with no keys, but is far less original than a real LLM. "
            "Connect Anthropic or OpenAI for production-quality writing.")

    def configured(self) -> bool:
        return True

    def generate(self, *a, **k) -> str:   # pragma: no cover
        raise ProviderError("The offline provider has no language model.")
