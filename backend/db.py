"""SQLite persistence (standard library only).

Projects are stored as one JSON document each so the schema can evolve without
migrations; files, jobs, style profiles and references have their own tables so
they can be listed and filtered cheaply.
"""
from __future__ import annotations

import json
import shutil
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable

from . import config

_db_lock = threading.RLock()
_project_locks: dict[str, threading.RLock] = {}
_project_locks_guard = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
  id TEXT PRIMARY KEY, name TEXT, idea TEXT, created REAL, updated REAL, data TEXT
);
CREATE TABLE IF NOT EXISTS jobs (
  id TEXT PRIMARY KEY, project_id TEXT, type TEXT, label TEXT, status TEXT, stage TEXT,
  progress REAL, message TEXT, logs TEXT, error TEXT, result TEXT,
  created REAL, started REAL, finished REAL
);
CREATE TABLE IF NOT EXISTS files (
  id TEXT PRIMARY KEY, project_id TEXT, kind TEXT, name TEXT, path TEXT UNIQUE,
  mime TEXT, size INTEGER, created REAL, meta TEXT
);
CREATE TABLE IF NOT EXISTS styles (
  id TEXT PRIMARY KEY, name TEXT, created REAL, data TEXT
);
CREATE TABLE IF NOT EXISTS refs (
  id TEXT PRIMARY KEY, name TEXT, kind TEXT, path TEXT, thumb TEXT, created REAL, analysis TEXT
);
CREATE TABLE IF NOT EXISTS premises (
  id INTEGER PRIMARY KEY AUTOINCREMENT, created REAL, text TEXT
);
CREATE TABLE IF NOT EXISTS kv (key TEXT PRIMARY KEY, value TEXT);
"""


def new_id(prefix: str = "") -> str:
    return prefix + uuid.uuid4().hex[:10]


def _connect() -> sqlite3.Connection:
    con = sqlite3.connect(config.DB_PATH, timeout=30, check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA foreign_keys=ON")
    return con


def init() -> None:
    with _db_lock:
        con = _connect()
        try:
            con.executescript(SCHEMA)
            con.commit()
        finally:
            con.close()


def execute(sql: str, params: tuple | list = ()) -> int:
    with _db_lock:
        con = _connect()
        try:
            cur = con.execute(sql, params)
            con.commit()
            return cur.lastrowid or 0
        finally:
            con.close()


def query(sql: str, params: tuple | list = ()) -> list[dict]:
    with _db_lock:
        con = _connect()
        try:
            return [dict(r) for r in con.execute(sql, params).fetchall()]
        finally:
            con.close()


def one(sql: str, params: tuple | list = ()) -> dict | None:
    rows = query(sql, params)
    return rows[0] if rows else None


# ---------------------------------------------------------------- key/value settings
def get_settings() -> dict:
    settings = dict(config.DEFAULT_SETTINGS)
    for row in query("SELECT key, value FROM kv WHERE key LIKE 'setting.%'"):
        try:
            settings[row["key"][8:]] = json.loads(row["value"])
        except Exception:
            pass
    return settings


def set_settings(patch: dict) -> dict:
    allowed = set(config.DEFAULT_SETTINGS)
    for k, v in patch.items():
        if k in allowed:
            execute("INSERT OR REPLACE INTO kv(key,value) VALUES(?,?)", (f"setting.{k}", json.dumps(v)))
    return get_settings()


# ---------------------------------------------------------------- projects
def project_dir(pid: str) -> Path:
    d = config.PROJECTS_DIR / pid
    d.mkdir(parents=True, exist_ok=True)
    return d


def project_lock(pid: str) -> threading.RLock:
    with _project_locks_guard:
        return _project_locks.setdefault(pid, threading.RLock())


def _hydrate(row: dict) -> dict:
    data = json.loads(row["data"] or "{}")
    data.update({"id": row["id"], "name": row["name"], "idea": row["idea"],
                 "created": row["created"], "updated": row["updated"]})
    return data


def get_project(pid: str) -> dict | None:
    row = one("SELECT * FROM projects WHERE id=?", (pid,))
    return _hydrate(row) if row else None


def list_projects() -> list[dict]:
    out = []
    for row in query("SELECT * FROM projects ORDER BY updated DESC"):
        p = _hydrate(row)
        out.append({
            "id": p["id"], "name": p["name"], "idea": p["idea"], "created": p["created"],
            "updated": p["updated"], "title": (p.get("story") or {}).get("title"),
            "stages": {k: v.get("status") for k, v in (p.get("stages") or {}).items()},
            "has_video": bool((p.get("render") or {}).get("video_file_id")),
            "scenes": len(p.get("scenes") or []),
        })
    return out


def save_project(p: dict) -> dict:
    p["updated"] = time.time()
    data = {k: v for k, v in p.items() if k not in ("id", "name", "idea", "created", "updated")}
    with _db_lock:
        execute(
            "INSERT INTO projects(id,name,idea,created,updated,data) VALUES(?,?,?,?,?,?) "
            "ON CONFLICT(id) DO UPDATE SET name=excluded.name, idea=excluded.idea, "
            "updated=excluded.updated, data=excluded.data",
            (p["id"], p.get("name", "Untitled"), p.get("idea", ""), p.get("created", time.time()),
             p["updated"], json.dumps(data)),
        )
    return p


def update_project(pid: str, fn: Callable[[dict], Any]) -> dict:
    """Atomic read-modify-write. fn mutates the project dict in place."""
    with project_lock(pid):
        p = get_project(pid)
        if p is None:
            raise KeyError(f"project {pid} not found")
        fn(p)
        save_project(p)
        return p


def delete_project(pid: str) -> None:
    execute("DELETE FROM files WHERE project_id=?", (pid,))
    execute("DELETE FROM jobs WHERE project_id=?", (pid,))
    execute("DELETE FROM projects WHERE id=?", (pid,))
    shutil.rmtree(config.PROJECTS_DIR / pid, ignore_errors=True)


# ---------------------------------------------------------------- files
MIME = {".mp4": "video/mp4", ".mp3": "audio/mpeg", ".wav": "audio/wav", ".png": "image/png",
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp", ".json": "application/json",
        ".srt": "text/plain", ".ass": "text/plain", ".md": "text/markdown", ".txt": "text/plain",
        ".zip": "application/zip", ".mov": "video/quicktime", ".webm": "video/webm"}


def register_file(project_id: str | None, kind: str, path: Path, name: str | None = None,
                  meta: dict | None = None) -> dict:
    path = Path(path)
    rel = str(path.resolve().relative_to(config.DATA_DIR))
    existing = one("SELECT * FROM files WHERE path=?", (rel,))
    size = path.stat().st_size if path.exists() else 0
    mime = MIME.get(path.suffix.lower(), "application/octet-stream")
    if existing:
        execute("UPDATE files SET size=?, created=?, kind=?, meta=? WHERE id=?",
                (size, time.time(), kind, json.dumps(meta or {}), existing["id"]))
        fid = existing["id"]
    else:
        fid = new_id("f_")
        execute("INSERT INTO files(id,project_id,kind,name,path,mime,size,created,meta) VALUES(?,?,?,?,?,?,?,?,?)",
                (fid, project_id, kind, name or path.name, rel, mime, size, time.time(), json.dumps(meta or {})))
    return get_file(fid)


def _file_out(row: dict) -> dict:
    row = dict(row)
    row["meta"] = json.loads(row.get("meta") or "{}")
    row["url"] = f"/files/{row['id']}"
    return row


def get_file(fid: str) -> dict | None:
    row = one("SELECT * FROM files WHERE id=?", (fid,))
    return _file_out(row) if row else None


def list_files(project_id: str | None = None, kind: str | None = None) -> list[dict]:
    sql, args = "SELECT * FROM files WHERE 1=1", []
    if project_id:
        sql += " AND project_id=?"
        args.append(project_id)
    if kind:
        sql += " AND kind=?"
        args.append(kind)
    sql += " ORDER BY created DESC"
    return [_file_out(r) for r in query(sql, args)]


def file_path(f: dict) -> Path:
    return config.DATA_DIR / f["path"]


def delete_file(fid: str) -> bool:
    f = get_file(fid)
    if not f:
        return False
    try:
        file_path(f).unlink(missing_ok=True)
    except Exception:
        pass
    execute("DELETE FROM files WHERE id=?", (fid,))
    return True


def rename_file(fid: str, name: str) -> dict | None:
    execute("UPDATE files SET name=? WHERE id=?", (name, fid))
    return get_file(fid)


# ---------------------------------------------------------------- styles / references / premises
def list_styles() -> list[dict]:
    return [{**json.loads(r["data"]), "id": r["id"], "name": r["name"], "created": r["created"]}
            for r in query("SELECT * FROM styles ORDER BY created DESC")]


def get_style(sid: str | None) -> dict | None:
    if not sid:
        return None
    r = one("SELECT * FROM styles WHERE id=?", (sid,))
    return {**json.loads(r["data"]), "id": r["id"], "name": r["name"], "created": r["created"]} if r else None


def save_style(style: dict) -> dict:
    sid = style.get("id") or new_id("s_")
    data = {k: v for k, v in style.items() if k not in ("id", "name", "created")}
    execute("INSERT INTO styles(id,name,created,data) VALUES(?,?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name, data=excluded.data",
            (sid, style.get("name", "Untitled style"), time.time(), json.dumps(data)))
    return get_style(sid)


def delete_style(sid: str) -> None:
    execute("DELETE FROM styles WHERE id=?", (sid,))


def list_refs() -> list[dict]:
    out = []
    for r in query("SELECT * FROM refs ORDER BY created DESC"):
        r["analysis"] = json.loads(r["analysis"]) if r["analysis"] else None
        out.append(r)
    return out


def get_ref(rid: str) -> dict | None:
    r = one("SELECT * FROM refs WHERE id=?", (rid,))
    if r:
        r["analysis"] = json.loads(r["analysis"]) if r["analysis"] else None
    return r


def remember_premise(text: str) -> None:
    execute("INSERT INTO premises(created,text) VALUES(?,?)", (time.time(), text[:400]))


def recent_premises(n: int = 25) -> list[str]:
    return [r["text"] for r in query("SELECT text FROM premises ORDER BY id DESC LIMIT ?", (n,))]
