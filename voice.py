"""Turn an event + a tone register into a short positive-reinforcement message.

Uses Claude if ANTHROPIC_API_KEY is set; otherwise falls back to templates so
the demo never dies on a missing key.
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


def _client():
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        return None
    try:
        import anthropic

        return anthropic.Anthropic()
    except Exception:
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
    client = _client()
    if client is None:
        return FALLBACK[kind][register].format(**slots)

    agenda = "\n".join(f'- {e["title"]} at {e["start"]:%H:%M} ({e.get("description","")})' for e in events)
    system = (
        "You are Meeting Oracle, a Telegram bot that sends positive reinforcement around calendar events. "
        f"Tone register: {STYLE[register]}. "
        "Rules: under 45 words. Never give meeting advice or agendas. Never mention being an AI. "
        "Address the user as 'you'. At most one emoji. Plain text, no markdown."
    )
    user = KIND_BRIEF[kind].format(lead=lead_minutes) + "\n\nEvents:\n" + agenda
    try:
        msg = client.messages.create(
            model=os.getenv("ORACLE_MODEL", "claude-haiku-4-5-20251001"),
            max_tokens=200,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return msg.content[0].text.strip()
    except Exception:
        return FALLBACK[kind][register].format(**slots)


def pick_register(weights: dict[str, float]) -> str:
    """Weighted random choice, so a 👎 lowers a register instead of banning it."""
    regs = list(REGISTERS)
    w = [max(weights.get(r, 1.0), 0.05) for r in regs]
    return random.choices(regs, weights=w, k=1)[0]
