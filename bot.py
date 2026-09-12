"""Computer Josiyam — Telegram bot that reads an ICS calendar and sends
positive-reinforcement nudges before and after meetings.

One-time setup: /start, then /connect <ics url>. After that, no input needed.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

from feed import upcoming
from voice import REGISTERS, compose, pick_register

load_dotenv()
logging.basicConfig(format="%(asctime)s %(levelname)s %(name)s: %(message)s", level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger("josiyam")

TZ = ZoneInfo(os.getenv("TZ_NAME", "Asia/Kolkata"))
PRE_LEAD = int(os.getenv("PRE_LEAD_MINUTES", "15"))
POST_LAG = int(os.getenv("POST_LAG_MINUTES", "5"))
POLL_SECONDS = int(os.getenv("POLL_SECONDS", "60"))
DAY_AHEAD_HOUR, DAY_AHEAD_MIN = (int(x) for x in os.getenv("DAY_AHEAD_AT", "08:30").split(":"))
STATE_PATH = Path(os.getenv("STATE_PATH", "state.json"))

# ---------------------------------------------------------------- state ----
DEFAULT_STATE = {
    "chat_id": None,
    "ics_url": None,
    "sent": [],  # "uid:kind:startiso" keys, so a restart never double-sends
    "tone": {r: 1.0 for r in REGISTERS},
    "last_register": {},  # message_id -> register, for 👍/👎 attribution
}


def load_state() -> dict:
    if STATE_PATH.exists():
        s = json.loads(STATE_PATH.read_text())
        return {**DEFAULT_STATE, **s}
    return dict(DEFAULT_STATE)


def save_state(s: dict) -> None:
    s["sent"] = s["sent"][-2000:]  # keep the file small
    STATE_PATH.write_text(json.dumps(s, indent=2))


state = load_state()

# ------------------------------------------------------------- handlers ----
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    state["chat_id"] = update.effective_chat.id
    save_state(state)
    await update.message.reply_text(
        "Hi, I'm Computer Josiyam.\n\n"
        "Josiyam means astrology. Connect your calendar once and I'll read your day and send a word of encouragement "
        f"{PRE_LEAD} min before each meeting and a close-out after.\n\n"
        "Google Calendar → Settings → your calendar → 'Secret address in iCal format'. "
        "Then send me:\n/connect <that url>"
    )


async def connect(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not ctx.args:
        await update.message.reply_text("Usage: /connect <ics url>")
        return
    url = ctx.args[0]
    try:
        evs = upcoming(url, hours=24)
    except Exception as e:  # bad url, network, not an ICS
        await update.message.reply_text(f"Couldn't read that calendar: {e}")
        return
    state["chat_id"] = update.effective_chat.id
    state["ics_url"] = url
    save_state(state)
    await update.message.reply_text(
        f"Connected. I see {len(evs)} event(s) in the next 24h. You won't need to talk to me again."
    )
    await poll_feed(ctx)  # schedule immediately instead of waiting a minute


async def today(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not state["ics_url"]:
        await update.message.reply_text("No calendar yet. /connect <ics url>")
        return
    await send_day_ahead(ctx)


async def status(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    jobs = [j for j in ctx.job_queue.jobs() if j.name.startswith("nudge:")]
    tone = ", ".join(f"{k} {v:.1f}" for k, v in state["tone"].items())
    await update.message.reply_text(
        f"Calendar: {'connected' if state['ics_url'] else 'none'}\n"
        f"Scheduled nudges: {len(jobs)}\n"
        f"Tone weights: {tone}"
    )


async def disconnect(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    state["ics_url"] = None
    save_state(state)
    for j in ctx.job_queue.jobs():
        if j.name.startswith("nudge:"):
            j.schedule_removal()
    await update.message.reply_text("Disconnected.")


async def feedback(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    verdict, register = q.data.split(":", 1)
    delta = 0.5 if verdict == "up" else -0.4
    state["tone"][register] = max(0.1, state["tone"].get(register, 1.0) + delta)
    save_state(state)
    await q.edit_message_reply_markup(reply_markup=None)
    log.info("feedback %s on %s -> %s", verdict, register, state["tone"])


# ----------------------------------------------------------------- jobs ----
def _keyboard(register: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("👍", callback_data=f"up:{register}"),
          InlineKeyboardButton("👎", callback_data=f"down:{register}")]]
    )


async def _send(ctx: ContextTypes.DEFAULT_TYPE, kind: str, events: list[dict]) -> None:
    if not state["chat_id"]:
        return
    register = pick_register(state["tone"])
    text = compose(kind, register, events, lead_minutes=PRE_LEAD)
    await ctx.bot.send_message(chat_id=state["chat_id"], text=text, reply_markup=_keyboard(register))
    log.info("sent %s [%s] for %s", kind, register, events[0]["title"] if events else "-")


async def send_nudge(ctx: ContextTypes.DEFAULT_TYPE) -> None:
    data = ctx.job.data
    await _send(ctx, data["kind"], [data["ev"]])


async def send_day_ahead(ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not state["ics_url"]:
        return
    now = datetime.now(TZ)
    end_of_day = now.replace(hour=23, minute=59, second=0)
    hours = max(1, int((end_of_day - now).total_seconds() // 3600) + 1)
    try:
        evs = upcoming(state["ics_url"], hours=hours)
    except Exception as e:
        log.warning("day-ahead fetch failed: %s", e)
        return
    evs = [e for e in evs if e["start"].date() == now.date()]
    if not evs:
        return
    await _send(ctx, "day", evs)


async def poll_feed(ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Every POLL_SECONDS: fetch the feed and schedule any nudge not yet scheduled."""
    if not state["ics_url"]:
        return
    try:
        evs = upcoming(state["ics_url"], hours=24)
    except Exception as e:
        log.warning("feed fetch failed: %s", e)
        return
    now = datetime.now(TZ)
    sent = set(state["sent"])
    scheduled = 0
    for ev in evs:
        for kind, when in (
            ("pre", ev["start"] - timedelta(minutes=PRE_LEAD)),
            ("post", ev["end"] + timedelta(minutes=POST_LAG)),
        ):
            key = f'{ev["uid"]}:{kind}:{ev["start"].isoformat()}'
            if key in sent or when < now:
                continue
            sent.add(key)
            ctx.job_queue.run_once(send_nudge, when=when, data={"ev": ev, "kind": kind}, name=f"nudge:{key}")
            scheduled += 1
    state["sent"] = sorted(sent)
    save_state(state)
    if scheduled:
        log.info("scheduled %d nudge(s) from %d event(s)", scheduled, len(evs))


# ----------------------------------------------------------------- main ----
def main() -> None:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("connect", connect))
    app.add_handler(CommandHandler("today", today))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("disconnect", disconnect))
    app.add_handler(CallbackQueryHandler(feedback))

    app.job_queue.run_repeating(poll_feed, interval=POLL_SECONDS, first=5, name="poll")
    app.job_queue.run_daily(send_day_ahead, time=time(DAY_AHEAD_HOUR, DAY_AHEAD_MIN, tzinfo=TZ), name="day-ahead")

    log.info("Computer Josiyam up. lead=%dm lag=%dm poll=%ds", PRE_LEAD, POST_LAG, POLL_SECONDS)
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
