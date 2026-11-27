"""Provider registry. To add a vendor: subclass the interface, append it to the list below."""
from __future__ import annotations

from .. import db
from .base import (ImageProvider, LLMProvider, Provider, ProviderError, ProviderUnavailable,  # noqa: F401
                   TTSProvider, VideoProvider)
from .llm import AnthropicLLM, CompatibleLLM, OfflineLLM, OpenAILLM
from .media import OfflineImages, OfflineVideo, OpenAIImages, RunwayVideo
from .tts import BlipTTS, ElevenLabsTTS, OpenAITTS

# Order matters for "auto": the first configured, non-offline provider wins.
REGISTRY: dict[str, list[Provider]] = {
    "llm": [AnthropicLLM(), OpenAILLM(), CompatibleLLM(), OfflineLLM()],
    "tts": [ElevenLabsTTS(), OpenAITTS(), BlipTTS()],
    "image": [OpenAIImages(), OfflineImages()],
    "video": [RunwayVideo(), OfflineVideo()],
}
SETTING_KEY = {"llm": "llm_provider", "tts": "tts_provider", "image": "image_provider", "video": "video_provider"}


def resolve(kind: str, settings: dict | None = None) -> Provider:
    settings = settings or db.get_settings()
    choice = settings.get(SETTING_KEY[kind], "auto")
    providers = REGISTRY[kind]
    if choice and choice != "auto":
        for p in providers:
            if p.name == choice:
                return p
    for p in providers:
        if not p.offline and p.configured():
            return p
    return next(p for p in providers if p.offline)


def offline_for(kind: str) -> Provider:
    return next(p for p in REGISTRY[kind] if p.offline)


def by_name(kind: str, name: str) -> Provider | None:
    return next((p for p in REGISTRY[kind] if p.name == name), None)


def llm() -> LLMProvider:
    return resolve("llm")  # type: ignore[return-value]


def tts() -> TTSProvider:
    return resolve("tts")  # type: ignore[return-value]


def image() -> ImageProvider:
    return resolve("image")  # type: ignore[return-value]


def video() -> VideoProvider:
    return resolve("video")  # type: ignore[return-value]


def capabilities() -> dict:
    settings = db.get_settings()
    out = {}
    for kind, providers in REGISTRY.items():
        active = resolve(kind, settings)
        out[kind] = {
            "selected": settings.get(SETTING_KEY[kind], "auto"),
            "active": active.name,
            "providers": [{**p.info(), "active": p.name == active.name} for p in providers],
        }
    return out
