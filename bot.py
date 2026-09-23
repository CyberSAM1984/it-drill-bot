# -*- coding: utf-8 -*-
"""IT Drill Bot — тренажёр IT-инженера в Telegram.

Использование:
    python bot.py            # запустить бота (BOT_TOKEN из .env или переменных)
    python bot.py stats      # статистика базы
"""
import json
import logging
import os
import random
from pathlib import Path

from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters,
)

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
QUESTIONS_FILE = DATA_DIR / "questions.json"
CASES_FILE = DATA_DIR / "cases.json"
PROGRESS_FILE = DATA_DIR / "progress.json"
QUESTIONS_PER_SESSION = 10

TOPICS = {
    "linux": "🐧 Linux", "net": "🌐 Сети", "db": "🗄 Базы данных",
    "proto": "📡 Протоколы", "fs": "💾 Файловые системы",
    "crypto": "🔐 Криптография", "sd": "🏗 System Design",
    "tls": "🔒 TLS", "cs": "🧠 Computer Science",
}
LEVELS = {"jun": "Junior", "mid": "Middle", "sen": "Senior"}

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s %(message)s", level=logging.INFO
)
log = logging.getLogger("it-drill")


# ------------------------------------------------------------------ данные

def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


class Quiz:
    def __init__(self):
        self.questions = load_json(QUESTIONS_FILE)
        self.cases = load_json(CASES_FILE)
        self.progress = {}
        if PROGRESS_FILE.exists():
            try:
                self.progress = load_json(PROGRESS_FILE)
            except Exception:
                self.progress = {}

    def save_progress(self):
        try:
            PROGRESS_FILE.write_text(
                json.dumps(self.progress, ensure_ascii=False, indent=1),
                encoding="utf-8",
            )
        except Exception as e:
            log.warning("progress save failed: %s", e)

    # --- выборки
    def pick(self, topic=None, level=None, count=QUESTIONS_PER_SESSION):
        pool = [q for q in self.questions
                if (topic is None or q["t"] == topic)
                and (level is None or q["lvl"] == level)]
        random.shuffle(pool)
        return pool[:count]

    # --- сессии
    def start(self, user_id, topic=None, level=None):
        qs = self.pick(topic, level)
        if not qs:
            return None
        self.progress[str(user_id)] = {
            "q": [x["key"] for x in qs], "i": 0,
            "topic": topic, "level": level, "score": 0, "self": [],
        }
        self.save_progress()
        return qs

    def session(self, user_id):
        return self.progress.get(str(user_id))

    def current(self, user_id):
        s = self.session(user_id)
        if not s or s["i"] >= len(s["q"]):
            return None
        key = s["q"][s["i"]]
        return next(x for x in self.questions if x["key"] == key)

    def submit(self, user_id, text, self_rating=None):
        """Записать ответ пользователя, сдвинуть индикатор, вернуть вопрос."""
        s = self.session(user_id)
        q = self.current(user_id)
        if not s or not q:
            return None
        s["self"].append({"key": q["key"], "answer": (text or "")[:2000],
                          "rating": self_rating})
        s["i"] += 1
        if self_rating == "ok":
            s["score"] += 1
        self.save_progress()
        return q

    def finish(self, user_id):
        s = self.session(user_id)
        if s:
            self.progress.pop(str(user_id), None)
            self.save_progress()
        return s

    # --- статистика
    def stats(self):
        by_topic, by_level = {}, {}
        for q in self.questions:
            by_topic[q["t"]] = by_topic.get(q["t"], 0) + 1
            by_level[q["lvl"]] = by_level.get(q["lvl"], 0) + 1
        return {"total": len(self.questions), "cases": len(self.cases),
                "by_topic": by_topic, "by_level": by_level}


quiz = Quiz()


# ------------------------------------------------------------------ вывод

def q_text(q, i, total):
    hard = " 🔥" if q.get("hard") else ""
    lvl = LEVELS.get(q["lvl"], q["lvl"])
    head = f"📝 Вопрос {i} из {total} · {lvl}{hard}"
    body = f"{q['q']}"
    if q.get("code"):
        body = f"{q['q']}\n\n```\n{q['code']}\n```"
    return f"{head}\n\n{TOPICS.get(q['t'], q['t'])}\n\n{body}\n\n" \
           f"Ответь своими словами или «не знаю»."


