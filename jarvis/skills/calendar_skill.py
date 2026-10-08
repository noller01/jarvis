"""Google Calendar controls."""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any

from jarvis.config import DATA, settings
from jarvis.skills.base import Skill

SCOPES = ["https://www.googleapis.com/auth/calendar"]
TOKEN = DATA / "credentials" / "calendar_token.json"


class CalendarSkill(Skill):
    name = "google_calendar"
    TOOLS = [
        {
            "name": "calendar_list_events",
            "description": "List upcoming Google Calendar events",
            "parameters": {
                "type": "object",
                "properties": {"days": {"type": "integer"}},
            },
        },
        {
            "name": "calendar_create_event",
            "description": "Create a Google Calendar event",
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {"type": "string"},
                    "start_iso": {"type": "string"},
                    "end_iso": {"type": "string"},
                    "description": {"type": "string"},
                },
                "required": ["summary", "start_iso", "end_iso"],
            },
        },
        {
            "name": "calendar_delete_event",
            "description": "Delete a Google Calendar event by id",
            "parameters": {
                "type": "object",
                "properties": {"event_id": {"type": "string"}},
                "required": ["event_id"],
            },
        },
    ]

    def handler(self, args: dict) -> Any:
        try:
            service = self._service()
        except Exception as exc:
            return {
                "ok": False,
                "error": str(exc),
                "hint": "Place OAuth client JSON path in GOOGLE_CALENDAR_CREDENTIALS and authorize once.",
            }
        if "event_id" in args:
            service.events().delete(calendarId="primary", eventId=args["event_id"]).execute()
            return {"ok": True}
        if "summary" in args:
            body = {
                "summary": args["summary"],
                "description": args.get("description", ""),
                "start": {"dateTime": args["start_iso"]},
                "end": {"dateTime": args["end_iso"]},
            }
            ev = service.events().insert(calendarId="primary", body=body).execute()
            return {"ok": True, "event": {"id": ev.get("id"), "htmlLink": ev.get("htmlLink")}}
        days = int(args.get("days") or 7)
        now = dt.datetime.utcnow().isoformat() + "Z"
        end = (dt.datetime.utcnow() + dt.timedelta(days=days)).isoformat() + "Z"
        events = (
            service.events()
            .list(calendarId="primary", timeMin=now, timeMax=end, singleEvents=True, orderBy="startTime")
            .execute()
            .get("items", [])
        )
        out = [
            {
                "id": e.get("id"),
                "summary": e.get("summary"),
                "start": e.get("start"),
                "end": e.get("end"),
            }
            for e in events
        ]
        return {"ok": True, "events": out, "display": out}

    def _service(self):
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
        import os

        creds = None
        TOKEN.parent.mkdir(parents=True, exist_ok=True)
        if TOKEN.exists():
            creds = Credentials.from_authorized_user_file(str(TOKEN), SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                client = os.getenv("GOOGLE_CALENDAR_CREDENTIALS") or ""
                if not client or not Path(client).exists():
                    raise RuntimeError("GOOGLE_CALENDAR_CREDENTIALS not configured")
                flow = InstalledAppFlow.from_client_secrets_file(client, SCOPES)
                creds = flow.run_local_server(port=0)
            TOKEN.write_text(creds.to_json(), encoding="utf-8")
        return build("calendar", "v3", credentials=creds)
