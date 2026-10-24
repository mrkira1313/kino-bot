"""
Kino bot (Telegram) - aiogram 3.x + SQLite

O'rnatish:
    pip install aiogram

Ishga tushirish:
    export BOT_TOKEN="123456:ABC..."
    python bot.py
"""
import asyncio
import logging
import os
import sqlite3

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

# ====== SOZLAMALAR ======
BOT_TOKEN = os.getenv("BOT_TOKEN", "BOT_TOKENNI_SHU_YERGA_QOYING")
ADMIN_IDS = {123456789}          # o'zingizning Telegram ID raqamingiz (@userinfobot dan oling)
CHANNELS = []                    # majburiy obuna kanallari, masalan: ["@kanal_username"]
DB_PATH = "kino.db"
# ========================

logging.basicConfig(level=logging.INFO)
dp = Dispatcher()


# ---------- Ma'lumotlar bazasi ----------
def db():
    return sqlite3.connect(DB_PATH)


def init_db():
    with db() as con:
        con.execute(
            """CREATE TABLE IF NOT EXISTS movies (
                code TEXT PRIMARY KEY,
                file_id TEXT NOT NULL,
                file_type TEXT NOT NULL,
                title TEXT NOT NULL,
                views INTEGER DEFAULT 0
            )"""
        )
        con.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY)")
        con.execute("CREATE TABLE IF NOT EXISTS channels (username TEXT PRIMARY KEY)")
        for ch in CHANNELS:
            con.execute("INSERT OR IGNORE INTO channels (username) VALUES (?)", (ch,))


def get_channels() -> list[str]:
    with db() as con:
        return [r[0] for r in con.execute("SELECT username FROM channels")]


def add_user(user_id: int):
    with db() as con:
        con.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))


def get_movie(code: str):
    with db() as con:
        return con.execute(
            "SELECT file_id, file_type, title FROM movies WHERE code = ?", (code,)
        ).fetchone()


# ---------- Majburiy obuna ----------
async def not_subscribed(bot: Bot, user_id: int) -> list[str]:
    missing = []
    if user_id in ADMIN_IDS:
        return missing
    for ch in get_channels():
        try:
            member = await bot.get_chat_member(ch, user_id)
            if member.status in ("left", "kicked"):
                missing.append(ch)
        except Exception:
            # bot kanalda admin emas yoki kanal topilmadi - o'tkazib yuboramiz
            logging.warning("Kanal tekshirib bo'lmadi: %s", ch)
    return missing


