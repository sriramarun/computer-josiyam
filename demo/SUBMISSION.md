# Submission — Agents, Everywhere: Bots, Channels & More (AI Tinkerers, 12 Sep 2026)

Deadline 16:00. Five things: title, description, public repo, two-minute video, social post.

---

## 1. Project title

**Computer Josiyam** — an agent that lives in your calendar and speaks through Telegram

## 2. Written description (paste as-is)

**What it is.** Computer Josiyam is an agent that belongs in two places you already live: your calendar and your messaging app. You connect a calendar once — the private ICS link, no OAuth — and from then on it acts without being asked. Fifteen minutes before every meeting it sends one line of encouragement. After every meeting it asks how it went, with one tap. At night it closes the day: every meeting, the mood you tapped, the notes you wrote, one reflection. It never needs a chat box. *Josiyam* is Tamil for astrology; one of its four voices reads your day like a horoscope, using your sun sign.

**Who it is for.** Anyone whose day is a stack of meetings and who would never open a journaling app. Founders, managers, anyone before a hard call.

**Why the context matters.** A chatbot waits to be asked. This agent reads the environment instead: the meeting title tells it whether the moment is hard (investor call) or nourishing (1:1, lunch with Amma); the day's density tells it to be brief; your taps and notes tell it which voice lands. The only input it ever asks for is a tap on a message it was already sending. Judges penalise daily input — this asks for none.

**What it learns.** Every message, tap, reaction time, mood and journal note is a row in SQLite. Four voices (astrology, hype, warm, quote) shuffle by weights derived from your last 30 taps. Your journal notes are fed into the next nudge, so it visibly listens. `/stats` shows all of it.

**Stack.** Python, python-telegram-bot, icalendar + recurring-ical-events, SQLite. LLM via **OpenRouter** (DeepSeek V4 Flash, ~$0.00002 per message, fallback chain to a free model, template fallback if offline). The demo calendar is seeded and says so on screen.

## 3. Repo

https://github.com/sriramarun/computer-josiyam

## 4. Two-minute video — voiceover (≤ 1:55)

Record the screen with `/play`, lay the voice over afterwards. Read at a steady pace; this is ~190 words, about 95 seconds.

**[0:00 — /start, name, IST, sun sign]**
The brief was an agent that belongs somewhere new. This one lives in my calendar and speaks through Telegram.
Computer Josiyam. Josiyam is Tamil for astrology.
Setup is three taps and one calendar link, pasted once. This is a sample day — the bot says so itself.

**[0:20 — /play, day reading]**
From here, I don't type anything it needs. Every morning, a reading of the day ahead.

**[0:35 — ⏰ standup, 👍]**
Before each meeting, one line, in one of four voices. A thumbs-up teaches it which one lands.

**[0:45 — ✅ standup, 😐, note]**
After each meeting: how did it go. One tap. Or a line of my own. That's a journal I never had to open.

**[1:00 — ⏰ investor call, 👎]**
It read the title. It knows this one is hard, and steadies instead of cheering. Thumbs down — the next voice changes.

**[1:10 — ✅ investor call, 🔥, note]**
Went well. I say so.

**[1:25 — ⏰ 1:1 with Priya]**
The next nudge already knows what I wrote.

**[1:35 — 🌙 day closed]**
At night, the day closed: every meeting, my mood, my notes, one reflection.

**[1:45 — 📊 stats]**
Everything it learned, in one screen. Runs on OpenRouter for a fraction of a cent a day.
An agent in the calendar, not in a chat box. Nothing asked of me but a tap.

**[1:52 — closing card, 3 s]**
Computer Josiyam · github.com/sriramarun/computer-josiyam

## 5. Social post (X / LinkedIn)

Built at @aitinkerers Puducherry for the global "Agents, Everywhere" hackathon:

**Computer Josiyam** — an agent that lives in your calendar and speaks through Telegram.

Connect a calendar once. Then: one line before every meeting, one tap after, a journal you never open, and the day closed at night. It reads the meeting title to know when you need steadying, and learns which of four voices lands — one of them is Tamil astrology, with your sun sign.

Never asks for input. Only taps.

Runs on @OpenRouterAI (DeepSeek, ~$0.00002/message). Python + Telegram + SQLite.

Repo: github.com/sriramarun/computer-josiyam
#AgentsEverywhere #AITinkerers @OpenAI @CopilotKit

(Check the event page for the exact sponsor handles before posting.)

## Timeline to 16:00

| By | Do |
|---|---|
| 15:00 | Record: clear chat → /reset → record → /start → /play. One take. |
| 15:15 | Record voiceover on phone voice memo, reading section 4. |
| 15:35 | Trim + overlay in CapCut/iMovie. Check it is under 2:00. Export. |
| 15:45 | Submit title, description (section 2), repo, video. |
| 15:50 | Post section 5 with the video. |
