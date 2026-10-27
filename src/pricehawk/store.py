"""Local SQLite storage: price log, watchlist and purchase log.

Lives at ~/.pricehawk/pricehawk.db (override with PRICEHAWK_DB).
"""

from __future__ import annotations

import json
import os
import sqlite3
import statistics
import time
from pathlib import Path
from typing import Any

from .models import Offer

SCHEMA = """
CREATE TABLE IF NOT EXISTS prices (
    ts REAL NOT NULL, query TEXT NOT NULL, title TEXT NOT NULL,
    store TEXT NOT NULL, price REAL NOT NULL, source TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS prices_query ON prices(query, ts);
CREATE TABLE IF NOT EXISTS watchlist (
    id INTEGER PRIMARY KEY AUTOINCREMENT, query TEXT NOT NULL, target REAL NOT NULL,
    created REAL NOT NULL, last_best REAL, last_checked REAL
);
CREATE TABLE IF NOT EXISTS purchases (
    id TEXT PRIMARY KEY, created REAL NOT NULL, status TEXT NOT NULL, data TEXT NOT NULL
);
"""


def _norm(q: str) -> str:
    return " ".join(q.lower().split())


class Store:
    def __init__(self, path: str | None = None):
        path = path or os.environ.get("PRICEHAWK_DB") or str(Path.home() / ".pricehawk" / "pricehawk.db")
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)

    # ---- price log -----------------------------------------------------------

    def log_prices(self, query: str, offers: list[Offer]) -> None:
        now = time.time()
        self.db.executemany(
            "INSERT INTO prices VALUES (?,?,?,?,?,?)",
            [(now, _norm(query), o.title, o.store, o.price, o.source) for o in offers],
        )
        self.db.commit()

    def daily_lows(self, query: str, days: int) -> list[dict[str, Any]]:
        since = time.time() - days * 86400
        rows = self.db.execute(
            "SELECT date(ts, 'unixepoch') AS day, MIN(price) AS low, COUNT(*) AS listings "
            "FROM prices WHERE query = ? AND ts >= ? GROUP BY day ORDER BY day",
            (_norm(query), since),
        ).fetchall()
        return [dict(r) for r in rows]

    def sale_check(self, query: str, current_low: float) -> dict[str, Any] | None:
        """Is today's best price actually low compared with the last 30 days?"""
        lows = [r["low"] for r in self.daily_lows(query, 30)]
        if len(lows) < 3:
            return None
        typical = statistics.median(lows)
        change = (current_low - typical) / typical
        if change <= -0.08:
            verdict = "Genuinely low: below its usual price for the last 30 days."
        elif change >= 0.05:
            verdict = "Higher than usual. Waiting may pay off."
        else:
            verdict = "Normal price. Any 'sale' label is not unusual for this item."
        return {"typical_30d_low": round(typical, 2), "change_pct": round(change * 100, 1), "verdict": verdict}

    # ---- watchlist -----------------------------------------------------------

    def watch(self, query: str, target: float) -> int:
        cur = self.db.execute(
            "INSERT INTO watchlist (query, target, created) VALUES (?,?,?)", (query.strip(), target, time.time())
        )
        self.db.commit()
        return int(cur.lastrowid or 0)

    def watches(self) -> list[dict[str, Any]]:
        return [dict(r) for r in self.db.execute("SELECT * FROM watchlist ORDER BY id")]

    def update_watch(self, watch_id: int, best: float) -> None:
        self.db.execute("UPDATE watchlist SET last_best=?, last_checked=? WHERE id=?", (best, time.time(), watch_id))
        self.db.commit()

    def unwatch(self, watch_id: int) -> bool:
        cur = self.db.execute("DELETE FROM watchlist WHERE id=?", (watch_id,))
        self.db.commit()
        return cur.rowcount > 0

    # ---- purchases -----------------------------------------------------------

    def save_purchase(self, pid: str, status: str, data: dict[str, Any]) -> None:
        self.db.execute(
            "INSERT OR REPLACE INTO purchases VALUES (?,?,?,?)",
            (pid, data.get("created", time.time()), status, json.dumps(data)),
        )
        self.db.commit()

    def purchase(self, pid: str) -> dict[str, Any] | None:
        row = self.db.execute("SELECT * FROM purchases WHERE id=?", (pid,)).fetchone()
        if not row:
            return None
        d = json.loads(row["data"])
        d["status"] = row["status"]
        return d

    def purchases(self, limit: int = 20) -> list[dict[str, Any]]:
        rows = self.db.execute("SELECT * FROM purchases ORDER BY created DESC LIMIT ?", (limit,))
        out = []
        for r in rows:
            d = json.loads(r["data"])
            d["status"] = r["status"]
            out.append(d)
        return out