def sub_keyboard(channels: list[str]) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=f"📢 {ch}", url=f"https://t.me/{ch.lstrip('@')}")]
        for ch in channels
    ]
    rows.append([InlineKeyboardButton(text="✅ Tekshirish", callback_data="check_sub")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ---------- Foydalanuvchi buyruqlari ----------
@dp.message(CommandStart())
async def start(message: Message, bot: Bot):
    add_user(message.from_user.id)
    missing = await not_subscribed(bot, message.from_user.id)
    if missing:
        await message.answer(
            "Botdan foydalanish uchun kanallarga obuna bo'ling:",
            reply_markup=sub_keyboard(missing),
        )
        return
    await message.answer(
        f"Salom, {message.from_user.first_name}! 🎬\n"
        "Kino kodini yuboring, men kinoni topib beraman."
    )


@dp.callback_query(F.data == "check_sub")
async def check_sub(call: CallbackQuery, bot: Bot):
    missing = await not_subscribed(bot, call.from_user.id)
    if missing:
        await call.answer("Hali hamma kanalga obuna bo'lmadingiz!", show_alert=True)
        return
    await call.message.edit_text("✅ Rahmat! Endi kino kodini yuboring.")


# ---------- Admin buyruqlari ----------
def is_admin(message: Message) -> bool:
    return message.from_user.id in ADMIN_IDS


@dp.message(Command("stats"), F.func(is_admin))
async def stats(message: Message):
    with db() as con:
        users = con.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        movies = con.execute("SELECT COUNT(*) FROM movies").fetchone()[0]
    await message.answer(f"👤 Foydalanuvchilar: {users}\n🎞 Kinolar: {movies}")


@dp.message(Command("list"), F.func(is_admin))
async def list_movies(message: Message):
    with db() as con:
        rows = con.execute(
            "SELECT code, title, views FROM movies ORDER BY rowid DESC LIMIT 50"
        ).fetchall()
    if not rows:
        await message.answer("Hozircha kino yo'q.")
        return
    await message.answer("\n".join(f"{c} — {t} ({v} ko'rish)" for c, t, v in rows))


@dp.message(Command("del"), F.func(is_admin))
async def delete_movie(message: Message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Foydalanish: /del KOD")
        return
    with db() as con:
        cur = con.execute("DELETE FROM movies WHERE code = ?", (parts[1].strip(),))
    await message.answer("🗑 O'chirildi." if cur.rowcount else "Bunday kod topilmadi.")


@dp.message(Command("send"), F.func(is_admin))
async def broadcast(message: Message, bot: Bot):
    """/send Xabar matni  — barcha foydalanuvchilarga yuboradi"""
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Foydalanish: /send xabar matni")
        return
    with db() as con:
        ids = [r[0] for r in con.execute("SELECT user_id FROM users")]
    ok = 0
    for uid in ids:
        try:
            await bot.send_message(uid, parts[1])
            ok += 1
        except Exception:
            pass
        await asyncio.sleep(0.05)
    await message.answer(f"✅ {ok}/{len(ids)} ta foydalanuvchiga yuborildi.")


@dp.message(Command("addchannel"), F.func(is_admin))
async def add_channel(message: Message, bot: Bot):
    """/addchannel @kanal_username"""
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip().startswith("@"):
        await message.answer("Foydalanish: /addchannel @kanal_username")
        return
    ch = parts[1].strip()
    try:
        me = await bot.get_me()
        member = await bot.get_chat_member(ch, me.id)
        if member.status not in ("administrator", "creator"):
            raise ValueError("bot admin emas")
    except Exception:
        await message.answer(
            "❌ Kanal topilmadi yoki bot u yerda admin emas.\n"
            "Avval botni kanalga admin qilib qo'shing."
        )
        return
    with db() as con:
        con.execute("INSERT OR IGNORE INTO channels (username) VALUES (?)", (ch,))
    await message.answer(f"✅ Majburiy obunaga qo'shildi: {ch}")


@dp.message(Command("delchannel"), F.func(is_admin))
async def del_channel(message: Message):
    """/delchannel @kanal_username"""
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Foydalanish: /delchannel @kanal_username")
        return
    with db() as con:
        cur = con.execute("DELETE FROM channels WHERE username = ?", (parts[1].strip(),))
    await message.answer("🗑 O'chirildi." if cur.rowcount else "Bunday kanal ro'yxatda yo'q.")


@dp.message(Command("channels"), F.func(is_admin))
async def show_channels(message: Message):
    chs = get_channels()
    await message.answer("\n".join(chs) if chs else "Majburiy kanallar yo'q.")


@dp.message(F.func(is_admin), F.video | F.document)
async def add_movie(message: Message):
    """Admin video yuboradi, izohga:  KOD | Kino nomi  deb yozadi."""
    caption = (message.caption or "").strip()
    if "|" not in caption:
        await message.answer(
            "Kino qo'shish uchun videoni izoh bilan yuboring:\n"
            "`KOD | Kino nomi`\nMasalan: `101 | Qasoskorlar`",
            parse_mode="Markdown",
        )
        return
    code, title = [x.strip() for x in caption.split("|", 1)]
    if message.video:
        file_id, ftype = message.video.file_id, "video"
    else:
        file_id, ftype = message.document.file_id, "document"
    with db() as con:
        con.execute(
            "INSERT OR REPLACE INTO movies (code, file_id, file_type, title) VALUES (?,?,?,?)",
            (code, file_id, ftype, title),
        )
    await message.answer(f"✅ Saqlandi: {code} — {title}")


# ---------- Kino qidirish (kod bo'yicha) ----------
@dp.message(F.text & ~F.text.startswith("/"))
async def find_movie(message: Message, bot: Bot):
    add_user(message.from_user.id)
    missing = await not_subscribed(bot, message.from_user.id)
    if missing:
        await message.answer(
            "Avval kanallarga obuna bo'ling:", reply_markup=sub_keyboard(missing)
        )
        return

    code = message.text.strip()
    movie = get_movie(code)
    if not movie:
        await message.answer("❌ Bunday kodli kino topilmadi.")
        return

    file_id, ftype, title = movie
    caption = f"🎬 {title}"
    if ftype == "video":
        await message.answer_video(file_id, caption=caption)
    else:
        await message.answer_document(file_id, caption=caption)
    with db() as con:
        con.execute("UPDATE movies SET views = views + 1 WHERE code = ?", (code,))


async def main():
    init_db()
    bot = Bot(BOT_TOKEN)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
    
