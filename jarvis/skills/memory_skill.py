"""Memory tools — store, recall, search."""

from __future__ import annotations

from typing import Any

from jarvis.core.openrouter import openrouter
from jarvis.memory.store import memory
from jarvis.skills.base import Skill


class MemorySkill(Skill):
    name = "memory"
    TOOLS = [
        {
            "name": "memory_add",
            "description": "Store a lasting fact about the user or project",
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {"type": "string"},
                    "category": {"type": "string"},
                },
                "required": ["content"],
            },
        },
        {
            "name": "memory_search",
            "description": "Look up facts from local memory on demand",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
        {
            "name": "memory_delete",
            "description": "Delete a memory fact by id",
            "parameters": {
                "type": "object",
                "properties": {"id": {"type": "string"}},
                "required": ["id"],
            },
        },
    ]

    def handler(self, args: dict) -> Any:
        if "id" in args and "content" not in args and "query" not in args:
            memory.delete(args["id"])
            return {"ok": True}
        if "query" in args:
            hits = memory.search(args["query"])
            # optional OpenRouter re-rank / summarise
            payload = [{"id": h.id, "content": h.content, "category": h.category, "created_at": h.created_at} for h in hits]
            if openrouter.available and hits:
                try:
                    summary = openrouter.complete(
                        f"Query: {args['query']}\nFacts:\n{payload}\nReturn the most relevant facts briefly.",
                        module="memory",
                    )
                    return {"ok": True, "facts": payload, "summary": summary}
                except Exception:
                    pass
            return {"ok": True, "facts": payload}
        content = args.get("content", "")
        if content:
            fact = memory.add(content, category=args.get("category") or "general")
            return {"ok": True, "id": fact.id}
        return {"ok": False, "error": "no action"}
