# Meeting Oracle

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
        → Claude (Haiku) writes ≤45 words in that register
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
cp .env.example .env      # add TELEGRAM_BOT_TOKEN (from @BotFather) and ANTHROPIC_API_KEY
python bot.py
```

In Telegram: `/start`, then `/connect <your secret ICS url>`.
Google Calendar → Settings → your calendar → *Secret address in iCal format*.

Commands: `/start` · `/connect <url>` · `/today` · `/status` · `/disconnect`

## Demo mode

Seed four events two minutes apart and shrink the lead times so the whole story plays out in ~10 minutes:

```bash
python demo/seed.py
# in .env:  PRE_LEAD_MINUTES=1  POST_LAG_MINUTES=0  POLL_SECONDS=15
python bot.py
```

Then `/connect demo/demo.ics` (a local path works too). Demo beats:

1. `/today` — day-ahead reading
2. Nudge lands 1 min before "Investor call: Series A"
3. Tap 👎 — the next message arrives in a different register
4. Post-meeting close-out

Four messages, ninety seconds, the user never typed a word after setup.

The demo calendar is seeded; say so on stage. "This is my calendar, I connected it this morning" is the honest and stronger line.

## Design notes

- **Setup vs daily input.** Judges penalise daily input. One `/connect` is the only setup; after that the bot only ever pushes.
- **Tone learning is weights, not bans.** 👎 lowers a register's weight by 0.4, 👍 raises it 0.5. A disliked register still appears occasionally so the bot can recover if your taste changes.
- **Dedupe survives restarts.** Sent keys are persisted, so a crash mid-day never double-sends.
- **Template fallback.** If the LLM key is missing or the API errors, messages still go out from built-in text. The demo can't die on a network blip.

## Gotchas

- `pip install "python-telegram-bot[job-queue]"` — the plain install has no scheduler.
- ICS secret URLs lag Google by a few minutes. Fine for a nudge.
- All-day events have a `date`, not a `datetime`; they're skipped.
