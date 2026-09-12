"""Pull an ICS calendar (URL or local file) and expand the next N hours of events.

Handles recurring events (RRULE) via recurring-ical-events so weekly standups
work. All-day events are skipped: they have a `date`, not a `datetime`, and
there is no meaningful "15 minutes before" for them.
"""
from __future__ import annotations

import os
import sys
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import recurring_ical_events
import requests
from icalendar import Calendar

TZ = ZoneInfo(os.getenv("TZ_NAME", "Asia/Kolkata"))


def _fetch(source: str) -> bytes:
    if source.startswith(("http://", "https://", "webcal://")):
        url = source.replace("webcal://", "https://", 1)
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        return r.content
    with open(source, "rb") as f:
        return f.read()


def _as_local(dt: datetime | date, tz: ZoneInfo) -> datetime | None:
    if not isinstance(dt, datetime):
        return None  # all-day event
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=tz)  # floating time: assume the user's zone
    return dt.astimezone(tz)


HARD = ("investor", "board", "review", "interview", "pitch", "deadline", "escalation", "negotiation", "performance", "appraisal", "demo", "exam")
NOURISHING = ("1:1", "lunch", "coffee", "walk", "amma", "appa", "mom", "dad", "family", "friend", "birthday", "yoga", "gym", "dinner")


def classify(title: str, description: str = "") -> str:
    """Cheap, deterministic: how emotionally loaded is this meeting? Feeds the prompt."""
    t = f"{title} {description}".lower()
    if any(k in t for k in HARD):
        return "hard"
    if any(k in t for k in NOURISHING):
        return "nourishing"
    return "neutral"


def upcoming(source: str, hours: int = 24, now: datetime | None = None, tz: ZoneInfo | None = None) -> list[dict]:
    """Return events starting in [now, now+hours), sorted by start."""
    tz = tz or TZ
    cal = Calendar.from_ical(_fetch(source))
    now = now or datetime.now(tz)
    window_end = now + timedelta(hours=hours)
    out = []
    for e in recurring_ical_events.of(cal).between(now, window_end):
        start = _as_local(e["DTSTART"].dt, tz)
        if start is None:
            continue
        if "DTEND" in e:
            end = _as_local(e["DTEND"].dt, tz)
        elif "DURATION" in e:
            end = start + e["DURATION"].dt
        else:
            end = start + timedelta(hours=1)
        out.append(
            {
                "uid": str(e.get("UID", "")),
                "title": str(e.get("SUMMARY", "Untitled")),
                "start": start,
                "end": end,
                "description": str(e.get("DESCRIPTION", "")),
                "klass": classify(str(e.get("SUMMARY", "")), str(e.get("DESCRIPTION", ""))),
            }
        )
    out.sort(key=lambda ev: ev["start"])
    return out


if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else "demo/demo.ics"
    for ev in upcoming(src):
        print(f'{ev["start"]:%a %H:%M} - {ev["end"]:%H:%M}  {ev["title"]:35s} [{ev["klass"]}]')
