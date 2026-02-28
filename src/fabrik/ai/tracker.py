import sqlite3
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .client import LLMResponse


class UsageTracker:
    def __init__(self, db_path: str | None = None):
        if db_path is None:
            self.db_path = str(Path.home() / ".fabrik" / "ai_usage.db")
        else:
            self.db_path = db_path
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ai_usage (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    model TEXT NOT NULL,
                    tokens_in INTEGER NOT NULL,
                    tokens_out INTEGER NOT NULL,
                    cost_usd REAL NOT NULL,
                    duration_ms INTEGER,
                    project TEXT
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON ai_usage(timestamp)")
            conn.commit()

    def record(self, response: "LLMResponse", project: str | None = None):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO ai_usage (
                    timestamp, provider, model, tokens_in, tokens_out, cost_usd, duration_ms, project
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    datetime.utcnow().isoformat(),
                    response.provider.value,
                    response.model,
                    response.tokens_in,
                    response.tokens_out,
                    response.cost,
                    response.duration_ms,
                    project,
                ),
            )
            conn.commit()

    def get_usage(self, month: str | None = None, project: str | None = None) -> dict:
        query = "SELECT * FROM ai_usage WHERE 1=1"
        params: list[str] = []
        if month:
            query += " AND timestamp LIKE ?"
            params.append(f"{month}%")
        if project:
            query += " AND project = ?"
            params.append(project)

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(query, params).fetchall()

        total_cost = 0.0
        total_tokens_in = 0
        total_tokens_out = 0
        total_calls = len(rows)
        by_model: dict = {}

        for row in rows:
            model = row["model"]
            cost = row["cost_usd"]
            tokens_in = row["tokens_in"]
            tokens_out = row["tokens_out"]

            total_cost += cost
            total_tokens_in += tokens_in
            total_tokens_out += tokens_out

            if model not in by_model:
                by_model[model] = {"calls": 0, "cost": 0.0, "tokens_in": 0, "tokens_out": 0}

            by_model[model]["calls"] += 1
            by_model[model]["cost"] += cost
            by_model[model]["tokens_in"] += tokens_in
            by_model[model]["tokens_out"] += tokens_out

        return {
            "total_calls": total_calls,
            "total_cost": total_cost,
            "total_tokens_in": total_tokens_in,
            "total_tokens_out": total_tokens_out,
            "by_model": by_model,
        }
