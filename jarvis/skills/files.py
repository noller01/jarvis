"""File management + advanced file processor."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from jarvis.agent.undo import undo_stack
from jarvis.core.gemini import generate_text, generate_with_image
from jarvis.skills.base import Skill


class FilesSkill(Skill):
    name = "files"
    TOOLS = [
        {
            "name": "file_list",
            "description": "List files in a directory",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        },
        {
            "name": "file_read",
            "description": "Read a text file (truncated for large files)",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}, "max_chars": {"type": "integer"}},
                "required": ["path"],
            },
        },
        {
            "name": "file_write",
            "description": "Write text to a file (undoable)",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
                "required": ["path", "content"],
            },
        },
        {
            "name": "file_move",
            "description": "Move or rename a file (undoable)",
            "parameters": {
                "type": "object",
                "properties": {"src": {"type": "string"}, "dst": {"type": "string"}},
                "required": ["src", "dst"],
            },
        },
        {
            "name": "file_delete",
            "description": "Delete a file (moves to undo backup first)",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        },
        {
            "name": "file_analyze",
            "description": "Summarize or answer questions about a local file (PDF, code, image)",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "question": {"type": "string"},
                },
                "required": ["path"],
            },
        },
        {
            "name": "undo_last",
            "description": "Undo the last file or settings change JARVIS made",
            "parameters": {"type": "object", "properties": {}},
        },
    ]

    def handler(self, args: dict) -> Any:
        if "content" in args and "path" in args and "src" not in args:
            return self._write(args["path"], args["content"])
        if "src" in args and "dst" in args:
            return self._move(args["src"], args["dst"])
        if "question" in args or (
            "path" in args
            and Path(args["path"]).suffix.lower() in {".pdf", ".png", ".jpg", ".jpeg", ".webp", ".gif"}
        ):
            if "question" in args or args.get("_tool") == "file_analyze":
                return self._analyze(args["path"], args.get("question", "Summarize this file."))
        if args.get("_tool") == "undo_last" or args.get("action") == "undo":
            return {"ok": True, "result": undo_stack.undo_last()}
        if args.get("_tool") == "file_delete" or args.get("delete"):
            return self._delete(args["path"])
        if args.get("_tool") == "file_read" or args.get("max_chars") is not None:
            return self._read(args["path"], int(args.get("max_chars") or 12000))
        if "path" in args:
            p = Path(args["path"])
            if p.is_dir() or args.get("_tool") == "file_list":
                return self._list(args["path"])
            return self._read(args["path"], int(args.get("max_chars") or 12000))
        return {"ok": False, "error": "ambiguous file args"}

    def _list(self, path: str) -> dict:
        p = Path(path).expanduser()
        if not p.exists():
            return {"ok": False, "error": "not found"}
        items = []
        for c in sorted(p.iterdir())[:200]:
            items.append({"name": c.name, "dir": c.is_dir(), "size": c.stat().st_size if c.is_file() else 0})
        return {"ok": True, "items": items}

    def _read(self, path: str, max_chars: int) -> dict:
        p = Path(path).expanduser()
        if not p.exists():
            return {"ok": False, "error": "not found"}
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
            return {"ok": True, "content": text[:max_chars], "truncated": len(text) > max_chars}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def _write(self, path: str, content: str) -> dict:
        p = Path(path).expanduser()
        prev = p.read_bytes() if p.exists() else None
        undo_stack.record_file_write(p, prev)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        if prev is None:
            undo_stack.record_file_create(p)
        return {"ok": True, "path": str(p)}

    def _move(self, src: str, dst: str) -> dict:
        s, d = Path(src).expanduser(), Path(dst).expanduser()
        undo_stack.record_file_move(s, d)
        d.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(s), str(d))
        return {"ok": True, "src": str(s), "dst": str(d)}

    def _delete(self, path: str) -> dict:
        p = Path(path).expanduser()
        if not p.exists():
            return {"ok": False, "error": "not found"}
        prev = p.read_bytes() if p.is_file() else None
        if prev is not None:
            undo_stack.record_file_write(p, prev)
        p.unlink()
        return {"ok": True, "path": str(p), "note": "Undo restores file contents"}

    def _analyze(self, path: str, question: str) -> dict:
        p = Path(path).expanduser()
        if not p.exists():
            return {"ok": False, "error": "not found"}
        suffix = p.suffix.lower()
        try:
            if suffix in {".png", ".jpg", ".jpeg", ".webp", ".gif"}:
                text = generate_with_image(question, p.read_bytes(), mime=f"image/{suffix.lstrip('.')}")
                return {"ok": True, "answer": text}
            if suffix == ".pdf":
                from PyPDF2 import PdfReader

                reader = PdfReader(str(p))
                pages = []
                for page in reader.pages[:30]:
                    pages.append(page.extract_text() or "")
                blob = "\n".join(pages)[:20000]
                ans = generate_text(
                    f"File: {p.name}\n\n{blob}\n\nQuestion: {question}",
                    module="file_processor",
                    prefer_openrouter=True,
                )
                return {"ok": True, "answer": ans}
            text = p.read_text(encoding="utf-8", errors="replace")[:20000]
            ans = generate_text(
                f"File: {p.name}\n\n{text}\n\nQuestion: {question}",
                module="file_processor",
                prefer_openrouter=True,
            )
            return {"ok": True, "answer": ans}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}
