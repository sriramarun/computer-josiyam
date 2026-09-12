"""Computer Josiyam — Telegram bot that reads an ICS calendar and sends
positive-reinforcement nudges before and after meetings.

One-time setup: /start walks through name → timezone → sun sign → calendar.
After that the bot only ever pushes; the only input is a tap.
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

import store
from feed import upcoming
from voice import compose, pick_register

load_dotenv()
logging.basicConfig(format="%(asctime)s %(levelname)s %(name)s: %(message)s", level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("apscheduler").setLevel(logging.WARNING)
log = logging.getLogger("josiyam")

PRE_LEAD = int(os.getenv("PRE_LEAD_MINUTES", "15"))
POST_LAG = int(os.getenv("POST_LAG_MINUTES", "5"))
POLL_SECONDS = int(os.getenv("POLL_SECONDS", "60"))
DAY_AHEAD_AT = os.getenv("DAY_AHEAD_AT", "08:30")

TIMEZONES = [("🇮🇳 IST", "Asia/Kolkata"), ("🇬🇧 London", "Europe/London"),
             ("🇺🇸 New York", "America/New_York"), ("🇺🇸 San Francisco", "America/Los_Angeles")]
URL_RE = re.compile(r"(https?://\S+|webcal://\S+|\S+\.ics)", re.I)

ICS_HOWTO = (
    "Last step: your calendar. I need the private read-only link, not a login.\n\n"
    "Google Calendar (on a computer):\n"
    "1. calendar.google.com → ⚙️ Settings\n"
    "2. Left side, under 'Settings for my calendars', tap your calendar\n"
    "3. Scroll to 'Secret address in iCal format' → copy\n\n"
    "Apple: Calendar app → right-click calendar → Share → Public Calendar → copy link\n"
    "Outlook: Settings → Calendar → Shared calendars → Publish → ICS link\n\n"
    "Paste the link here. That's the last time you'll need to type anything.\n"
    "(No calendar handy? Send /demo to use a sample day.)"
)


def tz_of(user) -> ZoneInfo:
    try:
        return ZoneInfo(user["tz"] or "Asia/Kolkata")
    except Exception:
        return ZoneInfo("Asia/Kolkata")


# ----------------------------------------------------------- onboarding ----
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    u = store.ensure_user(chat_id)
    if u["ics_url"]:
        await update.message.reply_text(
            f"Welcome back{', ' + u['name'] if u['name'] else ''}. Your calendar is connected. "
            "/today for a reading, /stats to see what I've learned, /reset to start over."
        )
        return
    store.set_user(chat_id, step="name")
    await update.message.reply_text(
        "Hi, I'm Computer Josiyam. Josiyam is Tamil for astrology.\n\n"
        "Connect your calendar once and I'll send a word of encouragement before each meeting "
        "and a close-out after. You never have to message me again.\n\n"
        "Three quick questions. First: what should I call you?"
    )


async def on_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Free text arrives in exactly two situations: the name, or a pasted calendar link."""
    chat_id = update.effective_chat.id
    text = (update.message.text or "").strip()
    u = store.ensure_user(chat_id)

    m = URL_RE.search(text)
    if m and (u["step"] in ("ics", "done") or "calendar" in text or text.endswith(".ics")):
        await do_connect(update, ctx, m.group(1))
        return

    if u["step"] == "name":
        name = text.split()[0][:30] if text else None
        store.set_user(chat_id, name=name, step="tz")
        kb = InlineKeyboardMarkup([[InlineKeyboardButton(lbl, callback_data=f"tz:{tz}")] for lbl, tz in TIMEZONES])
        await update.message.reply_text(f"Good to meet you, {name}. Which timezone are your meetings in?", reply_markup=kb)
        return

    if u["step"] == "tz":
        await update.message.reply_text("Tap one of the timezone buttons above.")
    elif u["step"] == "sunsign":
        await update.message.reply_text("Tap your sun sign above.")
    elif u["step"] == "ics":
        await update.message.reply_text("That doesn't look like a calendar link. " + ICS_HOWTO)
    else:
        await update.message.reply_text("I only push messages, I don't chat. /today · /stats · /help")


