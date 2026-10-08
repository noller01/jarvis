"""Remote dashboard — local HTTP + WebSocket, QR pairing."""

from __future__ import annotations

import asyncio
import json
import logging
import socket
import threading
from collections.abc import Callable
from pathlib import Path

from jarvis.config import DATA

log = logging.getLogger("jarvis.remote")

HTML = """<!DOCTYPE html>
<html><head><meta name="viewport" content="width=device-width,initial-scale=1">
<title>JARVIS Remote</title>
<style>
body{margin:0;background:#0A0A0A;color:#E8E8E8;font-family:system-ui;padding:16px}
input,button{width:100%;padding:12px;margin:8px 0;background:#161616;border:1px solid #2A2A2A;color:#E8E8E8;border-radius:2px}
button{background:#2A2A2A} #log{white-space:pre-wrap;color:#9A9A9A;font-size:13px}
</style></head><body>
<h2 style="font-weight:300;letter-spacing:4px">JARVIS</h2>
<input id="m" placeholder="Message"><button onclick="send()">Send</button>
<div id="log"></div>
<script>
const ws=new WebSocket((location.protocol==='https:'?'wss':'ws')+'://'+location.host+'/ws');
ws.onmessage=e=>{log.textContent+=e.data+'\\n'};
function send(){ws.send(JSON.stringify({type:'text',text:m.value}));m.value='';}
</script></body></html>
"""


class RemoteDashboard:
    def __init__(self, on_text: Callable[[str], None] | None = None, port: int = 8765) -> None:
        self.on_text = on_text
        self.port = port
        self._thread: threading.Thread | None = None
        self.pair_token = "jarvis-" + socket.gethostname()
        self.qr_path = DATA / "uploads" / "remote_qr.png"

    def start(self) -> Path:
        self._thread = threading.Thread(target=self._run, daemon=True, name="jarvis-remote")
        self._thread.start()
        return self._make_qr()

    def _lan_ip(self) -> str:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    def _make_qr(self) -> Path:
        import qrcode

        url = f"http://{self._lan_ip()}:{self.port}/?token={self.pair_token}"
        img = qrcode.make(url)
        self.qr_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(self.qr_path)
        (DATA / "uploads" / "remote_url.txt").write_text(url, encoding="utf-8")
        return self.qr_path

    def _run(self) -> None:
        try:
            from aiohttp import web
        except ImportError:
            log.warning("aiohttp missing — remote dashboard disabled")
            return

        clients: set = set()

        async def index(request):  # noqa: ANN001
            return web.Response(text=HTML, content_type="text/html")

        async def ws_handler(request):  # noqa: ANN001
            ws = web.WebSocketResponse()
            await ws.prepare(request)
            clients.add(ws)
            try:
                async for msg in ws:
                    if msg.type.name == "TEXT":
                        try:
                            data = json.loads(msg.data)
                            if data.get("type") == "text" and self.on_text:
                                self.on_text(data.get("text", ""))
                        except Exception:
                            pass
            finally:
                clients.discard(ws)
            return ws

        async def main():
            app = web.Application()
            app.router.add_get("/", index)
            app.router.add_get("/ws", ws_handler)
            runner = web.AppRunner(app)
            await runner.setup()
            site = web.TCPSite(runner, "0.0.0.0", self.port)
            await site.start()
            log.info("Remote dashboard on port %s", self.port)
            while True:
                await asyncio.sleep(3600)

        asyncio.run(main())

    def broadcast(self, text: str) -> None:
        # best-effort; full fanout would need shared loop — skip for simplicity
        pass
