"""LLM adapters: Anthropic (Claude), OpenAI, any OpenAI-compatible service (Ollama on your own computer, Google Gemini, Groq...), and the offline marker provider."""
from __future__ import annotations

import base64
import mimetypes
import re
from pathlib import Path
from urllib.parse import urlparse

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


class CompatibleLLM(LLMProvider):
    """Any service that speaks the OpenAI "chat completions" language, which includes free or local ones:

    * Ollama, running on your own computer (free, private, no internet or key):  base URL http://localhost:11434/v1
    * Google Gemini (has a free tier, key from aistudio.google.com):             base URL https://generativelanguage.googleapis.com/v1beta/openai
    * Groq, OpenRouter, LM Studio, vLLM and so on.

    Set OPENAI_COMPAT_BASE_URL and OPENAI_COMPAT_MODEL (and OPENAI_COMPAT_API_KEY if the service wants one). Small models write simpler stories
    than Claude and sometimes break the JSON format the app needs; the app then asks the model once to fix it and otherwise reports the failure.
    """
    name = "compatible"
    label = "Free / local AI (Ollama, Gemini, Groq...)"
    env_keys = ("OPENAI_COMPAT_BASE_URL", "OPENAI_COMPAT_MODEL")
    note = ("Any OpenAI-compatible service: Ollama on your own PC, or the free tier of Google Gemini or Groq. Set OPENAI_COMPAT_BASE_URL and "
            "OPENAI_COMPAT_MODEL, plus OPENAI_COMPAT_API_KEY when the service asks for a key. Writing quality depends on the model.")

    @staticmethod
    def endpoint() -> str:
        """The chat-completions address, tolerating the usual ways people type the base URL (with or without /v1 or the full path)."""
        base = config.env("OPENAI_COMPAT_BASE_URL").rstrip("/")
        base = re.sub(r"/chat/completions$", "", base)
        if urlparse(base).path in ("", "/"):            # "http://localhost:11434" -> ".../v1"
            base += "/v1"
        return base + "/chat/completions"

    def generate(self, system, user, *, images=None, json_mode=True, temperature=0.9, max_tokens=8000) -> str:
        self.require()
        content: list[dict] = [{"type": "text", "text": user}]
        for img in images or []:
            mime, data = _b64(img)
            content.append({"type": "image_url", "image_url": {"url": f"data:{mime};base64,{data}"}})
        body: dict = {"model": config.env("OPENAI_COMPAT_MODEL"), "max_tokens": max_tokens, "temperature": temperature,
                      "messages": [{"role": "system", "content": system + ("\n\nReply with a single valid JSON value and nothing else." if json_mode else "")},
                                   {"role": "user", "content": content if images else user}]}
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        headers = {"Authorization": "Bearer " + config.env("OPENAI_COMPAT_API_KEY")} if config.env("OPENAI_COMPAT_API_KEY") else {}
        # Local models can take minutes on a slow computer, hence the long wait. Servers differ in which options they accept:
        # if one is refused by name, leave it out and ask again.
        for _ in range(4):
            try:
                r = http("POST", self.endpoint(), headers=headers, json_body=body, timeout=900)
                break
            except ProviderError as exc:
                msg, refused = str(exc).lower(), "HTTP 4" in str(exc)
                if refused and "response_format" in body and ("response_format" in msg or "json" in msg):
                    body.pop("response_format")
                elif refused and "temperature" in body and "temperature" in msg:
                    body.pop("temperature")
                elif refused and "max_tokens" in msg and body["max_tokens"] > 4096:
                    body["max_tokens"] = 4096          # some free models cap the answer length
                elif "Network error" in str(exc) and urlparse(self.endpoint()).hostname in ("localhost", "127.0.0.1", "::1"):
                    raise ProviderError("Could not reach the AI on this computer. If you use Ollama, make sure it is running (open the Ollama app) "
                                        "and that the model name in OPENAI_COMPAT_MODEL is one you have pulled.")
                else:
                    raise
        else:                                           # pragma: no cover
            raise ProviderError("The AI service kept refusing the request.")
        try:
            text = r.json()["choices"][0]["message"].get("content") or ""
        except (ValueError, KeyError, IndexError, TypeError):
            raise ProviderError("The AI service answered, but not in the expected format. Check OPENAI_COMPAT_BASE_URL (for Ollama it ends in /v1).")
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.S | re.I).strip()      # reasoning models show their thinking first
        if not text:
            raise ProviderError("The AI model sent back an empty answer. Try a different model, or a larger one.")
        return text


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
