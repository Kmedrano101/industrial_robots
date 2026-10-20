"""Print job history.

One row per print, kept in SQLite under the data directory. Rows are
opened by the start endpoint (with the slice metadata the browser knows)
or, for prints started outside the web UI, by the first active state the
bridge sees; they are closed by the terminal state transitions
(COMPLETED / ERROR / back to IDLE after a cancel).

The store is driven from two threads — FastAPI handlers and the rclpy
executor — so every public method takes the lock and the connection is
opened with check_same_thread=False. Progress updates arrive at several
Hz and are kept in memory; only the terminal transition writes them out.
"""

from __future__ import annotations

import logging
import os
import sqlite3
import threading
import time
import uuid
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ur_3d_printer/msg/PrintState.msg
IDLE = 0
COMPLETED = 8
PAUSED = 9
CANCELLING = 10
ERROR = 11
ACTIVE_STATES = {1, 2, 3, 4, 5, 6, 7, 9}  # loading … layer change, paused

META_FIELDS = (
    "filename", "gcode_path", "material", "slicer_mode", "layer_height",
    "nozzle_diameter", "infill_pattern", "infill_density", "num_layers",
    "estimated_time",
)

# A job the bridge opened as "external" this recently is the one the web
# start endpoint is about to report: print_node leaves IDLE as soon as it
# starts parsing, but StartPrint only answers after validation and the
# wait for its services, which takes ~30 s. Sized above that.
ADOPT_WINDOW_S = 90.0

_SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    started_at REAL NOT NULL,
    finished_at REAL,
    status TEXT NOT NULL,            -- running | completed | cancelled | error
    filename TEXT,
    gcode_path TEXT,
    material TEXT,
    slicer_mode TEXT,
    layer_height REAL,
    nozzle_diameter REAL,
    infill_pattern TEXT,
    infill_density REAL,
    num_layers INTEGER,
    estimated_time REAL,
    layers_done INTEGER,
    elapsed_time REAL,
    error_message TEXT,
    source TEXT NOT NULL DEFAULT 'web'  -- web | external
);
CREATE INDEX IF NOT EXISTS jobs_started ON jobs(started_at DESC);
"""


class JobStore:
    def __init__(self, path: str):
        self.path = path
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        self._lock = threading.Lock()
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._current_id: Optional[str] = None
        self._last_state = IDLE
        self._layers_done = 0
        self._elapsed = 0.0
        with self._lock:
            self._db.executescript(_SCHEMA)
            # A backend restart mid-print leaves a row open with no process
            # to close it. Mark it so the history never shows a job that is
            # "running" for days.
            self._db.execute(
                "UPDATE jobs SET status='error', finished_at=?, "
                "error_message=COALESCE(error_message, 'backend restarted during print') "
                "WHERE status='running'",
                (time.time(),),
            )
            self._db.commit()

    # ── writes ───────────────────────────────────────────────────────────

    def start(self, meta: Optional[dict[str, Any]] = None, source: str = "web") -> dict[str, Any]:
        """Open a job for a print the web UI just started."""
        with self._lock:
            return self._start_locked(meta or {}, source)

    def annotate_recent(self, meta: dict[str, Any]) -> bool:
        """Attach the browser's metadata to the newest external job opened
        within the adoption window, running or not.

        For a start that print_node rejected after leaving IDLE (bad
        G-code, services missing): the bridge has already recorded and
        closed the attempt as an external error, and without this the
        history would show a nameless "ROS" row for a part the operator
        picked here."""
        with self._lock:
            row = self._db.execute(
                "SELECT id FROM jobs WHERE source='external' AND started_at > ? "
                "ORDER BY started_at DESC LIMIT 1",
                (time.time() - ADOPT_WINDOW_S,),
            ).fetchone()
            if row is None:
                return False
            sets = {k: v for k, v in meta.items() if k in META_FIELDS and v is not None}
            sets["source"] = "web"
            self._db.execute(
                "UPDATE jobs SET " + ", ".join(f"{k}=?" for k in sets) + " WHERE id=?",
                (*sets.values(), row["id"]),
            )
            self._db.commit()
            return True

    def request_cancel(self) -> None:
        """Kept for symmetry with the cancel endpoint; the transition back
        to IDLE is what actually closes the row."""

    def on_progress(self, current_layer: int, elapsed_time: float) -> None:
        # Memory only; persisted when the job closes.
        self._layers_done = int(current_layer)
        self._elapsed = float(elapsed_time)

    def on_print_state(self, state: int, error_message: str = "") -> None:
        """Apply a print_node state transition."""
        with self._lock:
            prev = self._last_state
            self._last_state = state
            if self._current_id is None:
                # A print the web UI did not start: record it anyway, so
                # the history is the history of the machine, not of the
                # browser. Leaving IDLE is the start; a resume (PAUSED →
                # PRINTING) is not.
                if state in ACTIVE_STATES and prev == IDLE and state != PAUSED:
                    self._start_locked({}, source="external")
                return
            if state == COMPLETED:
                self._finish_locked("completed", None)
            elif state == ERROR:
                self._finish_locked("error", error_message or "print error")
            elif state == IDLE and prev != IDLE:
                # Back to idle without COMPLETED: a cancel or an abort.
                self._finish_locked("cancelled", None)

    def delete(self, job_id: str) -> bool:
        with self._lock:
            if job_id == self._current_id:
                return False
            cur = self._db.execute("DELETE FROM jobs WHERE id=?", (job_id,))
            self._db.commit()
            return cur.rowcount > 0

    def clear_finished(self) -> int:
        with self._lock:
            cur = self._db.execute("DELETE FROM jobs WHERE status != 'running'")
            self._db.commit()
            return cur.rowcount

    # ── reads ────────────────────────────────────────────────────────────

    def current(self) -> Optional[dict[str, Any]]:
        with self._lock:
            return self._row_locked(self._current_id) if self._current_id else None

    def get(self, job_id: str) -> Optional[dict[str, Any]]:
        with self._lock:
            return self._row_locked(job_id)

    def list(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._db.execute(
                "SELECT * FROM jobs ORDER BY started_at DESC LIMIT ?", (int(limit),)
            ).fetchall()
            return [self._decorate(dict(r)) for r in rows]

    # ── internals (lock held) ────────────────────────────────────────────

    def _start_locked(self, meta: dict[str, Any], source: str) -> dict[str, Any]:
        now = time.time()
        cols = {k: meta.get(k) for k in META_FIELDS}
        current = self._row_locked(self._current_id) if self._current_id else None
        if current is not None:
            if (
                source == "web"
                and current["source"] == "external"
                and now - current["started_at"] < ADOPT_WINDOW_S
            ):
                # The bridge saw the state change before the start endpoint
                # got its answer: this is the same print. Fill in what the
                # browser knows instead of opening a duplicate.
                sets = {k: v for k, v in cols.items() if v is not None}
                sets["source"] = "web"
                self._db.execute(
                    "UPDATE jobs SET " + ", ".join(f"{k}=?" for k in sets) + " WHERE id=?",
                    (*sets.values(), self._current_id),
                )
                self._db.commit()
                return self._row_locked(self._current_id)  # type: ignore[return-value]
            # Two concurrent prints cannot exist on one robot.
            self._finish_locked("cancelled", None)
        job_id = uuid.uuid4().hex[:12]
        self._db.execute(
            "INSERT INTO jobs (id, started_at, status, source, "
            + ", ".join(cols)
            + ") VALUES (?, ?, 'running', ?, "
            + ", ".join("?" for _ in cols)
            + ")",
            (job_id, now, source, *cols.values()),
        )
        self._db.commit()
        self._current_id = job_id
        self._layers_done = 0
        self._elapsed = 0.0
        logger.info("job %s started (%s)", job_id, source)
        return self._row_locked(job_id)  # type: ignore[return-value]

    def _finish_locked(self, status: str, error_message: Optional[str]) -> None:
        if self._current_id is None:
            return
        self._db.execute(
            "UPDATE jobs SET status=?, finished_at=?, layers_done=?, elapsed_time=?, "
            "error_message=? WHERE id=?",
            (status, time.time(), self._layers_done, self._elapsed, error_message, self._current_id),
        )
        self._db.commit()
        logger.info("job %s finished: %s", self._current_id, status)
        self._current_id = None

    def _row_locked(self, job_id: Optional[str]) -> Optional[dict[str, Any]]:
        if job_id is None:
            return None
        r = self._db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        return self._decorate(dict(r)) if r else None

    def _decorate(self, row: dict[str, Any]) -> dict[str, Any]:
        if row["status"] == "running" and row["id"] == self._current_id:
            row["layers_done"] = self._layers_done
            row["elapsed_time"] = self._elapsed
        return row

    def close(self) -> None:
        with self._lock:
            self._db.close()
