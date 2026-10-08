"""Visual awareness — screen + webcam."""

from __future__ import annotations

from typing import Any

from jarvis.config import DATA
from jarvis.core.gemini import generate_with_image
from jarvis.skills.base import Skill


class VisionSkill(Skill):
    name = "vision"
    TOOLS = [
        {
            "name": "see_screen",
            "description": "Capture the screen and answer a question about it",
            "parameters": {
                "type": "object",
                "properties": {"question": {"type": "string"}},
            },
        },
        {
            "name": "see_webcam",
            "description": "Capture a webcam frame and describe / answer",
            "parameters": {
                "type": "object",
                "properties": {"question": {"type": "string"}},
            },
        },
    ]

    def handler(self, args: dict) -> Any:
        q = args.get("question") or "Describe what you see."
        if args.get("_tool") == "see_webcam" or args.get("webcam"):
            return self._webcam(q)
        return self._screen(q)

    def _screen(self, question: str) -> dict:
        import mss

        path = DATA / "uploads" / "vision_screen.png"
        with mss.mss() as sct:
            sct.shot(output=str(path))
        ans = generate_with_image(question, path.read_bytes())
        return {"ok": True, "answer": ans, "path": str(path)}

    def _webcam(self, question: str) -> dict:
        try:
            import cv2
        except ImportError:
            return {"ok": False, "error": "opencv not installed"}
        cam = cv2.VideoCapture(0)
        ok, frame = cam.read()
        cam.release()
        if not ok:
            return {"ok": False, "error": "webcam capture failed"}
        path = DATA / "uploads" / "vision_webcam.jpg"
        cv2.imwrite(str(path), frame)
        ans = generate_with_image(question, path.read_bytes(), mime="image/jpeg")
        return {"ok": True, "answer": ans, "path": str(path)}
