"""Turn an event + a tone register into a short positive-reinforcement message.

Uses OpenRouter if OPENROUTER_API_KEY is set (any cheap model), else Claude if
ANTHROPIC_API_KEY is set, else built-in templates so the demo never dies on a
missing key or a network blip.
"""
from __future__ import annotations

import os
import random

REGISTERS = ("warm", "punchy", "cosmic")

STYLE = {
    "warm": "gentle, encouraging, like a kind friend who believes in them",
    "punchy": "short, direct, energising, one or two sentences max",
    "cosmic": "playful astrology voice — planets, houses, retrogrades — but always landing on a concrete confidence boost",
}

KIND_BRIEF = {
    "pre": "The meeting starts in {lead} minutes. Give them one thing to walk in with.",
    "post": "The meeting just ended. Close it out: acknowledge, release, one small next step.",
    "day": "It's morning. Give a one-paragraph reading for the day ahead across all these events.",
}

FALLBACK = {
    "pre": {
        "warm": "{title} in {lead} minutes. You've prepared more than you think. Walk in slow, breathe once, and let them come to you.",
        "punchy": "{title} in {lead}. You know this room. Go.",
        "cosmic": "Mercury is direct and so are you. {title} in {lead} minutes — the stars filed the agenda in your favour.",
    },
    "post": {
        "warm": "{title} is done. Whatever happened in there, you showed up fully. Take a sip of water before the next thing.",
        "punchy": "{title}: done. Write one line of notes, then move.",
        "cosmic": "{title} has left your fourth house. Release it. The next transit is yours to shape.",
    },
    "day": {
        "warm": "Today holds {n} meetings. Each is a room you already know how to be in. Start with the first one and let the day unfold.",
        "punchy": "{n} meetings today. One at a time. First: {first}.",
        "cosmic": "The chart for today shows {n} conjunctions, opening with {first}. Saturn asks for structure, Venus for warmth. You have both.",
    },
}


def _complete(system: str, user: str) -> str | None:
    """Try OpenRouter (OpenAI-compatible), then Anthropic. None if neither is configured."""
    if os.getenv("OPENROUTER_API_KEY"):
        from openai import OpenAI

        client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=os.environ["OPENROUTER_API_KEY"])
        primary = os.getenv("JOSIYAM_MODEL", "deepseek/deepseek-v4-flash")
        fallbacks = [m for m in os.getenv("JOSIYAM_FALLBACK_MODELS", "deepseek/deepseek-v3.2,google/gemma-4-31b-it:free").split(",") if m]
        r = client.chat.completions.create(
            model=primary,
            max_tokens=400,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            extra_headers={"HTTP-Referer": "https://github.com/sriramarun/computer-josiyam", "X-Title": "Computer Josiyam"},
            extra_body={
                "models": [primary] + fallbacks,  # OpenRouter tries these in order on error / rate limit
                "reasoning": {"enabled": False},  # thinking models otherwise spend the budget on reasoning
            },
        )
        content = r.choices[0].message.content
        return content.strip() if content else None
    if os.getenv("ANTHROPIC_API_KEY"):
        import anthropic

        msg = anthropic.Anthropic().messages.create(
            model=os.getenv("JOSIYAM_MODEL", "claude-haiku-4-5-20251001"),
            max_tokens=200,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return msg.content[0].text.strip()
    return None


def compose(kind: str, register: str, events: list[dict], lead_minutes: int = 15) -> str:
    """kind: pre|post|day. events: one event for pre/post, all of today's for day."""
    register = register if register in REGISTERS else "warm"
    ev = events[0] if events else {"title": "your meeting"}
    slots = {
        "title": ev.get("title", "your meeting"),
        "lead": lead_minutes,
        "n": len(events),
        "first": ev.get("title", ""),
    }
    agenda = "\n".join(f'- {e["title"]} at {e["start"]:%H:%M} ({e.get("description","")})' for e in events)
    system = (
        "You are Computer Josiyam, a Telegram bot that sends positive reinforcement around calendar events. "
        f"Tone register: {STYLE[register]}. "
        "Rules: under 45 words. Never give meeting advice or agendas. Never mention being an AI. "
        "Address the user as 'you'. At most one emoji. Plain text, no markdown."
    )
    user = KIND_BRIEF[kind].format(lead=lead_minutes) + "\n\nEvents:\n" + agenda
    try:
        text = _complete(system, user)
    except Exception:
        text = None
    return text or FALLBACK[kind][register].format(**slots)


def pick_register(weights: dict[str, float]) -> str:
    """Weighted random choice, so a 👎 lowers a register instead of banning it."""
    regs = list(REGISTERS)
    w = [max(weights.get(r, 1.0), 0.05) for r in regs]
    return random.choices(regs, weights=w, k=1)[0]