def a_text(q, user_answer, i, total):
    parts = [f"📚 Разбор (вопрос {i} из {total})",
             f"\n❓ {q['q']}",
             f"\n✍️ Твой ответ:\n{user_answer}",
             f"\n📖 {q['a']}"]
    if q.get("d"):
        parts.append("\n🔎 Подробнее:\n• " + "\n• ".join(q["d"]))
    if q.get("f"):
        parts.append("\n🎯 Проверь себя:\n• " + "\n• ".join(q["f"]))
    return "\n".join(parts)


def rating_keyboard():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("😅 Не знал", callback_data="rate:no"),
        InlineKeyboardButton("🤔 Частично", callback_data="rate:part"),
        InlineKeyboardButton("😀 Знал", callback_data="rate:ok"),
    ]])


# ------------------------------------------------------------------ хендлеры

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 *Тренажёр IT-инженера*\n\n"
        f"В базе {len(quiz.questions)} вопросов по 9 темам "
        f"(Junior/Middle/Senior) и {len(quiz.cases)} разборов реальных "
        "инцидентов.\n\n"
        "*Команды:*\n"
        "/quiz — викторина (10 случайных вопросов)\n"
        "/topic — выбрать тему\n"
        "/level — выбрать уровень\n"
        "/case — разбор инцидента\n"
        "/stats — статистика базы\n"
        "/cancel — сбросить сессию\n\n"
        "Отвечай своими словами, потом сам оцениваешь себя по кнопкам.",
        parse_mode="Markdown",
    )


async def cmd_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    qs = quiz.start(user_id)
    if not qs:
        await update.message.reply_text("❌ Не удалось подобрать вопросы.")
        return
    await update.message.reply_text(f"🎯 {len(qs)} вопросов. Поехали!")
    await send_question(update.effective_chat.id, user_id)


async def send_question(chat_id, user_id):
    s = quiz.session(user_id)
    q = quiz.current(user_id)
    if not q or not s:
        await send_summary(chat_id, user_id)
        return
    await context_safe_reply(chat_id, q_text(q, s["i"] + 1, len(s["q"])))


async def context_safe_reply(chat_id, text):
    """Отправить сообщение в чат, безопасно для Markdown."""
    from telegram.constants import ParseMode
    try:
        await APP.bot.send_message(chat_id, text)
    except Exception:
        await APP.bot.send_message(chat_id, text[:4000])


APP = None


async def handle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    s = quiz.session(user_id)
    if not s or s["i"] >= len(s["q"]):
        await update.message.reply_text("Нет активной сессии. /quiz чтобы начать.")
        return
    q = quiz.submit(user_id, update.message.text)
    await update.message.reply_text(
        a_text(q, update.message.text, s["i"] + 1, len(s["q"]))
    )
    nxt = quiz.session(user_id)
    if nxt["i"] >= len(nxt["q"]):
        await update.message.reply_text(
            "Как ты оцениваешь последний ответ?",
            reply_markup=rating_keyboard(),
        )
    else:
        await send_question(update.effective_chat.id, user_id)