async def on_tz(q, chat_id: int, tz: str) -> None:
    store.set_user(chat_id, tz=tz, step="sunsign")
    signs = store.SUNSIGNS
    kb = InlineKeyboardMarkup([[InlineKeyboardButton(x, callback_data=f"sign:{x}") for x in signs[i:i + 4]] for i in range(0, 12, 4)])
    await q.edit_message_text(f"Timezone set: {tz}.")
    await q.message.reply_text("Josiyam needs one thing: your sun sign.", reply_markup=kb)


async def on_sign(q, chat_id: int, sign: str) -> None:
    store.set_user(chat_id, sunsign=sign, step="ics")
    await q.edit_message_text(f"{sign}. Noted.")
    await q.message.reply_text(ICS_HOWTO)


async def do_connect(update: Update, ctx: ContextTypes.DEFAULT_TYPE, url: str) -> None:
    chat_id = update.effective_chat.id
    u = store.ensure_user(chat_id)
    url = url.rstrip(").,")
    try:
        evs = await asyncio.to_thread(upcoming, url, 24, None, tz_of(u))
    except Exception as e:
        await update.message.reply_text(f"Couldn't read that calendar: {str(e)[:120]}\n\nCheck it's the secret iCal link and try again.")
        return
    store.set_user(chat_id, ics_url=url, step="done")
    store.clear_sent(chat_id)
    await update.message.reply_text(f"Connected. I can see {len(evs)} event(s) in the next 24 hours. Here's your day:")
    await schedule_for_user(ctx, store.get_user(chat_id))
    sent = await send_day_ahead(ctx, store.get_user(chat_id), force=True)
    if not sent:
        nxt = evs[0] if evs else None
        await update.message.reply_text(
            f"Nothing more today. Next up: {nxt['title']} at {nxt['start']:%a %H:%M}." if nxt else "Nothing in the next 24 hours. I'll be here when there is."
        )


async def connect_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not ctx.args:
        await update.message.reply_text("Usage: /connect <ics url>")
        return
    await do_connect(update, ctx, ctx.args[0])


