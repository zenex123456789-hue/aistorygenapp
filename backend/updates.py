"""Releases from GitHub: list them (with their notes and files), say whether a newer one exists, and hand a release file to the person.

The files are fetched by this app's own server and passed on, so nobody is sent to GitHub to download them. A private repository can only be
read with a token: set SF_UPDATE_TOKEN (a fine-grained token with read-only access to Contents of this one repository). The token stays on the
server side and is never sent to the browser.
"""
from __future__ import annotations

import os
import posixpath
import re
from urllib.parse import quote, urlparse

import requests

from . import config
from .version import VERSION

REPO = os.getenv("SF_UPDATE_REPO", "zenex123456789-hue/aistorygenapp").strip()
RELEASES_URL = f"https://github.com/{REPO}/releases"
API = "https://api.github.com"


class AssetError(Exception):
    def __init__(self, msg: str, status: int = 502):
        super().__init__(msg)
        self.msg, self.status = msg, status


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


def _headers(accept: str = "application/vnd.github+json") -> dict:
    h = {"Accept": accept, "User-Agent": "AIStoryFactory-updates"}
    token = os.getenv("SF_UPDATE_TOKEN", "").strip()
    if token:
        h["Authorization"] = "Bearer " + token
    return h


def _kind(name: str) -> str:
    n = name.lower()
    return "windows" if n.endswith(".exe") else "android" if n.endswith(".apk") else "iphone" if n.endswith(".ipa") else "other"


def changelog_for(tag: str) -> str:
    """The section for this version from CHANGELOG.md, shipped with the app (used when a release has no notes of its own)."""
    try:
        text = (config.ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    except OSError:
        return ""
    want = _ver(tag)
    for sec in re.split(r"(?m)^## +", text)[1:]:
        head, _, body = sec.partition("\n")
        first = head.split()[0] if head.split() else ""
        if re.match(r"v?\d", first) and _ver(first) == want:
            return body.strip()
    return ""


def _asset(a: dict) -> dict:
    name = a.get("name", "")
    return {"id": a["id"], "name": name, "kind": _kind(name), "size_mb": round(float(a.get("size") or 0) / 1e6, 1),
            "check_url": f"/api/releases/asset/{a['id']}/check", "download_url": f"/api/releases/asset/{a['id']}/file/{quote(name)}"}


def list_releases(limit: int = 20) -> dict:
    out = {"current": VERSION, "repo": REPO, "releases_url": RELEASES_URL}
    try:
        r = requests.get(f"{API}/repos/{REPO}/releases", params={"per_page": limit}, headers=_headers(), timeout=8)
    except requests.RequestException:
        return {**out, "status": "offline", "releases": []}
    if r.status_code == 404:
        return {**out, "status": "unlisted", "releases": []}          # private repository without a token
    if r.status_code != 200:
        return {**out, "status": "refused", "http": r.status_code, "releases": []}
    try:
        data = r.json()
        rels, latest_seen = [], False
        for x in data:
            if x.get("draft"):
                continue
            tag = str(x["tag_name"])
            is_latest = not latest_seen and not x.get("prerelease")
            latest_seen = latest_seen or is_latest
            page = x.get("html_url") or ""
            rels.append({"tag": tag, "title": x.get("name") or tag, "published": (x.get("published_at") or "")[:10], "prerelease": bool(x.get("prerelease")),
                         "latest": is_latest, "newer": _ver(tag) > _ver(VERSION), "current": _ver(tag) == _ver(VERSION),
                         "notes": ((x.get("body") or "").strip() or changelog_for(tag))[:4000],
                         "page": page if allowed_link(page) else RELEASES_URL,
                         "assets": [_asset(a) for a in x.get("assets", []) if _kind(a.get("name", "")) != "other"]})
    except (ValueError, KeyError, TypeError):
        return {**out, "status": "refused", "http": 200, "releases": []}
    return {**out, "status": "ok", "releases": rels}


def check() -> dict:
    """Is there a newer release than this app? (the newest non-pre-release one decides)"""
    res = list_releases(10)
    if res["status"] != "ok":
        return {k: v for k, v in res.items() if k != "releases"}
    latest = next((r for r in res["releases"] if r["latest"]), None)
    base = {k: v for k, v in res.items() if k != "releases"}
    if not latest:
        return {**base, "status": "unlisted"}
    return {**base, "latest": latest["tag"], "newer": latest["newer"], "title": latest["title"], "published": latest["published"],
            "notes": latest["notes"], "page": latest["page"], "assets": latest["assets"]}


def open_asset(asset_id: int) -> requests.Response:
    """Start fetching a release file from this repository. Returns the open streaming response; the caller must close it."""
    try:
        r = requests.get(f"{API}/repos/{REPO}/releases/assets/{int(asset_id)}", headers=_headers("application/octet-stream"),
                         stream=True, timeout=(10, 60), allow_redirects=True)
    except requests.RequestException:
        raise AssetError("Could not reach GitHub. Check your internet connection and try again.", 502)
    if r.status_code != 200:
        code = r.status_code
        r.close()
        if code in (401, 403, 404):
            raise AssetError("GitHub would not hand over the file. If the repository is private, a read-only token has to be set (SF_UPDATE_TOKEN); "
                             "otherwise the file may have been removed.", 404 if code == 404 else 502)
        raise AssetError(f"GitHub answered with error {code}.", 502)
    return r
