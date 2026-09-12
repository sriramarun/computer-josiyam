"""Write demo/demo.ics with four events starting a couple of minutes from now.

Usage:  python demo/seed.py [gap_minutes]
Default gap is 2 minutes so the whole demo plays out in ~10 minutes with
PRE_LEAD_MINUTES=1 and POST_LAG_MINUTES=0 in .env.
"""
import sys
import uuid
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Asia/Kolkata")
gap = int(sys.argv[1]) if len(sys.argv) > 1 else 2

events = [
    ("Team standup", 15, "Daily sync with the platform team"),
    ("Investor call: Series A", 30, "Hard conversation about runway"),
    ("1:1 with Priya", 20, "Career growth chat"),
    ("Hackathon demo", 10, "Ninety seconds on stage"),
]

now = datetime.now(TZ).replace(second=0, microsecond=0)
t = now + timedelta(minutes=2)


def fmt(dt):
    return dt.strftime("%Y%m%dT%H%M%S")


lines = [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    "PRODID:-//computer-josiyam//demo//EN",
    "BEGIN:VTIMEZONE",
    "TZID:Asia/Kolkata",
    "BEGIN:STANDARD",
    "DTSTART:19700101T000000",
    "TZOFFSETFROM:+0530",
    "TZOFFSETTO:+0530",
    "END:STANDARD",
    "END:VTIMEZONE",
]
for title, dur, desc in events:
    end = t + timedelta(minutes=dur)
    lines += [
        "BEGIN:VEVENT",
        f"UID:{uuid.uuid4()}@computer-josiyam",
        f"DTSTAMP:{fmt(now)}Z",
        f"DTSTART;TZID=Asia/Kolkata:{fmt(t)}",
        f"DTEND;TZID=Asia/Kolkata:{fmt(end)}",
        f"SUMMARY:{title}",
        f"DESCRIPTION:{desc}",
        "END:VEVENT",
    ]
    t = t + timedelta(minutes=gap)

# one recurring weekly event to prove RRULE expansion works
lines += [
    "BEGIN:VEVENT",
    f"UID:{uuid.uuid4()}@computer-josiyam",
    f"DTSTAMP:{fmt(now)}Z",
    f"DTSTART;TZID=Asia/Kolkata:{fmt(now + timedelta(hours=20))}",
    f"DTEND;TZID=Asia/Kolkata:{fmt(now + timedelta(hours=20, minutes=30))}",
    "RRULE:FREQ=WEEKLY",
    "SUMMARY:Weekly planning",
    "END:VEVENT",
    "END:VCALENDAR",
]
with open("demo/demo.ics", "w") as f:
    f.write("\r\n".join(lines) + "\r\n")
print(f"wrote demo/demo.ics — first event at {(now + timedelta(minutes=2)):%H:%M}")
