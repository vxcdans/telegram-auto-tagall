import os
import time
import html
import asyncio
import logging
import sqlite3
from pathlib import Path

from dotenv import load_dotenv
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN", "").strip()
DB = Path(os.getenv("DB_PATH", "data/tagall.sqlite3"))
COOLDOWN = max(60, int(os.getenv("COOLDOWN_SECONDS", "600")))
MAX_MEMBERS = max(1, min(20, int(os.getenv("MAX_MENTIONS", "20"))))

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("AutoTagAll")


def database():
    DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS members (
            chat_id INTEGER,
            user_id INTEGER,
            name TEXT,
            joined INTEGER,
            PRIMARY KEY(chat_id, user_id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cooldown (
            chat_id INTEGER PRIMARY KEY,
            last_used INTEGER
        )
    """)
    conn.commit()
    return conn


async def group_only(update):
    chat = update.effective_chat
    if not chat or chat.type not in ("group", "supergroup"):
        await update.effective_message.reply_text("Gunakan perintah ini di grup.")
        return False
    return True


async def admin_only(update, context):
    try:
        member = await context.bot.get_chat_member(
            update.effective_chat.id, update.effective_user.id
        )
        return member.status in ("administrator", "creator")
    except Exception:
        return False


async def start(update, context):
    await update.effective_message.reply_text(
        "🤖 Auto TagAll Bot\\n\\n"
        "/tagme - daftar mention\\n"
        "/untagme - keluar dari daftar\\n"
        "/tagcount - jumlah anggota terdaftar\\n"
        "/tagall - mulai TagAll (admin)\\n"
        "/tagstop - hentikan TagAll (admin)\\n\\n"
        "Hanya anggota yang memilih /tagme yang akan di-mention."
    )


async def tagme(update, context):
    if not await group_only(update):
        return
    user = update.effective_user
    if not user or user.is_bot:
        return
    with database() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO members VALUES (?, ?, ?, ?)",
            (update.effective_chat.id, user.id, user.full_name, int(time.time()))
        )
    await update.effective_message.reply_text(
        "Kamu sudah terdaftar. Gunakan /untagme untuk keluar kapan saja."
    )


async def untagme(update, context):
    if not await group_only(update):
        return
    with database() as conn:
        conn.execute(
            "DELETE FROM members WHERE chat_id=? AND user_id=?",
            (update.effective_chat.id, update.effective_user.id)
        )
    await update.effective_message.reply_text("Kamu sudah keluar dari daftar mention.")


async def tagcount(update, context):
    if not await group_only(update):
        return
    with database() as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM members WHERE chat_id=?",
            (update.effective_chat.id,)
        ).fetchone()[0]
    await update.effective_message.reply_text(
        f"Anggota yang opt-in: {count}. Batas per proses: {MAX_MEMBERS}."
    )


async def tagstop(update, context):
    if not await group_only(update):
        return
    if not await admin_only(update, context):
        await update.effective_message.reply_text("Khusus admin grup.")
        return
    context.chat_data["tagall_stop"] = True
    await update.effective_message.reply_text("Permintaan berhenti diterima.")


async def tagall(update, context):
    if not await group_only(update):
        return
    chat_id = update.effective_chat.id

    if not await admin_only(update, context):
        await update.effective_message.reply_text("Hanya admin yang dapat memakai /tagall.")
        return

    if context.chat_data.get("tagall_running"):
        await update.effective_message.reply_text("TagAll sedang berjalan.")
        return

    now = int(time.time())
    with database() as conn:
        row = conn.execute(
            "SELECT last_used FROM cooldown WHERE chat_id=?", (chat_id,)
        ).fetchone()
        if row and now - row[0] < COOLDOWN:
            wait = COOLDOWN - (now - row[0])
            await update.effective_message.reply_text(
                f"Tunggu {wait // 60 + 1} menit sebelum menjalankan TagAll lagi."
            )
            return

        members = conn.execute(
            "SELECT user_id, name FROM members WHERE chat_id=? ORDER BY joined LIMIT ?",
            (chat_id, MAX_MEMBERS)
        ).fetchall()

        if not members:
            await update.effective_message.reply_text(
                "Belum ada anggota yang mendaftar. Gunakan /tagme."
            )
            return

        conn.execute(
            "INSERT OR REPLACE INTO cooldown VALUES (?, ?)", (chat_id, now)
        )

    context.chat_data["tagall_running"] = True
    context.chat_data["tagall_stop"] = False
    await update.effective_message.reply_text(
        f"Memulai TagAll untuk {len(members)} anggota yang sudah mendaftar."
    )

    stopped = False
    try:
        for i in range(0, len(members), 5):
            if context.chat_data.get("tagall_stop"):
                stopped = True
                break

            chunk = members[i:i + 5]
            text = " ".join(
                f'<a href="tg://user?id={uid}">{html.escape(name)}</a>'
                for uid, name in chunk
            )
            await context.bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True
            )
            if i + 5 < len(members):
                await asyncio.sleep(1.5)

        await update.effective_message.reply_text(
            "TagAll dihentikan." if stopped else "TagAll selesai."
        )
    except Exception:
        log.exception("TagAll error")
        await update.effective_message.reply_text("Terjadi kesalahan saat mengirim mention.")
    finally:
        context.chat_data["tagall_running"] = False
        context.chat_data["tagall_stop"] = False


def main():
    if not TOKEN:
        raise SystemExit("BOT_TOKEN belum diisi di .env")

    with database():
        pass

    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("tagme", tagme))
    app.add_handler(CommandHandler("untagme", untagme))
    app.add_handler(CommandHandler("tagcount", tagcount))
    app.add_handler(CommandHandler("tagall", tagall))
    app.add_handler(CommandHandler("tagstop", tagstop))

    log.info("Auto TagAll Bot aktif.")
    app.run_polling()


if __name__ == "__main__":
    main()
