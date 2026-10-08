"""Morning briefing — first boot: greet, time, yesterday recap, news."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from jarvis.config import settings
from jarvis.memory.store import memory


def build_morning_briefing() -> dict[str, Any]:
    now = datetime.now()
    name = settings.get("user_name") or "there"
    assistant = settings.get("assistant_name", "JARVIS")
    greeting = _greeting(now.hour, name)
    yesterday = memory.consume_morning_summary()
    news = _fetch_news()
    weather = None
    try:
        from jarvis.skills.weather import WeatherSkill

        weather = WeatherSkill().handler({})
    except Exception:
        pass
    text_parts = [
        f"{greeting} It's {now.strftime('%A, %H:%M')}.",
    ]
    if yesterday:
        text_parts.append(f"Yesterday we covered: {yesterday}")
    if weather and weather.get("ok"):
        r = weather["report"]
        text_parts.append(
            f"Weather in {r.get('city')}: {r.get('temperature_c')}°C, humidity {r.get('humidity')}%."
        )
    if news:
        text_parts.append("Headlines: " + "; ".join(news[:3]))
    spoken = " ".join(text_parts)
    return {
        "spoken": spoken,
        "news": news,
        "weather": weather,
        "yesterday": yesterday,
        "assistant": assistant,
    }


def _greeting(hour: int, name: str) -> str:
    if hour < 12:
        return f"Good morning, {name}."
    if hour < 18:
        return f"Good afternoon, {name}."
    return f"Good evening, {name}."


def _fetch_news() -> list[str]:
    try:
        import feedparser

        feed = feedparser.parse("https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en")
        return [e.title for e in feed.entries[:6]]
    except Exception:
        try:
            from duckduckgo_search import DDGS

            with DDGS() as ddgs:
                return [r.get("title") or "" for r in ddgs.news("world", max_results=5)]
        except Exception:
            return []
