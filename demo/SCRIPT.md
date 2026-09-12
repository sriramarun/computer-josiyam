# Demo recording — shot list

Target: 90–120 seconds, phone screen only, portrait. One take of ~9 minutes real time, then cut the waits.

## Before you press record (5 min)

1. `.env`: `PRE_LEAD_MINUTES=1`, `POST_LAG_MINUTES=0`, `POLL_SECONDS=15`. Restart the bot.
2. Telegram on the phone: open the bot chat → ⋮ → **Clear history**. Clean slate.
3. Send `/reset` so onboarding runs from the top.
4. Phone: Do Not Disturb **off** (you want the notification banner to appear), brightness up, battery > 50%, close other apps.
5. Optional: put the sample day into Google Calendar (`demo/sample-day.ics` → Settings → Import) and take one screenshot of it. Cut it in as a 3-second opener: "this is my day".

## Recording (one continuous take, ~9 min real time)

| Real time | You do | What lands |
|---|---|---|
| 0:00 | Start screen record. Send `/start` | greeting, asks name |
| 0:10 | Type your name | timezone buttons |
| 0:15 | Tap IST | sun-sign grid |
| 0:20 | Tap your sign | calendar instructions |
| 0:30 | Send `/demo fast` | "Connected. I can see 4 events" + **day reading** within 3 s |
| 1:00 | wait | ⏰ pre-nudge: Team standup |
| 1:30 | tap 👍 | footer appears |
| 3:00 | wait | ✅ post: Team standup + mood buttons |
| 3:10 | tap 😐, then **type one line** ("quick one, nothing new") | 📓 saved · Team standup + one-line reply |
| 4:00 | wait | ⏰ pre-nudge: Investor call (a *hard* meeting — voice steadies) |
| 4:10 | tap 👎 | "the next one will sound different" |
| 6:00 | wait | ✅ post: Investor call |
| 6:10 | tap 🔥, type "they pushed on burn, I held the line" | 📓 saved · Investor call |
| 7:00 | wait | ⏰ pre-nudge: 1:1 with Priya — watch it echo "held the line" |
| 7:30 | send `/summary` | 🌙 day closed: meetings with moods, your notes, reflection |
| 8:00 | send `/stats` | thumbs-up rate, per-voice, reaction time, moods, journal count |
| 8:15 | stop recording | |

## Edit (15 min)

- iPhone: Photos → edit → trim, or iMovie. Android: CapCut / Google Photos.
- Cut every wait. Keep ~2 s of stillness before each incoming message so the notification is readable.
- Text captions, one per beat, plain: "Connected once" · "Pre-meeting" · "One tap" · "Post-meeting → journal" · "It listened" · "End of day".
- Export vertical 1080×1920, ≤ 2 minutes. No music needed; if any, keep it under the voice.

## What to say (if you narrate, ~12 lines)

1. "I connected my calendar once this morning. This is a seeded sample day — I'll say that up front."
2. "From here I never type anything the bot needs."
3. "Fifteen minutes before each meeting: one line, in one of four voices — astrology, hype, warm, a quote."
4. "Thumbs down. Watch the next one change register."
5. "After the meeting: how did it go. One tap. Or a line, if I want — that's my journal."
6. "The next nudge already knows what I wrote."
7. "Nine o'clock: the day, closed. Every meeting, my mood, my notes, one reflection."
8. "Everything it learned is in `/stats`. Nothing was asked of me except taps."

## Fallbacks

- No wifi on stage → messages still arrive from built-in templates; no LLM needed.
- Phone dies → the recording is the demo. Never demo live if you have a recording.

## The easy way: `/play`

One command runs the whole day in about three minutes, pausing at each point for your real tap or note:

1. Clear the chat history, `/reset`, start the screen recorder.
2. `/start` → name → timezone → sun sign (30 s of onboarding on camera).
3. Send `/play`. Then just react:
   - day reading → wait
   - ⏰ standup → tap 👍
   - ✅ standup → tap 😐, type "quick one, nothing new"
   - ⏰ investor call → tap 👎
   - ✅ investor call → tap 🔥, type "they pushed on burn, I held the line"
   - ⏰ 1:1 with Priya → read it; it echoes your note
   - 🌙 day closed → arrives on its own
   - 📊 stats → arrives on its own
4. Stop recording. Total ≈ 3½ minutes, no editing required beyond trimming the ends.

If you don't tap, it moves on after ~20–45 s. Every message is the real pipeline; only the clock is compressed — and the first message on screen says so.
