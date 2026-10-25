import os
import asyncio
import logging
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)

# --- ASOSIY SOZLAMALAR ---
BOT_TOKEN = "8318167396:AAFwWj6MyQW-_sBSRtC3czw2D5w2lcbp3Mk"
MAIN_ADMIN_ID = 6505655178
CHANNEL_USERNAME = "@FORTIS_OKTO"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Baza (xotirada saqlanadi)
ADMINS = [MAIN_ADMIN_ID]
CHANNELS = [CHANNEL_USERNAME]
USERS = set()

# Namuna uchun kinolar bazasi
MOVIES = {
    "101": {
        "title": "Qasoskorlar: Intiho",
        "video_id": None
    }
}

# --- ADMIN HOLATLARI ---
class AddMovie(StatesGroup):
    waiting_for_name = State()
    waiting_for_code = State()
    waiting_for_video = State()

# --- MENYULAR ---
def get_user_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔎 Kino izlash"), KeyboardButton(text="📊 Statistika")]
        ],
        resize_keyboard=True
    )

def get_admin_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Kino qo'shish"), KeyboardButton(text="🗑 Kino o'chirish")],
            [KeyboardButton(text="📊 Statistika"), KeyboardButton(text="🚪 Chiqish")]
        ],
        resize_keyboard=True
    )

cancel_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="❌ Bekor qilish")]],
    resize_keyboard=True
)

# --- MAJBURIY OBUNA TEKSHIRUVI ---
async def check_subscription(user_id: int) -> bool:
    if user_id in ADMINS:
        return True
    for ch in CHANNELS:
        try:
            member = await bot.get_chat_member(chat_id=ch, user_id=user_id)
            if member.status not in ["creator", "administrator", "member"]:
                return False
        except Exception as e:
            logging.error(f"Kanalni tekshirishda xatolik: {e}")
            return False
    return True

def get_sub_keyboard():
    clean_name = CHANNEL_USERNAME.replace("@", "")
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📢 Kanalga a'zo bo'lish", url=f"https://t.me/{clean_name}")],
            [InlineKeyboardButton(text="🔄 Tekshirish", callback_data="check_sub")]
        ]
    )

