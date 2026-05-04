"""
A5 – 3-tier demo: Flask REST API for a simple notes board.

Routes (all consumed by the nginx reverse-proxy under /api/):
  GET  /health       → liveness probe used by Docker healthcheck
  GET  /notes        → list all notes (JSON array)
  POST /notes        → create a new note  (body: {"content": "..."})
  DELETE /notes/<id> → delete note by id

Network isolation:
  - Reachable from frontend-net  (nginx → api)
  - Reaches db via backend-net   (api  → db)
  The DB port is never exposed to nginx or to the host.
"""

import os
import time
import logging

import psycopg2
import psycopg2.extras
from flask import Flask, jsonify, request, abort

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# ── Database connection ────────────────────────────────────────────────────────

DSN = {
    "host": os.environ["DB_HOST"],
    "port": int(os.environ.get("DB_PORT", 5432)),
    "dbname": os.environ["DB_NAME"],
    "user": os.environ["DB_USER"],
    "password": os.environ["DB_PASSWORD"],
}


def get_db():
    """Return a fresh connection; caller must close it."""
    return psycopg2.connect(**DSN)


def init_db(retries: int = 10, delay: float = 2.0) -> None:
    """Create the notes table if it does not exist; retry on connection error."""
    for attempt in range(1, retries + 1):
        try:
            conn = get_db()
            with conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        CREATE TABLE IF NOT EXISTS notes (
                            id         SERIAL PRIMARY KEY,
                            content    TEXT NOT NULL,
                            created_at TIMESTAMPTZ DEFAULT NOW()
                        )
                        """
                    )
            conn.close()
            logger.info("Database initialised successfully.")
            return
        except psycopg2.OperationalError as exc:
            logger.warning("DB not ready (attempt %d/%d): %s", attempt, retries, exc)
            time.sleep(delay)
    raise RuntimeError("Could not connect to the database after %d attempts." % retries)


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    """Liveness probe: also checks DB connectivity."""
    try:
        conn = get_db()
        conn.close()
        return jsonify({"status": "ok", "db": "reachable"})
    except Exception as exc:  # noqa: BLE001
        return jsonify({"status": "error", "db": str(exc)}), 503


@app.get("/notes")
def list_notes():
    conn = get_db()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT id, content, created_at FROM notes ORDER BY id DESC")
            rows = cur.fetchall()
        return jsonify([dict(r) for r in rows])
    finally:
        conn.close()


@app.post("/notes")
def create_note():
    data = request.get_json(silent=True) or {}
    content = (data.get("content") or "").strip()
    if not content:
        abort(400, description="'content' field is required and must not be empty.")

    conn = get_db()
    try:
        with conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "INSERT INTO notes (content) VALUES (%s) RETURNING id, content, created_at",
                    (content,),
                )
                row = cur.fetchone()
        return jsonify(dict(row)), 201
    finally:
        conn.close()


@app.delete("/notes/<int:note_id>")
def delete_note(note_id: int):
    conn = get_db()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM notes WHERE id = %s RETURNING id", (note_id,))
                deleted = cur.fetchone()
        if deleted is None:
            abort(404, description=f"Note {note_id} not found.")
        return jsonify({"deleted": note_id})
    finally:
        conn.close()


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    init_db()
    # Listen on all interfaces so Docker can reach this from other containers
    app.run(host="0.0.0.0", port=5000)
