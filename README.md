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
        T+dur+5m    post-meeting close-out
   → 08:30 daily    day-ahead reading
   → each fire: pick a tone register from learned weights
        → LLM (OpenRouter, any cheap model) writes ≤45 words in that register
        → send with 👍 / 👎 buttons
        → tap adjusts the weights for the next message
```

No OAuth, no consent screens, no client secrets. The ICS secret address works for Google, Apple and Outlook calendars.

## Files

| File | Job |
|---|---|
| `bot.py` | Telegram handlers, scheduler, state |
| `feed.py` | fetch + parse ICS, expand recurring events |
| `voice.py` | LLM persona, tone registers, template fallback |
| `demo/seed.py` | writes a demo calendar with events minutes apart |
| `state.json` | chat_id, ics_url, sent keys, tone weights (auto-created) |

## Run it

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # add TELEGRAM_BOT_TOKEN (from @BotFather) and OPENROUTER_API_KEY
python bot.py
```

In Telegram: `/start`, then `/connect <your secret ICS url>`.
Google Calendar → Settings → your calendar → *Secret address in iCal format*.

Commands: `/start` · `/connect <url>` · `/today` · `/status` · `/disconnect`

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

## Design notes

- **Setup vs daily input.** Judges penalise daily input. One `/connect` is the only setup; after that the bot only ever pushes.
- **Tone learning is weights, not bans.** 👎 lowers a register's weight by 0.4, 👍 raises it 0.5. A disliked register still appears occasionally so the bot can recover if your taste changes.
- **Dedupe survives restarts.** Sent keys are persisted, so a crash mid-day never double-sends.
- **Template fallback.** If the LLM key is missing or the API errors, messages still go out from built-in text. The demo can't die on a network blip.

## Gotchas

- `pip install "python-telegram-bot[job-queue]"` — the plain install has no scheduler.
- ICS secret URLs lag Google by a few minutes. Fine for a nudge.
- All-day events have a `date`, not a `datetime`; they're skipped.