async def demo(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Seed the sample calendar and connect it. For stage use."""
    chat_id = update.effective_chat.id
    u = store.ensure_user(chat_id)
    if not u["name"]:
        store.set_user(chat_id, name="Sriram", sunsign=u["sunsign"] or "Leo", step="done")
    subprocess.run([sys.executable, "demo/seed.py"], check=True, capture_output=True)
    await update.message.reply_text("Using the sample calendar: a founder's Friday in Bangalore.")
    await do_connect(update, ctx, "demo/demo.ics")


# ------------------------------------------------------------- commands ----
async def today(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    u = store.get_user(update.effective_chat.id)
    if not u or not u["ics_url"]:
        await update.message.reply_text("No calendar yet. Send /start.")
        return
    if not await send_day_ahead(ctx, u, force=True):
        await update.message.reply_text("Nothing left on the calendar today.")


async def stats_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    s = store.stats(update.effective_chat.id)
    n_fb = s["up"] + s["down"]
    pct = f"{100 * s['up'] // n_fb}%" if n_fb else "—"
    regs = "\n".join(
        f"  {r}: {up}/{n} liked" for r, (up, n) in s["per_register"].items()
    ) or "  (no taps yet)"
    moods = ", ".join(f"{k} ×{v}" for k, v in s["moods"].items()) or "none yet"
    w = " · ".join(f"{k} {v:.1f}" for k, v in s["weights"].items())
    lat = f"{s['avg_latency_s']:.0f}s" if s["avg_latency_s"] else "—"
    await update.message.reply_text(
        f"Messages sent: {s['messages']}\n"
        f"Thumbs up: {pct} of {n_fb} taps\n"
        f"By voice:\n{regs}\n"
        f"Avg time to react: {lat}\n"
        f"Post-meeting moods: {moods}\n"
        f"Current voice weights: {w}"
    )


async def status(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    u = store.get_user(chat_id)
    jobs = [j for j in ctx.job_queue.jobs() if j.name.startswith(f"nudge:{chat_id}:")]
    await update.message.reply_text(
        f"Name: {u['name'] if u else '—'}\nTimezone: {u['tz'] if u else '—'}\n"
        f"Sun sign: {u['sunsign'] if u else '—'}\nCalendar: {'connected' if u and u['ics_url'] else 'none'}\n"
        f"Scheduled nudges: {len(jobs)}"
    )


async def reset(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    for j in ctx.job_queue.jobs():
        if j.name.startswith(f"nudge:{chat_id}:"):
            j.schedule_removal()
    store.delete_user(chat_id)
    await update.message.reply_text("Forgotten. Your message history stays for /stats. Send /start to begin again.")


async def help_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "/start — set up (once)\n/today — reading for the rest of today\n/stats — what I've learned about you\n"
        "/status — connection and schedule\n/demo — use the sample calendar\n/reset — forget me"
    )


# ------------------------------------------------------------- feedback ----
async def on_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    chat_id = q.message.chat_id
    kind, _, arg = q.data.partition(":")

    if kind == "tz":
        await q.answer()
        await on_tz(q, chat_id, arg)
        return
    if kind == "sign":
        await q.answer()
        await on_sign(q, chat_id, arg)
        return

    if kind in ("up", "down"):
        message_id = int(arg)
        latency = store.record_feedback(message_id, chat_id, kind)
        m = store.get_message(message_id)
        reg = m["register"] if m else "?"
        toast, footer = (("More like this.", "👍 noted — more of this voice") if kind == "up"
                         else ("Understood. Changing register.", "👎 noted — the next one will sound different"))
        await q.answer(toast)
        log.info("feedback %s on %s (%.0fs) -> %s", kind, reg, latency, store.tone_weights(chat_id))

    elif kind == "mood":
        value, _, mid = arg.partition(":")
        message_id = int(mid)
        store.record_mood(chat_id, value, source="tap", message_id=message_id)
        # a great meeting is also a vote for the voice that closed it out; rough is not a vote against
        if value == "great":
            store.record_feedback(message_id, chat_id, "up")
        toast = {"rough": "Noted. That one's behind you.", "fine": "Fine is fine.", "great": "Good. Carry that."}[value]
        footer = {"rough": "😮‍💨 rough — noted", "fine": "😐 fine — noted", "great": "🔥 great — noted"}[value]
        await q.answer(toast)
        log.info("mood %s for message %d", value, message_id)
    else:
        await q.answer()
        return

    try:
        await q.edit_message_text(f"{q.message.text}\n\n{footer}")
    except Exception as e:
        log.warning("could not edit message: %s", e)


async def on_error(update: object, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    log.error("handler error: %s", ctx.error, exc_info=ctx.error)


# ----------------------------------------------------------------- jobs ----
def _keyboard(kind: str, message_id: int) -> InlineKeyboardMarkup:
    if kind == "post":  # one-tap mood, piggybacked on a message we were sending anyway
        return InlineKeyboardMarkup([[
            InlineKeyboardButton("😮‍💨 rough", callback_data=f"mood:rough:{message_id}"),
            InlineKeyboardButton("😐 fine", callback_data=f"mood:fine:{message_id}"),
            InlineKeyboardButton("🔥 great", callback_data=f"mood:great:{message_id}"),
        ]])
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("👍", callback_data=f"up:{message_id}"),
        InlineKeyboardButton("👎", callback_data=f"down:{message_id}"),
    ]])


async def _send(ctx: ContextTypes.DEFAULT_TYPE, user, kind: str, events: list[dict], density: int | None = None) -> bool:
    chat_id = user["chat_id"]
    register = pick_register(store.tone_weights(chat_id), avoid=store.last_register(chat_id))
    ev = events[0] if events else None
    context = {
        "event_class": ev.get("klass") if ev else None,
        "density": density,
        "moods": [r["value"] for r in store.recent_moods(chat_id)][:5] if kind in ("day", "pre") else None,
        "sunsign": user["sunsign"],
    }
    text = await asyncio.to_thread(compose, kind, register, events, PRE_LEAD, user["name"], context)
    message_id = store.record_message(chat_id, kind, register, text, ev)
    for attempt in range(4):  # wifi blips happen; a nudge 10s late beats a nudge never
        try:
            msg = await ctx.bot.send_message(chat_id=chat_id, text=text, reply_markup=_keyboard(kind, message_id))
            store.set_tg_message_id(message_id, msg.message_id)
            log.info("sent %s [%s] to %s for %s", kind, register, chat_id, ev["title"] if ev else "-")
            return True
        except Exception as e:
            log.warning("send failed (attempt %d): %s", attempt + 1, e)
            await asyncio.sleep(3 * (attempt + 1))
    log.error("gave up sending %s to %s", kind, chat_id)
    return False


async def send_nudge(ctx: ContextTypes.DEFAULT_TYPE) -> None:
    d = ctx.job.data
    user = store.get_user(d["chat_id"])
    if not user or not user["ics_url"]:
        return
    await _send(ctx, user, d["kind"], [d["ev"]], density=d.get("density"))


async def send_day_ahead(ctx: ContextTypes.DEFAULT_TYPE, user, force: bool = False) -> bool:
    if not user["ics_url"]:
        return False
    tz = tz_of(user)
    now = datetime.now(tz)
    key = f"day:{now:%Y-%m-%d}"
    if not force and store.already_sent(user["chat_id"], key):
        return False
    try:
        evs = await asyncio.to_thread(upcoming, user["ics_url"], 24, None, tz)
    except Exception as e:
        log.warning("day-ahead fetch failed: %s", e)
        return False
    evs = [e for e in evs if e["start"].date() == now.date()]
    if not evs:
        return False
    store.mark_sent(user["chat_id"], key)
    return await _send(ctx, user, "day", evs, density=len(evs))


async def schedule_for_user(ctx: ContextTypes.DEFAULT_TYPE, user) -> int:
    chat_id = user["chat_id"]
    tz = tz_of(user)
    try:
        evs = await asyncio.to_thread(upcoming, user["ics_url"], 24, None, tz)
    except Exception as e:
        log.warning("feed fetch failed for %s: %s", chat_id, e)
        return 0
    now = datetime.now(tz)
    density = sum(1 for e in evs if e["start"].date() == now.date())
    if density >= 5 and not store.already_sent(chat_id, f"dense:{now:%Y-%m-%d}"):
        store.record_mood(chat_id, "dense_day", source="passive")  # passive signal, no tap needed
        store.mark_sent(chat_id, f"dense:{now:%Y-%m-%d}")
    scheduled = 0
    for ev in evs:
        for kind, when in (("pre", ev["start"] - timedelta(minutes=PRE_LEAD)),
                           ("post", ev["end"] + timedelta(minutes=POST_LAG))):
            key = f'{ev["uid"]}:{kind}:{ev["start"].isoformat()}'
            if when < now or store.already_sent(chat_id, key):
                continue
            store.mark_sent(chat_id, key)
            ctx.job_queue.run_once(
                send_nudge, when=when, name=f"nudge:{chat_id}:{key}",
                data={"chat_id": chat_id, "ev": ev, "kind": kind, "density": density},
                job_kwargs={"misfire_grace_time": 300},
            )
            scheduled += 1
    if scheduled:
        log.info("scheduled %d nudge(s) for %s from %d event(s)", scheduled, chat_id, len(evs))
    return scheduled


async def poll_feed(ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Every POLL_SECONDS: for every connected user, fetch the feed and schedule new nudges."""
    for user in store.connected_users():
        await schedule_for_user(ctx, user)


async def daily_tick(ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Once a minute: whose local clock just hit DAY_AHEAD_AT? Timezone-correct per user."""
    for user in store.connected_users():
        if datetime.now(tz_of(user)).strftime("%H:%M") == DAY_AHEAD_AT:
            await send_day_ahead(ctx, user)


# ----------------------------------------------------------------- main ----
def main() -> None:
    store.db()
    app = Application.builder().token(os.environ["TELEGRAM_BOT_TOKEN"]).build()
    for name, fn in [("start", start), ("connect", connect_cmd), ("today", today), ("stats", stats_cmd),
                     ("status", status), ("demo", demo), ("reset", reset), ("help", help_cmd),
                     ("disconnect", reset)]:
        app.add_handler(CommandHandler(name, fn))
    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    app.add_error_handler(on_error)

    app.job_queue.run_repeating(poll_feed, interval=POLL_SECONDS, first=5, name="poll")
    app.job_queue.run_repeating(daily_tick, interval=60, first=10, name="daily-tick")

    log.info("Computer Josiyam up. lead=%dm lag=%dm poll=%ds day-ahead=%s", PRE_LEAD, POST_LAG, POLL_SECONDS, DAY_AHEAD_AT)
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