# --- START BUYRUG'I ---
@dp.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    USERS.add(user_id)

    is_subscribed = await check_subscription(user_id)
    if not is_subscribed:
        await message.answer(
            f"👋 Assalomu alaykum, <b>{message.from_user.first_name}</b>!\n\n"
            "⚠️ <b>Botdan to'liq foydalanish va kinolarni olish uchun homiy kanalimizga obuna bo'ling!</b>\n\n"
            "<i>Obuna bo'lgach, «🔄 Tekshirish» tugmasini bosing:</i>",
            reply_markup=get_sub_keyboard(),
            parse_mode="HTML"
        )
        return

    await message.answer(
        f"👋 Assalomu alaykum, <b>{message.from_user.first_name}</b>!\n\n"
        "🎬 <b>Kino botimizga xush kelibsiz!</b>\n\n"
        "🍿 Kinoni olish uchun uning <b>kodini yuboring</b> (Masalan: <code>101</code>):",
        reply_markup=get_user_kb(),
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "check_sub")
async def callback_check_sub(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    is_subscribed = await check_subscription(user_id)
    
    if not is_subscribed:
        await callback.answer("❌ Hali kanalga a'zo bo'lmadingiz!", show_alert=True)
    else:
        await callback.answer("✅ Rahmat, a'zolik tasdiqlandi!")
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.message.answer(
            "🎉 <b>A'zolik tasdiqlandi!</b>\n\nMarhamat, kino kodini yuboring:",
            reply_markup=get_user_kb(),
            parse_mode="HTML"
        )

# --- TUGMALAR VA BEKOR QILISH ---
@dp.message(F.text == "❌ Bekor qilish")
async def cancel_handler(message: types.Message, state: FSMContext):
    await state.clear()
    if message.from_user.id in ADMINS:
        await message.answer("Bekor qilindi.", reply_markup=get_admin_kb())
    else:
        await message.answer("Bekor qilindi.", reply_markup=get_user_kb())

@dp.message(F.text == "🚪 Chiqish")
async def exit_admin(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Foydalanuvchi menyusi:", reply_markup=get_user_kb())

@dp.message(F.text == "🔎 Kino izlash")
async def search_hint(message: types.Message):
    await message.answer("🍿 Kinoni tomosha qilish uchun uning kodini yuboring (Masalan: <code>101</code>):", parse_mode="HTML")

@dp.message(F.text == "📊 Statistika")
async def show_stats(message: types.Message):
    await message.answer(
        f"📊 <b>Bot statistikasi:</b>\n\n"
        f"👥 Foydalanuvchilar: <b>{len(USERS)}</b> ta\n"
        f"🎬 Kinolar soni: <b>{len(MOVIES)}</b> ta",
        parse_mode="HTML"
    )

# --- ADMIN PANEL ---
@dp.message(Command("admin"))
async def cmd_admin(message: types.Message, state: FSMContext):
    await state.clear()
    if message.from_user.id not in ADMINS:
        return
    await message.answer("👨‍💼 <b>Admin paneliga xush kelibsiz!</b>", reply_markup=get_admin_kb(), parse_mode="HTML")

@dp.message(F.text == "➕ Kino qo'shish")
async def start_add_movie(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMINS:
        return
    await message.answer("Kino nomini kiriting:", reply_markup=cancel_kb)
    await state.set_state(AddMovie.waiting_for_name)

@dp.message(AddMovie.waiting_for_name)
async def add_movie_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await message.answer("Kino uchun raqamli kod kiriting (Masalan: <code>105</code>):", parse_mode="HTML")
    await state.set_state(AddMovie.waiting_for_code)

@dp.message(AddMovie.waiting_for_code)
async def add_movie_code(message: types.Message, state: FSMContext):
    code = message.text.strip()
    if code in MOVIES:
        await message.answer("❌ Bu kod bazada mavjud! Boshqa kod kiriting:")
        return
    await state.update_data(code=code)
    await message.answer("Kinoning video faylini yuboring:")
    await state.set_state(AddMovie.waiting_for_video)

@dp.message(AddMovie.waiting_for_video)
async def add_movie_video(message: types.Message, state: FSMContext):
    if not message.video:
        await message.answer("Iltimos, faqat video fayl yuboring:")
        return
    data = await state.get_data()
    code = data["code"]
    
    MOVIES[code] = {
        "title": data["name"],
        "video_id": message.video.file_id
    }
    
    await message.answer(
        f"✅ <b>Kino saqlandi!</b>\n\n🎬 Nomi: {data['name']}\n🔢 Kodi: <code>{code}</code>",
        reply_markup=get_admin_kb(),
        parse_mode="HTML"
    )
    await state.clear()

@dp.message(F.text == "🗑 Kino o'chirish")
async def del_movie_start(message: types.Message):
    if message.from_user.id not in ADMINS:
        return
    await message.answer("O'chirmoqchi bo'lgan kino kodini yuboring:")

# --- KOD ORQALI KINO BERISH ---
@dp.message(F.text.regexp(r'^\d+$'))
async def send_movie_by_code(message: types.Message):
    user_id = message.from_user.id
    USERS.add(user_id)

    is_subscribed = await check_subscription(user_id)
    if not is_subscribed:
        await message.answer(
            "⚠️ <b>Kinoni ko'rish uchun oldin homiy kanalimizga obuna bo'ling!</b>",
            reply_markup=get_sub_keyboard(),
            parse_mode="HTML"
        )
        return

    code = message.text.strip()
    if code in MOVIES:
        movie = MOVIES[code]
        caption = (
            f"🎬 <b>{movie['title']}</b>\n\n"
            f"🔢 Kino kodi: <code>{code}</code>\n"
            f"📢 Kanal: {CHANNEL_USERNAME}"
        )
        if movie.get("video_id"):
            await message.answer_video(video=movie["video_id"], caption=caption, parse_mode="HTML")
        else:
            await message.answer(caption, parse_mode="HTML")
    else:
        await message.answer(f"❌ <b>{code}</b> kodli kino bazadan topilmadi.")

# --- RENDER VEB-SERVERI VA ISHGA TUSHIRISH ---
async def handle_ping(request):
    return web.Response(text="Bot ishlayapti!")

async def main():
    app = web.Application()
    app.router.add_get("/", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
    
