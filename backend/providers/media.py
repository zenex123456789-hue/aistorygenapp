"""Image and video generation adapters + their offline markers."""
from __future__ import annotations

import base64
import time
from pathlib import Path

from .. import config
from .base import ImageProvider, ProviderError, VideoProvider, http


class OpenAIImages(ImageProvider):
    name = "openai"
    label = "OpenAI Images"
    env_keys = ("OPENAI_API_KEY",)
    note = "Scene keyframes via the Images API. Model via OPENAI_IMAGE_MODEL (default gpt-image-1)."

    def generate(self, prompt: str, out_path: Path, *, size: str = "1024x1536") -> Path:
        self.require()
        body = {"model": config.env("OPENAI_IMAGE_MODEL", "gpt-image-1"), "prompt": prompt, "size": size, "n": 1}
        r = http("POST", config.env("OPENAI_BASE_URL", "https://api.openai.com") + "/v1/images/generations",
                 headers={"Authorization": f"Bearer {config.env('OPENAI_API_KEY')}"}, json_body=body, timeout=240)
        item = r.json()["data"][0]
        if item.get("b64_json"):
            out_path.write_bytes(base64.b64decode(item["b64_json"]))
        elif item.get("url"):
            out_path.write_bytes(http("GET", item["url"], timeout=120).content)
        else:
            raise ProviderError("Image API returned neither b64_json nor url")
        return out_path


class OfflineImages(ImageProvider):
    """Marker: scene art comes from the built-in procedural renderer."""
    name = "procedural"
    label = "Built-in procedural renderer"
    offline = True
    verified = True
    note = "2.5D scenes drawn by the app itself in the art style you pick (blocky, cartoon, pixel, comic, sketch). Same character spec every scene, so looks never drift."

    def configured(self) -> bool:
        return True

    def generate(self, prompt, out_path, *, size="1024x1536"):   # pragma: no cover
        raise ProviderError("The procedural renderer is driven by scene data, not text prompts.")


class RunwayVideo(VideoProvider):
    name = "runway"
    label = "Runway (image-to-video)"
    env_keys = ("RUNWAY_API_KEY",)
    note = "Animates scene keyframes. Model via RUNWAY_MODEL (default gen4_turbo). Clips are 5 or 10 seconds."

    BASE = config.env("RUNWAY_BASE_URL", "https://api.dev.runwayml.com") + "/v1"

    def _h(self) -> dict:
        return {"Authorization": f"Bearer {config.env('RUNWAY_API_KEY')}", "X-Runway-Version": "2024-11-06",
                "Content-Type": "application/json"}

    def image_to_video(self, image_path: Path, prompt: str, out_path: Path, *, duration: int = 5, progress=None) -> Path:
        self.require()
        mime = "image/png" if image_path.suffix.lower() == ".png" else "image/jpeg"
        data_uri = f"data:{mime};base64,{base64.b64encode(image_path.read_bytes()).decode()}"
        body = {"model": config.env("RUNWAY_MODEL", "gen4_turbo"), "promptImage": data_uri,
                "promptText": prompt[:950], "ratio": config.env("RUNWAY_RATIO", "720:1280"),
                "duration": 10 if duration > 6 else 5}
        task = http("POST", f"{self.BASE}/image_to_video", headers=self._h(), json_body=body, timeout=120).json()
        task_id = task["id"]
        deadline = time.time() + 15 * 60
        while time.time() < deadline:
            time.sleep(5)
            st = http("GET", f"{self.BASE}/tasks/{task_id}", headers=self._h(), timeout=60).json()
            status = st.get("status")
            if progress:
                progress(f"Runway task {status}")
            if status == "SUCCEEDED":
                url = (st.get("output") or [None])[0]
                if not url:
                    raise ProviderError("Runway reported success but returned no output URL")
                out_path.write_bytes(http("GET", url, timeout=300).content)
                return out_path
            if status in ("FAILED", "CANCELED"):
                raise ProviderError(f"Runway task {status}: {st.get('failure') or st.get('error') or 'no reason given'}")
        raise ProviderError("Runway task timed out after 15 minutes")


class OfflineVideo(VideoProvider):
    name = "none"
    label = "No AI video provider"
    offline = True
    verified = True
    note = "Without a video provider, scenes are animated by the built-in rig (or keyframes + camera moves)."

    def configured(self) -> bool:
        return True

    def image_to_video(self, *a, **k):   # pragma: no cover
        raise ProviderError("No video provider configured. Set RUNWAY_API_KEY to enable AI video clips.")
