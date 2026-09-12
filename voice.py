"""Turn an event + a voice register into a short positive-reinforcement message.

Four registers, shuffled by learned weights (every tap moves them):
  josiyam — playful astrology, uses the user's sun sign
  hype    — short, direct, energising
  warm    — gentle, like a kind friend
  quote   — a real, attributed quote that fits the moment, plus at most one line

Uses OpenRouter if OPENROUTER_API_KEY is set (any cheap model), else Claude if
ANTHROPIC_API_KEY is set, else built-in templates so the demo never dies on a
missing key or a network blip.
"""
from __future__ import annotations

import os
import random

REGISTERS = ("josiyam", "hype", "warm", "quote")

STYLE = {
    "josiyam": "playful Tamil-astrology voice: rasi, nakshatram, planets, houses — always landing on a concrete confidence boost. Mention their sun sign if known.",
    "hype": "short, direct, energising. Verbs. No softening.",
    "warm": "gentle, encouraging, like a kind friend who believes in them",
    "quote": "one real, correctly attributed quote from a real person (author, athlete, scientist, film) that fits this moment, in quotation marks with the name, then at most one short line tying it to them. No invented quotes.",
}

KIND_BRIEF = {
    "pre": "The meeting starts in {lead} minutes. One thing to walk in with.",
    "post": "The meeting just ended. Close it out: acknowledge, release, one small next step.",
    "day": "It's morning. A short reading for the day ahead across all these events.",
    "ack": "They just wrote a journal note (below). Reply in one short line: reflect it back, no advice, no questions.",
}

WORD_CAP = {"pre": 25, "post": 25, "day": 60, "ack": 15}

QUOTES = [
    '"Courage is grace under pressure." — Hemingway',
    '"You miss 100% of the shots you don\'t take." — Wayne Gretzky',
    '"It always seems impossible until it\'s done." — Nelson Mandela',
    '"Do the thing and you will have the power." — Emerson',
    '"Whether you think you can or you can\'t, you\'re right." — Henry Ford',
    '"Start where you are. Use what you have. Do what you can." — Arthur Ashe',
]

FALLBACK = {
    "pre": {
        "warm": "{title} in {lead} min. You've prepared more than you think. Breathe once, then go.",
        "hype": "{title} in {lead}. You know this room. Go.",
        "josiyam": "Mercury is direct and so are you, {sign}. {title} in {lead} — the chart is on your side.",
        "quote": "{quote}\n{title} in {lead}.",
    },
    "post": {
        "warm": "{title} done. Whatever happened, you showed up fully. Water, then the next thing.",
        "hype": "{title}: done. One line of notes. Move.",
        "josiyam": "{title} has left your fourth house. Release it, {sign}. The next transit is yours.",
        "quote": "{quote}\nThat one's behind you.",
    },
    "ack": {
        "warm": "Noted. Thank you for telling me.",
        "hype": "Logged. Onward.",
        "josiyam": "Written into the chart, {sign}.",
        "quote": "\"The unexamined life is not worth living.\" — Socrates. Noted.",
    },
    "day": {
        "warm": "{n} meetings today. Each is a room you already know. Start with {first}.",
        "hype": "{n} meetings. One at a time. First: {first}.",
        "josiyam": "{n} conjunctions today for a {sign}, opening with {first}. Saturn asks for structure, Venus for warmth. You have both.",
        "quote": "{quote}\n{n} meetings today, starting with {first}.",
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
            max_tokens=300,
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
            max_tokens=300,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return msg.content[0].text.strip()
    return None


def compose(kind: str, register: str, events: list[dict], lead_minutes: int = 15,
            name: str | None = None, context: dict | None = None) -> str:
    """kind: pre|post|day. events: one event for pre/post, all of today's for day.

    context (all optional): event_class, density (meetings today), moods (recent taps),
    sunsign. These are passive signals — nothing the user typed today.
    """
    register = register if register in REGISTERS else "warm"
    context = context or {}
    ev = events[0] if events else {"title": "your meeting"}
    slots = {
        "title": ev.get("title", "your meeting"),
        "lead": lead_minutes,
        "n": len(events),
        "first": ev.get("title", ""),
        "sign": context.get("sunsign") or "friend",
        "quote": random.choice(QUOTES),
    }
    agenda = "\n".join(
        f'- {e["title"]} at {e["start"]:%H:%M} [{e.get("klass", "neutral")}] {e.get("description", "")}'.rstrip()
        for e in events
    )
    who = f"The user's name is {name}. Use it at most once, or not at all." if name else "Address the user as 'you'."
    signals = []
    if context.get("sunsign"):
        signals.append(f"Their sun sign is {context['sunsign']}.")
    if context.get("event_class") == "hard":
        signals.append("This meeting is emotionally loaded. Steady them; do not minimise it.")
    elif context.get("event_class") == "nourishing":
        signals.append("This is a nourishing, human meeting. Be light and glad for them.")
    if (context.get("density") or 0) >= 5:
        signals.append(f"They have {context['density']} meetings today — keep it especially short.")
    if context.get("moods"):
        signals.append("Recent post-meeting moods (newest first): " + ", ".join(context["moods"]) + ". Acknowledge lightly only if relevant.")
    if context.get("journal"):
        notes = " | ".join(f'"{j}"' for j in context["journal"])
        signals.append(f"Their own recent journal notes (newest first): {notes}. Let these colour the message; quote them only if it lands naturally.")
    if context.get("note"):
        signals.append(f'The note they just wrote: "{context["note"]}"' + (f' (about: {context["note_about"]})' if context.get("note_about") else ""))
    system = (
        "You are Computer Josiyam, a Telegram bot that sends positive reinforcement around calendar events. "
        f"Voice: {STYLE[register]} "
        f"Hard rules: under {WORD_CAP[kind]} words. One or two sentences. Never give meeting advice or agendas. "
        f"Never mention being an AI. {who} At most one emoji. Plain text, no markdown, no preamble."
    )
    user = KIND_BRIEF[kind].format(lead=lead_minutes) + ("\n\nEvents:\n" + agenda if events else "")
    if signals:
        user += "\n\nContext:\n" + "\n".join(f"- {x}" for x in signals)
    try:
        text = _complete(system, user)
    except Exception:
        text = None
    return text or FALLBACK[kind][register].format(**slots)


def pick_register(weights: dict[str, float], avoid: str | None = None) -> str:
    """Weighted random choice, so a 👎 lowers a register instead of banning it.
    `avoid` is the register used last time, so two in a row is rare — it shuffles."""
    regs = list(REGISTERS)
    w = [max(weights.get(r, 1.0), 0.05) * (0.25 if r == avoid else 1.0) for r in regs]
    return random.choices(regs, weights=w, k=1)[0]
