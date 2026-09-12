# Computer Josiyam

*Josiyam* (ஜோசியம்) is Tamil for astrology.

A Telegram bot that reads your calendar once and then, without you ever typing again, sends a short word of encouragement before each meeting and a close-out after.

Connect a source once. Never ask again.

## How it works

```
ICS URL (polled every 60s)
   → expand next 24h of events (RRULE-aware, all-day events skipped)
   → for each event, schedule two jobs, deduped by uid:kind:start
        T-15m       pre-meeting nudge
        T+dur+5m    post-meeting close-out + journal prompt (😮‍💨 / 😐 / 🔥, or type)
   → 08:30 daily    day-ahead reading
   → 21:00 daily    end-of-day summary: each meeting with its mood, your notes, one reflection
   → each fire: pick a tone register from learned weights
        → LLM (OpenRouter, any cheap model) writes ≤25 words (day reading ≤60) in that voice,
          given the event's emotional class, the day's density, recent moods
        → pre/day messages carry 👍 / 👎; post-meeting carries 😮‍💨 / 😐 / 🔥
        → every tap is a row in SQLite; weights are derived, never stored
```

No OAuth, no consent screens, no client secrets. The ICS secret address works for Google, Apple and Outlook calendars.

## Files

| File | Job |
|---|---|
| `bot.py` | onboarding, handlers, scheduler (multi-user, per-timezone) |
| `store.py` | SQLite: users, messages, feedback, mood, sent keys |
| `feed.py` | fetch + parse ICS, expand recurring events, classify each as hard / neutral / nourishing |
| `voice.py` | LLM persona, tone registers, passive-signal prompt context, template fallback |
| `demo/seed.py` | writes a demo calendar with events minutes apart |
| `josiyam.db` | the SQLite file (auto-created) |

## Run it

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # add TELEGRAM_BOT_TOKEN (from @BotFather) and OPENROUTER_API_KEY
python bot.py
```

In Telegram send `/start`. Three taps: your name, timezone, sun sign, then paste your calendar's secret ICS link. The first reading arrives immediately.

Commands: `/start` · `/today` · `/summary` · `/journal` · `/stats` · `/status` · `/demo` · `/reset` · `/help`

Anything else you type is a journal entry (see below).

## Demo mode

Two dummy calendars, both a founder's Friday in Bangalore:

```bash
python demo/seed.py          # compressed: 4 events, 2 min apart, starting in 2 min  → demo/demo.ics
python demo/seed.py --day    # realistic: 7 events 09:00–18:30 today                 → demo/sample-day.ics
```

**Live demo** — shrink the lead times in `.env` (`PRE_LEAD_MINUTES=1`, `POST_LAG_MINUTES=0`, `POLL_SECONDS=15`), run `python demo/seed.py`, start the bot, then `/connect demo/demo.ics`. Re-seed right before you hit record; events are relative to now.

**For the phone screen** — import `demo/sample-day.ics` into Google Calendar (Settings → Import & export → Import). Your calendar app then shows a real-looking day, and you can `/connect` Google's actual secret ICS URL instead of a local file. Same bot, same code; the only difference is where the file lives.

Demo beats:

1. `/today` — day-ahead reading
2. Nudge lands 1 min before "Investor call: Series A"
3. Tap 👎 — the next message arrives in a different register
4. Post-meeting close-out

Four messages, ninety seconds, the user never typed a word after setup.

The calendar is seeded; say so on stage. "This is my calendar, I connected it this morning" is the honest and stronger line.

## Mood without asking

Judges penalise daily input, so the bot never asks "how are you?". It reads mood from what it already has:

| Signal | Source | Costs the user |
|---|---|---|
| Event class (hard / neutral / nourishing) | keywords in title + description | nothing |
| Day density | count of meetings today; ≥5 flips to short messages | nothing |
| Reaction latency | seconds from send to 👍/👎 | nothing |
| Post-meeting mood | 😮‍💨 / 😐 / 🔥 on the close-out message | one tap, only on a message already sent |

Recent moods feed the next morning's reading ("yesterday's investor call was rough…").

`/stats` shows what has been learned: thumbs-up rate per voice, average reaction time, mood counts, current weights.

## Journal

After setup, any free text you send is kept as a journal entry. No command needed. The bot:

- links it to the meeting it last spoke to you about (within 90 min), so "that was brutal" lands on the right event
- replies in one line, in the current voice — reflection, never advice or questions
- feeds your last three notes into the next nudges, so what you wrote colours what it says back

`/journal` reads back the last 7 days grouped by day, each entry tagged with its meeting.

**End of day** (21:00 local, `EOD_AT`): one message listing every meeting with the mood you tapped, your last notes, and a short reflection. `/summary` sends it on demand.

## Design notes

- **Setup vs daily input.** Judges penalise daily input. One `/connect` is the only setup; after that the bot only ever pushes.
- **Tone learning is weights, not bans.** Four voices — josiyam (astrology, uses your sun sign), hype, warm, quote (a real attributed line) — shuffle with equal weight to start. Weights are recomputed from the last 30 taps, newest counting most (👍 +0.5, 👎 −0.4, decay 0.92 per step). A disliked register still appears occasionally so the bot can recover if your taste changes.
- **Dedupe survives restarts.** Sent keys live in SQLite, so a crash mid-day never double-sends.
- **Onboarding is three taps.** Name, timezone, sun sign, calendar link. Pasting a bare URL works — no one types `/connect`. The first reading arrives the second the calendar connects.
- **Template fallback.** If the LLM key is missing or the API errors, messages still go out from built-in text. The demo can't die on a network blip.

## Gotchas

- `pip install "python-telegram-bot[job-queue]"` — the plain install has no scheduler.
- ICS secret URLs lag Google by a few minutes. Fine for a nudge.
- All-day events have a `date`, not a `datetime`; they're skipped.
