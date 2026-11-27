"""Look for a newer release on GitHub. Only the newest release's public details are read; nothing is downloaded or installed here.

A private repository cannot be read without a token, so the check says so instead of guessing. Set SF_UPDATE_TOKEN (a read-only GitHub token)
in .env to let it see a private repository's releases.
"""
from __future__ import annotations

import os
import posixpath
import re
from urllib.parse import urlparse

import requests

from .version import VERSION

REPO = os.getenv("SF_UPDATE_REPO", "zenex123456789-hue/aistorygenapp").strip()
RELEASES_URL = f"https://github.com/{REPO}/releases"


def _ver(tag: str) -> tuple[int, int, int]:
    nums = [int(x) for x in re.findall(r"\d+", (tag or "").split("-")[0])][:3]
    return tuple(nums + [0] * (3 - len(nums)))  # type: ignore[return-value]


def allowed_link(url: str) -> bool:
    """Only github.com pages inside this repository may be opened on the person's behalf."""
    try:
        u = urlparse(url)
    except ValueError:
        return False
    if u.scheme != "https" or u.netloc != "github.com" or u.query or u.fragment:
        return False
    path = posixpath.normpath(u.path)
    return ".." not in u.path and (path == f"/{REPO}" or path.startswith(f"/{REPO}/"))


def _kind(name: str) -> str:
    n = name.lower()
    return "windows" if n.endswith(".exe") else "android" if n.endswith(".apk") else "iphone" if n.endswith(".ipa") else "other"


def check() -> dict:
    out = {"current": VERSION, "repo": REPO, "releases_url": RELEASES_URL}
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "AIStoryFactory-update-check"}
    token = os.getenv("SF_UPDATE_TOKEN", "").strip()
    if token:
        headers["Authorization"] = "Bearer " + token
    try:
        r = requests.get(f"https://api.github.com/repos/{REPO}/releases/latest", headers=headers, timeout=8)
    except requests.RequestException:
        return {**out, "status": "offline"}
    if r.status_code == 404:
        return {**out, "status": "unlisted"}          # private repository without a token, or no release published yet
    if r.status_code != 200:
        return {**out, "status": "refused", "http": r.status_code}
    try:
        data = r.json()
        tag = str(data["tag_name"])
    except (ValueError, KeyError):
        return {**out, "status": "refused", "http": 200}
    assets = [{"name": a.get("name", ""), "kind": _kind(a.get("name", "")), "size_mb": round(float(a.get("size") or 0) / 1e6, 1), "url": a.get("browser_download_url", "")}
              for a in data.get("assets", []) if _kind(a.get("name", "")) != "other" and allowed_link(a.get("browser_download_url", ""))]
    return {**out, "status": "ok", "latest": tag, "newer": _ver(tag) > _ver(VERSION), "title": data.get("name") or tag,
            "published": (data.get("published_at") or "")[:10], "notes": (data.get("body") or "")[:1500],
            "page": data.get("html_url") if allowed_link(data.get("html_url") or "") else RELEASES_URL, "assets": assets}
