#!/usr/bin/env python3
"""Check that a hosted Story Factory behaves: login required, wrong code refused, signed-in pages work, optionally a real render.

    python tools/smoke_test.py https://your-site.example  your-personal-code
    python tools/smoke_test.py https://your-site.example  your-personal-code --render     (also makes a 10 second video; takes a minute)
    python tools/smoke_test.py https://your-site.example  your-personal-code --render --footage   (also tries the gameplay-footage layouts; needs ffmpeg on this computer)

Uses only the standard library. Exit code 0 = everything passed. The --render check uses the built-in offline engines unless the
server has AI keys, in which case it will use them (and spend a little of your credit).
"""
from __future__ import annotations

import http.cookiejar
import json
import os
import subprocess
import sys
import tempfile
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

    def req(self, method: str, path: str, body=None, headers=None, raw=None):
        data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
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


def upload_file(c: Client, path: str, name: str, filename: str, data: bytes):
    """Minimal multipart upload with the standard library."""
    boundary = "----sfsmoke" + str(int(time.time() * 1000))
    body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"; filename=\"{filename}\"\r\nContent-Type: application/octet-stream\r\n\r\n").encode() \
        + data + f"\r\n--{boundary}--\r\n".encode()
    s, b, _, _ = c.req("POST", path, headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}, raw=body)
    try:
        return s, json.loads(b or b"{}")
    except ValueError:
        return s, {}


def run_video(me: Client, idea: str) -> tuple[str, dict, dict]:
    """Create a 10 s project, run the whole pipeline, return (job status, finished project, job)."""
    s, p = me.json("POST", "/api/projects", {"name": "Smoke test", "idea": idea, "options": {"duration": 10}})
    pid = p.get("id")
    s, job = me.json("POST", f"/api/projects/{pid}/run", {"from": "story", "to": "export", "fresh": False, "pause_after": []})
    t0, status, j = time.time(), "", {}
    while s in (200, 202) and time.time() - t0 < 600:
        _, j = me.json("GET", f"/api/jobs/{job['id']}")
        status = j.get("status", "")
        if status in ("succeeded", "failed", "cancelled", "paused"):
            break
        time.sleep(3)
    _, proj = me.json("GET", f"/api/projects/{pid}")
    return status, proj, j


def footage_checks(me: Client, anon: Client) -> None:
    """Upload a real (generated) screen-recording-like clip and render both footage layouts with it."""
    tmp = tempfile.mkdtemp()
    clip = os.path.join(tmp, "gameplay.mp4")
    try:
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc2=size=720x1280:rate=24:duration=6",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", clip], check=True, timeout=120)
    except Exception as exc:
        check("footage: could make a test clip with ffmpeg on this computer", False, str(exc))
        return
    s, d = upload_file(me, "/api/footage", "files", "not-a-video.mp4", b"this is just text")
    check("footage: a file that is not a video is refused", s == 400, f"{s} {d}")
    s, d = upload_file(me, "/api/footage", "files", "gameplay.mp4", open(clip, "rb").read())
    added = (d.get("added") or [{}])[0]
    check("footage: a clip uploads", s == 201 and added.get("id"), f"{s} {d}")
    if not added.get("id"):
        return
    fid = added["id"]
    s, lst = me.json("GET", "/api/footage")
    check("footage: the clip is listed with its size and length", s == 200 and any(m["id"] == fid and m["duration"] >= 5 for m in lst), str(lst))
    s, body, _, _ = me.req("GET", f"/footage/{fid}/thumb")
    check("footage: its thumbnail loads", s == 200 and len(body) > 500, str(s))
    s, _, _, _ = anon.req("GET", f"/footage/{fid}/video")
    check("footage: the clip is NOT readable without signing in", s == 401, str(s))
    for layout in ("split", "full"):
        me.json("PUT", "/api/settings", {"footage_layout": layout, "footage_id": fid})
        status, proj, j = run_video(me, "A funny story about a boy who is the only one not invited to the party.")
        check(f"footage ({layout}): the video run finishes", status == "succeeded", f"{status} {j.get('error', '')}")
        rep = (proj.get("render") or {}).get("footage") or {}
        check(f"footage ({layout}): the render report says the footage was used", rep.get("layout") == layout and rep.get("id") == fid, str(rep))
        me.json("DELETE", f"/api/projects/{proj.get('id')}")
    me.json("PUT", "/api/settings", {"footage_layout": "off", "footage_id": ""})
    s, _ = me.json("DELETE", f"/api/footage/{fid}")
    check("footage: the clip can be deleted", s == 200, str(s))
    try:
        os.remove(clip)
        os.rmdir(tmp)
    except OSError:
        pass


def main(argv: list[str]) -> int:
    args = [a for a in argv if not a.startswith("--")]
    if len(args) < 2:
        print(__doc__)
        return 2
    base, code = args[0], args[1]
    render = "--render" in argv
    with_footage = "--footage" in argv

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
        if with_footage:
            footage_checks(me, anon)

    me.json("POST", "/api/logout")
    s, _ = me.json("GET", "/api/projects")
    check("signing out works", s == 401, str(s))
    print("\nALL CHECKS PASSED" if not failures else f"\n{len(failures)} CHECK(S) FAILED: " + "; ".join(failures))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
