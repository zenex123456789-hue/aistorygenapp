"""Background job runner with persisted progress.

Jobs run on a small thread pool. The browser polls /api/jobs/<id>. A job can be
cancelled cooperatively: long-running code calls ctx.check_cancel().
"""
from __future__ import annotations

import json
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from typing import Callable

from . import db


class Cancelled(Exception):
    pass


_cancel_flags: dict[str, threading.Event] = {}
_pool = ThreadPoolExecutor(max_workers=3, thread_name_prefix="job")
_render_lock = threading.Lock()  # only one heavy render at a time


class JobContext:
    def __init__(self, job_id: str, project_id: str | None):
        self.job_id = job_id
        self.project_id = project_id
        self._logs: list[str] = []
        self._last_write = 0.0

    # -- progress -----------------------------------------------------------
    def update(self, progress: float | None = None, message: str | None = None, stage: str | None = None,
               force: bool = False) -> None:
        self.check_cancel()
        fields, args = [], []
        if progress is not None:
            fields.append("progress=?")
            args.append(max(0.0, min(100.0, float(progress))))
        if message is not None:
            fields.append("message=?")
            args.append(message)
        if stage is not None:
            fields.append("stage=?")
            args.append(stage)
        if not fields:
            return
        now = time.time()
        if not force and now - self._last_write < 0.15:
            return
        self._last_write = now
        db.execute(f"UPDATE jobs SET {', '.join(fields)} WHERE id=?", (*args, self.job_id))

    def log(self, line: str) -> None:
        self._logs.append(f"[{time.strftime('%H:%M:%S')}] {line}")
        self._logs = self._logs[-300:]
        db.execute("UPDATE jobs SET logs=? WHERE id=?", (json.dumps(self._logs), self.job_id))

    def check_cancel(self) -> None:
        ev = _cancel_flags.get(self.job_id)
        if ev is not None and ev.is_set():
            raise Cancelled()


def submit(project_id: str | None, job_type: str, label: str,
           fn: Callable[[JobContext], dict | None], heavy: bool = False) -> dict:
    job_id = db.new_id("j_")
    db.execute(
        "INSERT INTO jobs(id,project_id,type,label,status,stage,progress,message,logs,error,result,created) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
        (job_id, project_id, job_type, label, "queued", "", 0.0, "Queued", "[]", "", "null", time.time()),
    )
    _cancel_flags[job_id] = threading.Event()

    def runner() -> None:
        ctx = JobContext(job_id, project_id)
        lock = _render_lock if heavy else None
        if lock:
            db.execute("UPDATE jobs SET message=? WHERE id=?", ("Waiting for another render to finish…", job_id))
            lock.acquire()
        try:
            if _cancel_flags[job_id].is_set():
                raise Cancelled()
            db.execute("UPDATE jobs SET status='running', started=?, message='Starting…' WHERE id=?",
                       (time.time(), job_id))
            result = fn(ctx) or {}
            status = result.pop("_status", "succeeded") if isinstance(result, dict) else "succeeded"
            db.execute("UPDATE jobs SET status=?, progress=100, finished=?, result=?, message=? WHERE id=?",
                       (status, time.time(), json.dumps(result), result.get("message", "Done"), job_id))
        except Cancelled:
            db.execute("UPDATE jobs SET status='cancelled', finished=?, message='Cancelled' WHERE id=?",
                       (time.time(), job_id))
        except Exception as exc:  # noqa: BLE001 - surface every failure to the UI
            tb = traceback.format_exc()
            ctx.log("ERROR: " + str(exc))
            db.execute("UPDATE jobs SET status='failed', finished=?, error=?, message=? WHERE id=?",
                       (time.time(), f"{type(exc).__name__}: {exc}", f"Failed: {exc}", job_id))
            print(tb)
        finally:
            if lock:
                lock.release()
            _cancel_flags.pop(job_id, None)

    _pool.submit(runner)
    return get(job_id)


def cancel(job_id: str) -> bool:
    ev = _cancel_flags.get(job_id)
    if ev:
        ev.set()
        return True
    return False


def _out(row: dict) -> dict:
    row = dict(row)
    row["logs"] = json.loads(row.get("logs") or "[]")
    row["result"] = json.loads(row.get("result") or "null")
    return row


def get(job_id: str) -> dict | None:
    row = db.one("SELECT * FROM jobs WHERE id=?", (job_id,))
    return _out(row) if row else None


def list_jobs(project_id: str | None = None, limit: int = 30) -> list[dict]:
    if project_id:
        rows = db.query("SELECT * FROM jobs WHERE project_id=? ORDER BY created DESC LIMIT ?", (project_id, limit))
    else:
        rows = db.query("SELECT * FROM jobs ORDER BY created DESC LIMIT ?", (limit,))
    return [_out(r) for r in rows]


def recover_interrupted() -> None:
    """Called on startup: jobs that were running when the server stopped cannot resume."""
    db.execute("UPDATE jobs SET status='failed', error='Interrupted by server restart', "
               "message='Interrupted by server restart', finished=? WHERE status IN ('queued','running')",
               (time.time(),))
