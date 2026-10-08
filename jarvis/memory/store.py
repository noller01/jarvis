"""Unlimited local memory — prompt carries what fits; rest is searched on demand."""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jarvis.config import DATA


@dataclass
class MemoryFact:
    id: str
    content: str
    category: str
    created_at: float
    source: str
    meta: dict


class MemoryStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or (DATA / "memory.db")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _conn(self) -> sqlite3.Connection:
        c = sqlite3.connect(str(self.path))
        c.row_factory = sqlite3.Row
        return c

    def _init(self) -> None:
        with self._conn() as c:
            c.execute(
                """
                CREATE TABLE IF NOT EXISTS facts (
                    id TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    category TEXT DEFAULT 'general',
                    created_at REAL,
                    source TEXT DEFAULT 'conversation',
                    meta TEXT DEFAULT '{}'
                )
                """
            )
            c.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS facts_fts
                USING fts5(content, category, id UNINDEXED)
                """
            )
            c.execute(
                """
                CREATE TABLE IF NOT EXISTS session_summaries (
                    id TEXT PRIMARY KEY,
                    summary TEXT,
                    created_at REAL,
                    consumed INTEGER DEFAULT 0
                )
                """
            )

    def add(self, content: str, category: str = "general", source: str = "conversation", **meta: Any) -> MemoryFact:
        fact = MemoryFact(
            id=str(uuid.uuid4()),
            content=content.strip(),
            category=category,
            created_at=time.time(),
            source=source,
            meta=meta,
        )
        with self._conn() as c:
            c.execute(
                "INSERT INTO facts VALUES (?,?,?,?,?,?)",
                (fact.id, fact.content, fact.category, fact.created_at, fact.source, json.dumps(fact.meta)),
            )
            c.execute(
                "INSERT INTO facts_fts(content, category, id) VALUES (?,?,?)",
                (fact.content, fact.category, fact.id),
            )
        return fact

    def delete(self, fact_id: str) -> None:
        with self._conn() as c:
            c.execute("DELETE FROM facts WHERE id=?", (fact_id,))
            c.execute("DELETE FROM facts_fts WHERE id=?", (fact_id,))

    def list_all(self) -> list[MemoryFact]:
        with self._conn() as c:
            rows = c.execute("SELECT * FROM facts ORDER BY created_at DESC").fetchall()
        return [self._row(r) for r in rows]

    def search(self, query: str, limit: int = 8) -> list[MemoryFact]:
        q = query.strip()
        if not q:
            return []
        with self._conn() as c:
            try:
                rows = c.execute(
                    "SELECT f.* FROM facts_fts fts JOIN facts f ON f.id=fts.id "
                    "WHERE facts_fts MATCH ? ORDER BY rank LIMIT ?",
                    (q, limit),
                ).fetchall()
            except sqlite3.OperationalError:
                rows = c.execute(
                    "SELECT * FROM facts WHERE content LIKE ? ORDER BY created_at DESC LIMIT ?",
                    (f"%{q}%", limit),
                ).fetchall()
        return [self._row(r) for r in rows]

    def prompt_slice(self, max_chars: int = 1800) -> str:
        facts = self.list_all()
        lines = []
        total = 0
        for f in facts:
            line = f"- [{f.category}] {f.content}"
            if total + len(line) > max_chars:
                break
            lines.append(line)
            total += len(line)
        return "\n".join(lines)

    def save_session_summary(self, summary: str) -> None:
        if not summary.strip():
            return
        with self._conn() as c:
            c.execute(
                "INSERT INTO session_summaries VALUES (?,?,?,0)",
                (str(uuid.uuid4()), summary.strip(), time.time()),
            )

    def consume_morning_summary(self) -> str | None:
        with self._conn() as c:
            row = c.execute(
                "SELECT * FROM session_summaries WHERE consumed=0 ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
            if not row:
                return None
            c.execute("UPDATE session_summaries SET consumed=1 WHERE id=?", (row["id"],))
            return row["summary"]

    @staticmethod
    def _row(r: sqlite3.Row) -> MemoryFact:
        return MemoryFact(
            id=r["id"],
            content=r["content"],
            category=r["category"],
            created_at=r["created_at"],
            source=r["source"],
            meta=json.loads(r["meta"] or "{}"),
        )


memory = MemoryStore()
