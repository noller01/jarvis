# JARVIS

All-in-one AI personal assistant desktop app — Python 3.12, Gemini Live + OpenRouter.

Black / grey minimal HUD with a software-rendered holographic avatar, real-time voice, system control, memory, and a plugin skill system.

## Setup

```bash
cd Projects/jarvis
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
copy .env.example .env          # then edit keys
python main.py
```

### Keys

| Variable | Required | Purpose |
|----------|----------|---------|
| `GEMINI_API_KEY` | Yes | Live voice + tool calling + grounded search |
| `OPENROUTER_API_KEY` | No | Free-tier LLM for web/memory/desktop/file modules |
| `GOOGLE_CALENDAR_CREDENTIALS` | No | Path to Google OAuth client JSON |

## Controls

- **Ctrl+Space** — push-to-talk (global on Windows)
- **Hey Jarvis** — local wake word; auto-sleep after 2 min silence
- Type in the input bar for hybrid keyboard mode
- Drop files onto the HUD to analyze PDFs / code / images
- Copy text → clipboard panel (Translate / Summarise / Explain / Fix)

## Architecture

- `jarvis/core` — Gemini Live, OpenRouter, model ladder, context compression
- `jarvis/avatar` — CPU holographic face, formant lip-sync, Unicode mouth reduction
- `jarvis/skills` — self-describing `TOOL` + `handler`, auto-discovered
- `plugins/` — drop a single `.py` to add a skill on next launch
- `jarvis/memory` — SQLite + FTS, unlimited store, prompt slice + on-demand search

## Design

Palette: `#0A0A0A` base, `#161616` panels, `#2A2A2A` borders, `#E8E8E8` text, hue-tinted grey accent. Live hue wheel retints the HUD and avatar.
