"""Access control for the hosted (shared) version.

Off by default, so the Windows app and `python run.py` on your own PC work with no login. It turns on when
SF_ACCESS_CODES is set, for example:

    SF_ACCESS_CODES=alice:Kd83-hq2LzPw,bob:r7Tn-4Vm9XcE

One code per person, so you can cut one person off without touching the others. This is a login for a small group of people you
know. It is not a full account system: everyone shares the same projects and files.

What it does:
  * a signed, HttpOnly cookie (60 days) that is tied to that person's code, so changing or removing a code logs them out
  * at most 8 wrong codes per address per 5 minutes
  * a per-person daily cap on pipeline runs (SF_DAILY_RUNS, default 20; 0 = no cap) so a friend cannot burn your API credit
  * a same-origin check on every change request, plus basic security headers
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import re
import threading
import time
from datetime import datetime, timezone

from flask import Response, jsonify, redirect, request

COOKIE = "sf_auth"
TTL = 60 * 24 * 3600
MIN_CODE = 8
NAME_OK = re.compile(r"^[A-Za-z0-9 _.\-]{1,32}$")
# Requests that start a (paid) pipeline run.
RUN_PATH = re.compile(r"^/api/projects/[^/]+/(run|stage/[^/]+|score/apply)$")
OPEN_PATHS = {"/login", "/api/login", "/healthz", "/manifest.webmanifest", "/sw.js"}
UNSAFE = {"POST", "PUT", "PATCH", "DELETE"}

_users: dict[str, str] = {}
_lock = threading.Lock()
_fails: dict[str, list[float]] = {}
_runs: dict[tuple[str, str], int] = {}


class ConfigError(RuntimeError):
    pass


def parse_codes(raw: str, legacy: str = "") -> dict[str, str]:
    """'alice:code1,bob:code2' -> {'alice': 'code1', 'bob': 'code2'}. A bare code gets the name friend1, friend2..."""
    users: dict[str, str] = {}
    items = [x.strip() for x in re.split(r"[,\n;]+", raw or "") if x.strip()]
    if legacy.strip():
        items.append("friend:" + legacy.strip())
    for item in items:
        if ":" in item:
            name, code = item.split(":", 1)
        else:
            name, code = f"friend{len(users) + 1}", item
        name, code = name.strip(), code.strip()
        if not NAME_OK.match(name):
            raise ConfigError(f"Access name {name!r} is not allowed. Use letters, numbers, spaces, dots, dashes (up to 32).")
        if len(code) < MIN_CODE:
            raise ConfigError(f"The access code for {name!r} is too short. Use at least {MIN_CODE} characters; 12 or more random ones is better.")
        if name in users:
            raise ConfigError(f"Two access codes use the name {name!r}.")
        if code in users.values():
            raise ConfigError("Two people share the same access code. Give each person their own.")
        users[name] = code
    return users


def enabled() -> bool:
    return bool(_users)


def _token(name: str, code: str, exp: int) -> str:
    sig = hmac.new(code.encode(), f"{name}|{exp}".encode(), hashlib.sha256).hexdigest()
    return f"{base64.urlsafe_b64encode(name.encode()).decode().rstrip('=')}.{exp}.{sig}"


def current_user() -> str | None:
    tok = request.cookies.get(COOKIE, "")
    try:
        b64, exp_s, sig = tok.split(".")
        name = base64.urlsafe_b64decode(b64 + "=" * (-len(b64) % 4)).decode()
        exp = int(exp_s)
    except Exception:  # noqa: BLE001
        return None
    code = _users.get(name)
    if not code or exp < time.time():
        return None
    good = hmac.new(code.encode(), f"{name}|{exp}".encode(), hashlib.sha256).hexdigest()
    return name if hmac.compare_digest(sig, good) else None


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def daily_limit() -> int:
    try:
        return max(0, int(os.getenv("SF_DAILY_RUNS", "20")))
    except ValueError:
        return 20


def runs_today(name: str) -> int:
    return _runs.get((name, _today()), 0)


def status() -> dict:
    """Safe to send to the browser: no codes, only who is signed in and their allowance."""
    if not enabled():
        return {"enabled": False}
    name = current_user()
    return {"enabled": True, "user": name, "runs_today": runs_today(name) if name else 0, "run_limit": daily_limit()}


def _client_ip() -> str:
    return request.remote_addr or "?"


def init(app, hosted: bool) -> None:
    """Read the codes, wire the request gate. Raises ConfigError if hosted mode is requested without a code."""
    global _users
    _users = parse_codes(os.getenv("SF_ACCESS_CODES", ""), os.getenv("SF_ACCESS_CODE", ""))
    if hosted and not _users:
        raise ConfigError("SF_HOSTED is on but no access codes are set. Set SF_ACCESS_CODES (for example alice:some-long-code) "
                          "so the internet cannot use your API keys.")

    @app.get("/healthz")
    def healthz():                                   # for hosting platforms; says nothing about the app
        return jsonify({"ok": True})

    @app.before_request
    def gate():
        if not enabled():
            return None
        p = request.path
        if request.method in UNSAFE:                 # a form on another website must not be able to act as a signed-in person
            origin = request.headers.get("Origin")
            ohost = origin.split("://", 1)[-1].rstrip("/") if origin else ""
            if origin and ohost not in (request.host, request.headers.get("X-Forwarded-Host", "")):
                return jsonify({"error": "Blocked: request came from another site."}), 403
        if p in OPEN_PATHS or p.startswith("/icons/"):
            return None
        name = current_user()
        if not name:
            if p.startswith(("/api/", "/files/", "/refs/", "/footage/", "/preview/")):
                return jsonify({"error": "Please sign in.", "login": "/login"}), 401
            return redirect("/login")
        if request.method == "POST" and RUN_PATH.match(p):
            limit = daily_limit()
            with _lock:
                key = (name, _today())
                if limit and _runs.get(key, 0) >= limit:
                    return jsonify({"error": f"Daily limit reached ({limit} runs per person per day). It resets at midnight UTC."}), 429
                _runs[key] = _runs.get(key, 0) + 1
        return None

    @app.after_request
    def headers(resp):
        if enabled():
            resp.headers.setdefault("X-Content-Type-Options", "nosniff")
            resp.headers.setdefault("Referrer-Policy", "same-origin")
            resp.headers.setdefault("X-Frame-Options", "DENY")
            if request.is_secure:
                resp.headers.setdefault("Strict-Transport-Security", "max-age=15552000")
        return resp

    @app.get("/login")
    def login_page():
        if not enabled() or current_user():
            return redirect("/")
        resp = Response(LOGIN_HTML, mimetype="text/html")
        resp.headers["Cache-Control"] = "no-store"
        return resp

    @app.post("/api/login")
    def login():
        if not enabled():
            return jsonify({"ok": True})
        ip, now = _client_ip(), time.time()
        with _lock:
            recent = [t for t in _fails.get(ip, []) if now - t < 300]
            _fails[ip] = recent
            if len(recent) >= 8:
                return jsonify({"error": "Too many wrong codes. Wait a few minutes and try again."}), 429
        code = str((request.get_json(silent=True) or {}).get("code", "")).strip()
        who = None
        for name, c in _users.items():                # compare against everyone, so timing says nothing about which code was close
            if hmac.compare_digest(code.encode(), c.encode()):
                who = name
        if not who:
            with _lock:
                _fails.setdefault(ip, []).append(now)
            time.sleep(0.6)
            return jsonify({"error": "That code isn't right."}), 401
        with _lock:
            _fails.pop(ip, None)
        exp = int(now) + TTL
        resp = jsonify({"ok": True, "user": who})
        resp.set_cookie(COOKIE, _token(who, _users[who], exp), max_age=TTL, httponly=True, samesite="Lax", secure=request.is_secure)
        return resp

    @app.post("/api/logout")
    def logout():
        resp = jsonify({"ok": True})
        resp.delete_cookie(COOKIE)
        return resp


LOGIN_HTML = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover"><title>Story Factory - sign in</title>
<meta name="theme-color" content="#7c5cff"><link rel="manifest" href="/manifest.webmanifest"><link rel="icon" href="/icons/icon-192.png">
<link rel="apple-touch-icon" href="/icons/apple-touch-icon.png">
<style>:root{color-scheme:light dark}*{box-sizing:border-box}
body{margin:0;min-height:100vh;display:grid;place-items:center;background:#f4f1ff;font-family:system-ui,Segoe UI,Roboto,sans-serif;color:#1d1b2e;padding:16px}
.c{background:#fff;border-radius:20px;padding:28px;width:min(380px,100%);box-shadow:0 10px 40px #5b3df522}
.logo{width:48px;height:48px;border-radius:14px;background:linear-gradient(135deg,#7c5cff,#ff5ca8);display:grid;place-items:center;color:#fff;font-size:24px;margin-bottom:12px}
h1{font-size:21px;margin:0 0 6px}p{margin:0 0 18px;color:#666;font-size:14px;line-height:1.45}
input{width:100%;padding:13px 14px;border:1.5px solid #d9d3f5;border-radius:12px;font-size:16px;background:#fff;color:inherit}
button{margin-top:12px;width:100%;padding:13px;border:0;border-radius:12px;background:linear-gradient(135deg,#7c5cff,#ff5ca8);color:#fff;font-weight:700;font-size:16px;cursor:pointer}
.e{color:#c0264b;font-size:13.5px;min-height:20px;margin-top:10px}
@media (prefers-color-scheme:dark){body{background:#0e1124;color:#e8eaf8}.c{background:#171b36;box-shadow:0 10px 40px #0008}p{color:#9ba1c6}input{background:#11142b;border-color:#2a2f55}.e{color:#ff8ea3}}</style></head>
<body><form class="c" id="f"><div class="logo">&#10022;</div><h1>Story Factory</h1><p>Enter your personal access code to continue.</p>
<input id="code" type="password" autocomplete="current-password" placeholder="Access code" autofocus>
<button>Enter</button><div class="e" id="e" role="alert"></div></form>
<script>document.getElementById('f').onsubmit=async ev=>{ev.preventDefault();const e=document.getElementById('e');e.textContent='';
try{const r=await fetch('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({code:document.getElementById('code').value})});
const d=await r.json().catch(()=>({}));if(r.ok)location.href='/';else e.textContent=d.error||'Something went wrong.';}catch{e.textContent='Cannot reach the server.';}}</script></body></html>"""
