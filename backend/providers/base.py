"""Provider interfaces.

Every external AI service sits behind one of four small interfaces (LLM, TTS,
Image, Video). To add a vendor, subclass the interface, implement one or two
methods and add it to the list in providers/__init__.py. Nothing else changes.

Providers never fake output: if a call fails they raise ProviderError, and the
pipeline decides (per the user's "allow fallback" setting) whether to fall back
to the offline implementation, always recording that it did.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

import requests

from .. import config


class ProviderError(Exception):
    """The provider was reachable/configured but the request failed."""


class ProviderUnavailable(ProviderError):
    """The provider is not configured (missing API key etc.)."""


class Provider:
    kind = ""
    name = ""
    label = ""
    env_keys: tuple[str, ...] = ()
    offline = False
    #: True only if this adapter has been exercised against the live vendor API.
    #: Adapters written without live access are honest about it in the UI.
    verified = False
    note = ""

    def configured(self) -> bool:
        return all(config.env(k) for k in self.env_keys)

    def require(self) -> None:
        if not self.configured():
            missing = [k for k in self.env_keys if not config.env(k)]
            raise ProviderUnavailable(f"{self.label} is not configured. Set {', '.join(missing)} in your .env file.")

    def info(self) -> dict:
        return {"kind": self.kind, "name": self.name, "label": self.label, "configured": self.configured(),
                "env_keys": list(self.env_keys), "offline": self.offline, "verified": self.verified,
                "note": self.note}


# --------------------------------------------------------------------------- HTTP
def _scrub(text: str) -> str:
    return re.sub(r"(sk-[A-Za-z0-9_\-]{8,}|xi-[A-Za-z0-9_\-]{8,}|key_[A-Za-z0-9]{8,})", "***", text)[:600]


def http(method: str, url: str, *, headers: dict | None = None, json_body: Any = None, data: Any = None,
         timeout: float = 120, retries: int = 2, stream: bool = False) -> requests.Response:
    last: Exception | None = None
    for attempt in range(retries + 1):
        try:
            r = requests.request(method, url, headers=headers, json=json_body, data=data, timeout=timeout, stream=stream)
        except requests.RequestException as exc:
            last = ProviderError(f"Network error calling {url.split('?')[0]}: {exc}")
            time.sleep(1.5 * (attempt + 1))
            continue
        if r.status_code in (429, 500, 502, 503, 529) and attempt < retries:
            time.sleep(2.0 * (attempt + 1))
            last = ProviderError(f"HTTP {r.status_code} from {url.split('?')[0]}")
            continue
        if r.status_code >= 400:
            raise ProviderError(f"HTTP {r.status_code} from {url.split('?')[0]}: {_scrub(r.text)}")
        return r
    raise last or ProviderError("request failed")


# --------------------------------------------------------------------------- JSON parsing
def extract_json(raw: str) -> Any:
    """Parse JSON from model output, tolerating code fences and surrounding prose."""
    s = raw.strip()
    s = re.sub(r"^```(?:json)?\s*|\s*```$", "", s, flags=re.I)
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        pass
    start = min([i for i in (s.find("{"), s.find("[")) if i >= 0], default=-1)
    if start < 0:
        raise ValueError("no JSON found in model output")
    opener = s[start]
    closer = "}" if opener == "{" else "]"
    depth, in_str, esc = 0, False, False
    for i in range(start, len(s)):
        ch = s[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == opener:
            depth += 1
        elif ch == closer:
            depth -= 1
            if depth == 0:
                return json.loads(s[start:i + 1])
    raise ValueError("unterminated JSON in model output")


# --------------------------------------------------------------------------- LLM
class LLMProvider(Provider):
    kind = "llm"

    def generate(self, system: str, user: str, *, images: list[Path] | None = None, json_mode: bool = True,
                 temperature: float = 0.9, max_tokens: int = 8000) -> str:
        raise NotImplementedError

    def generate_json(self, system: str, user: str, *, images: list[Path] | None = None,
                      temperature: float = 0.9, max_tokens: int = 8000) -> Any:
        raw = self.generate(system, user, images=images, json_mode=True, temperature=temperature, max_tokens=max_tokens)
        try:
            return extract_json(raw)
        except Exception as exc:  # one repair attempt: show the model its own broken output
            repair = (f"Your previous reply was not valid JSON ({exc}). Reply again with ONLY the corrected, "
                      f"complete JSON and nothing else.\n\nPrevious reply:\n{raw[:6000]}")
            raw2 = self.generate(system, repair, json_mode=True, temperature=0.2, max_tokens=max_tokens)
            return extract_json(raw2)


# --------------------------------------------------------------------------- TTS
class TTSProvider(Provider):
    kind = "tts"

    def voices(self) -> list[dict]:
        """[{id, name, gender, accent, age, description}]"""
        raise NotImplementedError

    def synth(self, text: str, voice_id: str, out_path: Path, *, delivery: str = "natural", emotion: str = "neutral",
              speed: float = 1.0, pitch: float = 0.0, accent: str = "") -> dict:
        """Write audio to out_path (extension may be changed by the provider; the
        returned dict has the real 'path'). Returns {path, words|None, timing: 'exact'|'estimated'|None}."""
        raise NotImplementedError


# --------------------------------------------------------------------------- Image
class ImageProvider(Provider):
    kind = "image"

    def generate(self, prompt: str, out_path: Path, *, size: str = "1024x1536") -> Path:
        raise NotImplementedError


# --------------------------------------------------------------------------- Video
class VideoProvider(Provider):
    kind = "video"

    def image_to_video(self, image_path: Path, prompt: str, out_path: Path, *, duration: int = 5,
                       progress=None) -> Path:
        raise NotImplementedError