async def rate_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Самооценка по кнопке после последнего вопроса."""
    query = update.callback_query
    await query.answer()
    rating = query.data.split(":", 1)[1]
    user_id = query.from_user.id
    s = quiz.session(user_id)
    if s and s["self"]:
        s["self"][-1]["rating"] = rating
        if rating == "ok":
            s["score"] += 1
        quiz.save_progress()
    await query.edit_message_text("Принято!")
    await send_summary(query.message.chat_id, user_id)


async def send_summary(chat_id, user_id):
    s = quiz.finish(user_id)
    if not s:
        return
    ok = s["score"]
    total = len(s["q"])
    emoji = "🏆" if ok >= total * 0.8 else "💪" if ok >= total * 0.5 else "📚"
    await context_safe_reply(
        chat_id,
        f"{emoji} Сессия завершена!\n\n"
        f"Самооценка «знал»: {ok} из {total}.\n"
        "Слабые места:\n"
        + "\n".join(
            f"• {next((x['q'] for x in quiz.questions if x['key'] == a['key']), a['key'])[:70]}"
            for a in s["self"] if a.get("rating") in (None, "no", "part")
        )[:3500]
        + "\n\n/quiz — ещё раз, /topic — по теме, /case — инцидент.",
    )


async def cmd_topic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [[InlineKeyboardButton(name, callback_data=f"topic:{code}")]
          for code, name in TOPICS.items()]
    await update.message.reply_text("Выбери тему:", reply_markup=InlineKeyboardMarkup(kb))


async def cmd_level(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [[InlineKeyboardButton(name, callback_data=f"level:{code}")]
          for code, name in LEVELS.items()]
    await update.message.reply_text("Выбери уровень:", reply_markup=InlineKeyboardMarkup(kb))


async def cmd_case(update: Update, context: ContextTypes.DEFAULT_TYPE):
    c = random.choice(quiz.cases)
    text = (
        f"🚨 *Инцидент {c['sev']} · {c['tag']}*\n\n"
        f"*{c['q']}*\n\n{c['sym']}"
    )
    if c.get("out"):
        text += f"\n\n```\n{c['out'][:1200]}\n```"
    text += "\n\nПодумай: как диагностировать? Отвечай, потом /case_show — разбор."
    context.user_data["case"] = c["key"]
    await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_case_show(update: Update, context: ContextTypes.DEFAULT_TYPE):
    key = context.user_data.get("case")
    if not key:
        await update.message.reply_text("Сначала /case — взять инцидент.")
        return
    c = next(x for x in quiz.cases if x["key"] == key)
    parts = [f"🔍 *Разбор: {c['q']}*"]
    for field, label in (("hyp", "Гипотезы"), ("diag", "Диагностика"),
                         ("cause", "Причина"), ("fix", "Решение"),
                         ("trap", "Ловушка")):
        if c.get(field):
            parts.append(f"\n*{label}:*\n{c[field]}")
    await update.message.reply_text("\n".join(parts)[:4000], parse_mode="Markdown")


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    st = quiz.stats()
    lines = [f"📚 База: {st['total']} вопросов, {st['cases']} инцидентов\n",
             "По темам:"] + \
        [f"• {TOPICS.get(k, k)}: {v}" for k, v in sorted(st["by_topic"].items())] + \
        ["", "По уровням:"] + \
        [f"• {LEVELS.get(k, k)}: {v}" for k, v in sorted(st["by_level"].items())]
    await update.message.reply_text("\n".join(lines))


async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    quiz.finish(update.effective_user.id)
    await update.message.reply_text("Сессия сброшена. /quiz для новой.")


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    kind, _, value = query.data.partition(":")
    topic = level = None
    if kind == "topic":
        topic = value
    elif kind == "level":
        level = value
    else:
        return
    qs = quiz.start(user_id, topic=topic, level=level)
    if not qs:
        await query.edit_message_text("Нет вопросов по этому фильтру.")
        return
    await query.edit_message_text(f"🎯 {len(qs)} вопросов. Поехали!")
    await send_question(query.message.chat_id, user_id)


async def error_handler(update, context: ContextTypes.DEFAULT_TYPE):
    log.error("Exception:", exc_info=context.error)


def main():
    global APP
    if len(os.sys.argv) > 1 and os.sys.argv[1] == "stats":
        print(json.dumps(quiz.stats(), ensure_ascii=False, indent=2))
        return

    load_dotenv(BASE_DIR / ".env")
    token = os.getenv("BOT_TOKEN")
    if not token:
        print("❌ BOT_TOKEN не найден. Создай .env: BOT_TOKEN=123:abc")
        raise SystemExit(1)
    if not quiz.questions:
        print("❌ data/questions.json пуст или отсутствует.")
        raise SystemExit(1)

    APP = Application.builder().token(token).build()
    APP.add_handler(CommandHandler("start", cmd_start))
    APP.add_handler(CommandHandler("quiz", cmd_quiz))
    APP.add_handler(CommandHandler("topic", cmd_topic))
    APP.add_handler(CommandHandler("level", cmd_level))
    APP.add_handler(CommandHandler("case", cmd_case))
    APP.add_handler(CommandHandler("case_show", cmd_case_show))
    APP.add_handler(CommandHandler("stats", cmd_stats))
    APP.add_handler(CommandHandler("cancel", cmd_cancel))
    APP.add_handler(CommandHandler("help", cmd_start))
    APP.add_handler(CallbackQueryHandler(rate_callback, pattern=r"^rate:"))
    APP.add_handler(CallbackQueryHandler(button_callback, pattern=r"^(topic|level):"))
    APP.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_answer))
    APP.add_error_handler(error_handler)
    APP.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
