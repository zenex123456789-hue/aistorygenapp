#!/usr/bin/env python3
"""Check that a hosted Story Factory behaves: login required, wrong code refused, signed-in pages work, optionally a real render.

    python tools/smoke_test.py https://your-site.example  your-personal-code
    python tools/smoke_test.py https://your-site.example  your-personal-code --render     (also makes a 10 second video; takes a minute)

Uses only the standard library. Exit code 0 = everything passed. The --render check uses the built-in offline engines unless the
server has AI keys, in which case it will use them (and spend a little of your credit).
"""
from __future__ import annotations

import http.cookiejar
import json
import sys
import time
import urllib.error
import urllib.request

failures: list[str] = []


def check(name: str, ok: bool, extra: str = "") -> None:
    print(("PASS  " if ok else "FAIL  ") + name + (f"   ({extra})" if extra and not ok else ""))
    if not ok:
        failures.append(name)


class Client:
    def __init__(self, base: str):
        self.base = base.rstrip("/")
        self.jar = http.cookiejar.CookieJar()
        self.op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))

    def req(self, method: str, path: str, body=None, headers=None):
        data = json.dumps(body).encode() if body is not None else None
        h = {"Content-Type": "application/json", **(headers or {})}
        r = urllib.request.Request(self.base + path, data=data, method=method, headers=h)
        try:
            resp = self.op.open(r, timeout=60)
            return resp.status, resp.read(), resp.headers, resp.geturl()
        except urllib.error.HTTPError as e:
            return e.code, e.read(), e.headers, self.base + path

    def json(self, method: str, path: str, body=None):
        s, b, _, _ = self.req(method, path, body)
        try:
            return s, json.loads(b or b"{}")
        except ValueError:
            return s, {}


def main(argv: list[str]) -> int:
    args = [a for a in argv if not a.startswith("--")]
    if len(args) < 2:
        print(__doc__)
        return 2
    base, code = args[0], args[1]
    render = "--render" in argv

    anon = Client(base)
    s, b, _, _ = anon.req("GET", "/healthz")
    check("server answers /healthz", s == 200, str(s))
    s, _ = anon.json("GET", "/api/projects")
    check("projects are NOT readable without signing in", s == 401, str(s))
    s, _, _, url = anon.req("GET", "/")
    check("the home page sends visitors to the sign-in page", url.rstrip("/").endswith("/login"), url)
    s, _ = anon.json("POST", "/api/login", {"code": "definitely-not-a-real-code"})
    check("a wrong code is refused", s == 401, str(s))

    me = Client(base)
    s, d = me.json("POST", "/api/login", {"code": code})
    check("your code signs you in", s == 200 and d.get("ok"), f"{s} {d}")
    if s != 200:
        return 1
    s, caps = me.json("GET", "/api/capabilities")
    check("the app loads once signed in", s == 200 and caps.get("auth", {}).get("enabled") is True, str(s))
    check("FFmpeg is present on the server", bool(caps.get("ffmpeg")))
    llm = next((p for p in caps["providers"]["llm"]["providers"] if p["active"]), {})
    tts = next((p for p in caps["providers"]["tts"]["providers"] if p["active"]), {})
    print(f"INFO  writer: {llm.get('label')}   voices: {tts.get('label')}")
    s, upd = me.json("GET", "/api/update-check")
    check("the update check answers (needs no internet to do so)", s == 200 and bool(upd.get("current")) and bool(upd.get("status")), f"{s} {upd}")
    s, page, _, _ = me.req("GET", "/")
    check("the home page opens when signed in", s == 200 and b"Story Factory" in page, str(s))

    if render:
        s, p = me.json("POST", "/api/projects", {"name": "Smoke test", "idea": "A funny story about a cat who runs the town.", "options": {"duration": 10}})
        check("can create a project", s in (200, 201) and p.get("id"), str(s))
        pid = p.get("id")
        s, job = me.json("POST", f"/api/projects/{pid}/run", {"from": "story", "to": "export", "fresh": False, "pause_after": []})
        check("can start a video run", s in (200, 202) and job.get("id"), f"{s} {job}")
        t0, status = time.time(), ""
        while time.time() - t0 < 600:
            _, j = me.json("GET", f"/api/jobs/{job['id']}")
            status = j.get("status", "")
            if status in ("succeeded", "failed", "cancelled", "paused"):
                break
            time.sleep(3)
        check("the video run finishes", status == "succeeded", f"{status} {j.get('error', '')}")
        _, files = me.json("GET", f"/api/files?project={pid}")
        vids = [f for f in files if f.get("kind") == "video"] if isinstance(files, list) else []
        check("an MP4 was produced", bool(vids))
        if vids:
            s, body, hdr, _ = me.req("GET", vids[0]["url"], headers={"Range": "bytes=0-1023"})
            check("the video can be streamed and skipped through (range request)", s == 206 and len(body) == 1024, str(s))
            s, _, _, _ = anon.req("GET", vids[0]["url"])
            check("the video is NOT downloadable without signing in", s == 401, str(s))
        me.json("DELETE", f"/api/projects/{pid}")

    me.json("POST", "/api/logout")
    s, _ = me.json("GET", "/api/projects")
    check("signing out works", s == 401, str(s))
    print("\nALL CHECKS PASSED" if not failures else f"\n{len(failures)} CHECK(S) FAILED: " + "; ".join(failures))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
