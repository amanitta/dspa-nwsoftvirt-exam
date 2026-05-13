"""
A5 – 3-tier demo: Flask REST API for a personal expense tracker.

Routes (all consumed by the nginx reverse-proxy under /api/):
  GET    /health              → liveness probe used by Docker healthcheck
  GET    /expenses            → list all expenses ordered by date DESC
  POST   /expenses            → add expense  {amount, category, description, date?}
  DELETE /expenses/<id>       → delete expense by id
  GET    /expenses/summary    → per-category aggregates (GROUP BY in SQL)

Network isolation:
  - Reachable from frontend-net  (nginx → api)
  - Reaches db via db-net         (api  → db)
  The DB port is never exposed to nginx or to the host.
"""

import os
import time
import logging

import datetime
import decimal

import psycopg2
import psycopg2.extras
from flask import Flask, jsonify, request, abort

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)


class JSONEncoder(app.json_provider_class):
    """Serialize date/Decimal types that psycopg2 returns."""

    def default(self, o):
        if isinstance(o, (datetime.date, datetime.datetime)):
            return o.isoformat()
        if isinstance(o, decimal.Decimal):
            return str(o)
        return super().default(o)


app.json_provider_class = JSONEncoder
app.json = JSONEncoder(app)

#region DB access

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


CATEGORIES = [
    "Alimentari", "Trasporti", "Salute", "Intrattenimento",
    "Utenze", "Abbigliamento", "Istruzione", "Altro",
]


def init_db(retries: int = 10, delay: float = 2.0) -> None:
    """Create the expenses table if it does not exist; retry on connection error."""
    for attempt in range(1, retries + 1):
        try:
            conn = get_db()
            with conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        CREATE TABLE IF NOT EXISTS expenses (
                            id          SERIAL PRIMARY KEY,
                            amount      NUMERIC(10,2) NOT NULL CHECK (amount > 0),
                            category    TEXT NOT NULL,
                            description TEXT NOT NULL,
                            expense_date DATE NOT NULL DEFAULT CURRENT_DATE,
                            created_at  TIMESTAMPTZ DEFAULT NOW()
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


#region Routes

@app.get("/health")
def health():
    """Liveness probe: also checks DB connectivity."""
    try:
        conn = get_db()
        conn.close()
        return jsonify({"status": "ok", "db": "reachable"})
    except Exception as exc:  # noqa: BLE001
        return jsonify({"status": "error", "db": str(exc)}), 503


@app.get("/expenses/summary")
def expenses_summary():
    """Per-category aggregates computed entirely in PostgreSQL (GROUP BY)."""
    conn = get_db()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT
                    category,
                    COUNT(*)                        AS count,
                    SUM(amount)                     AS total,
                    ROUND(AVG(amount), 2)           AS avg,
                    MIN(amount)                     AS min,
                    MAX(amount)                     AS max
                FROM expenses
                GROUP BY category
                ORDER BY total DESC
                """
            )
            rows = cur.fetchall()
        # grand total across all categories
        grand = {
            "count": sum(r["count"] for r in rows),
            "total": sum(r["total"] for r in rows),
        }
        return jsonify({"by_category": [dict(r) for r in rows], "grand_total": grand})
    finally:
        conn.close()


@app.get("/expenses")
def list_expenses():
    conn = get_db()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, amount, category, description,
                       expense_date, created_at
                FROM expenses
                ORDER BY expense_date DESC, id DESC
                """
            )
            rows = cur.fetchall()
        return jsonify([dict(r) for r in rows])
    finally:
        conn.close()


@app.post("/expenses")
def create_expense():
    data = request.get_json(silent=True) or {}

    #region validation
    try:
        amount = float(data.get("amount", 0))
        if amount <= 0:
            raise ValueError
    except (TypeError, ValueError):
        abort(400, description="'amount' must be a positive number.")

    category = (data.get("category") or "").strip()
    if not category:
        abort(400, description="'category' is required.")

    description = (data.get("description") or "").strip()
    if not description:
        abort(400, description="'description' is required.")

    expense_date = (data.get("date") or "").strip() or None  # None → DEFAULT CURRENT_DATE

    conn = get_db()
    try:
        with conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """
                    INSERT INTO expenses (amount, category, description, expense_date)
                    VALUES (%s, %s, %s, COALESCE(%s::date, CURRENT_DATE))
                    RETURNING id, amount, category, description, expense_date, created_at
                    """,
                    (amount, category, description, expense_date),
                )
                row = cur.fetchone()
        return jsonify(dict(row)), 201
    finally:
        conn.close()


@app.delete("/expenses/<int:expense_id>")
def delete_expense(expense_id: int):
    conn = get_db()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM expenses WHERE id = %s RETURNING id", (expense_id,)
                )
                deleted = cur.fetchone()
        if deleted is None:
            abort(404, description=f"Expense {expense_id} not found.")
        return jsonify({"deleted": expense_id})
    finally:
        conn.close()


#region Entry point

if __name__ == "__main__":
    init_db()
    # Listen on all interfaces so Docker can reach this from other containers
    app.run(host="0.0.0.0", port=5000)
