"""Write a dummy calendar for the demo.

  python demo/seed.py            # compressed: events 2 min apart starting in 2 min
  python demo/seed.py 3          # same, 3 min apart
  python demo/seed.py --fast     # for recording: 1-minute meetings, 3 min apart, so
                                 # pre AND post nudges all land inside ~8 minutes
  python demo/seed.py --day      # realistic full day (09:00–18:30 today) → demo/sample-day.ics
                                 # import that into Google Calendar so the phone shows a real-looking day

A founder's Friday in Bangalore. Titles are chosen so the nudges have something
to react to: a hard investor call, a people conversation, a stage moment.
"""
import sys
import uuid
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Asia/Kolkata")

# (title, start "HH:MM", duration minutes, description)
DAY = [
    ("Team standup", "09:00", 15, "Daily sync with the platform team"),
    ("Investor call: Series A", "10:00", 45, "Runway conversation with Peak XV. Bring the burn chart."),
    ("1:1 with Priya", "11:30", 30, "Career growth — she asked about the tech lead path"),
    ("Lunch with Arjun (Razorpay)", "13:00", 45, "Partnership sounding-out, Koramangala"),
    ("Product review: onboarding flow", "15:00", 60, "Drop-off at step 3 is 40%. Decide: cut or fix."),
    ("Hackathon demo", "16:30", 20, "Ninety seconds on stage. Phone screen only."),
    ("Call with Amma", "18:00", 30, "Sunday plans"),
]

# compressed mode uses this subset, in this order
LIVE = [DAY[0], DAY[1], DAY[2], DAY[5]]


def fmt(dt):
    return dt.strftime("%Y%m%dT%H%M%S")


def header(now):
    return [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//computer-josiyam//demo//EN",
        "X-WR-CALNAME:Sriram (demo)",
        "X-WR-TIMEZONE:Asia/Kolkata",
        "BEGIN:VTIMEZONE",
        "TZID:Asia/Kolkata",
        "BEGIN:STANDARD",
        "DTSTART:19700101T000000",
        "TZOFFSETFROM:+0530",
        "TZOFFSETTO:+0530",
        "END:STANDARD",
        "END:VTIMEZONE",
    ]


def vevent(now, title, start, dur, desc, rrule=None):
    end = start + timedelta(minutes=dur)
    lines = [
        "BEGIN:VEVENT",
        f"UID:{uuid.uuid4()}@computer-josiyam",
        f"DTSTAMP:{fmt(now)}Z",
        f"DTSTART;TZID=Asia/Kolkata:{fmt(start)}",
        f"DTEND;TZID=Asia/Kolkata:{fmt(end)}",
        f"SUMMARY:{title}",
        f"DESCRIPTION:{desc}",
    ]
    if rrule:
        lines.append(f"RRULE:{rrule}")
    lines.append("END:VEVENT")
    return lines


def weekly_planning(now):
    # next Monday 10:00, repeating weekly — proves RRULE expansion
    days_ahead = (7 - now.weekday()) % 7 or 7
    start = (now + timedelta(days=days_ahead)).replace(hour=10, minute=0, second=0, microsecond=0)
    return vevent(now, "Weekly planning", start, 30, "Roadmap + hiring", rrule="FREQ=WEEKLY;BYDAY=MO")


def write(path, lines):
    with open(path, "w") as f:
        f.write("\r\n".join(lines + ["END:VCALENDAR"]) + "\r\n")


def main():
    now = datetime.now(TZ).replace(second=0, microsecond=0)
    out = "demo/demo.ics"
    if "--out" in sys.argv:
        out = sys.argv[sys.argv.index("--out") + 1]
    if "--day" in sys.argv:
        lines = header(now)
        for title, hhmm, dur, desc in DAY:
            h, m = map(int, hhmm.split(":"))
            lines += vevent(now, title, now.replace(hour=h, minute=m), dur, desc)
        lines += weekly_planning(now)
        write("demo/sample-day.ics", lines)
        print(f"wrote demo/sample-day.ics — {len(DAY)} events today + weekly planning")
        return

    fast = "--fast" in sys.argv
    args = [a for i, a in enumerate(sys.argv[1:], 1) if sys.argv[i - 1] != "--out"]
    gap = 3 if fast else int(next((a for a in args if a.isdigit()), 2))
    lines = header(now)
    t = now + timedelta(minutes=2)
    for title, _, dur, desc in LIVE:
        lines += vevent(now, title, t, 1 if fast else dur, desc)
        t += timedelta(minutes=gap)
    lines += weekly_planning(now)
    write(out, lines)
    print(f"wrote {out} — first event at {(now + timedelta(minutes=2)):%H:%M}, {gap} min apart"
          + (" (fast: 1-min meetings)" if fast else ""))


if __name__ == "__main__":
    main()
