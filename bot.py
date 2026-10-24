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

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Baza sozlamalari
ADMINS = [MAIN_ADMIN_ID]
CHANNELS = ["@FORTIS_OKTO"]

MOVIES = {
    "101": {
        "title": "Qasoskorlar: Intiho",
        "description": "Koinotni qutqarish uchun so'nggi kurash.",
        "year": "2019",
        "country": "AQSH",
        "genre": "Fantastika, Jangari",
        "video_file_id": None
    }
}

USERS_DB = {}

# --- HOLATLAR (FSM) ---
class MovieAddStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_desc = State()
    waiting_for_year = State()
    waiting_for_country = State()
    waiting_for_genre = State()
    waiting_for_code = State()
    waiting_for_video = State()

class AdminActions(StatesGroup):
    waiting_for_broadcast = State()
    waiting_for_add_channel = State()
    waiting_for_del_channel = State()
    waiting_for_del_movie = State()
    waiting_for_add_admin = State()

# --- MENYULAR ---
def get_user_main_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎬 Kino izlash")],
            [KeyboardButton(text="🔥 Top kinolar"), KeyboardButton(text="ℹ️ Bot haqida")]
        ],
        resize_keyboard=True
    )

def get_admin_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Kino qo'shish"), KeyboardButton(text="🗑 Kino o'chirish")],
            [KeyboardButton(text="📢 Kanallar"), KeyboardButton(text="✉️ Xabar yuborish")],
            [KeyboardButton(text="📊 Statistika"), KeyboardButton(text="👥 Adminlar")],
            [KeyboardButton(text="🚪 Foydalanuvchi menyusi")]
        ],
        resize_keyboard=True
    )

cancel_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="❌ Bekor qilish")]],
    resize_keyboard=True
)

# --- MAJBURIY OBUNA TEKSHIRUVI ---
async def check_channel_membership(user_id: int):
    unsubscribed = []
    for ch in CHANNELS:
        try:
            member = await bot.get_chat_member(chat_id=ch, user_id=user_id)
            if member.status in ["left", "kicked"]:
                unsubscribed.append(ch)
        except Exception:
            unsubscribed.append(ch)
    return unsubscribed

def get_sub_keyboard(unsubscribed_channels):
    buttons = []
    for i, ch in enumerate(unsubscribed_channels, 1):
        clean_ch = ch.replace("@", "")
        buttons.append([InlineKeyboardButton(text=f"📢 {i}-kanalga a'zo bo'lish", url=f"https://t.me/{clean_ch}")])
    buttons.append([InlineKeyboardButton(text="✅ TEKSHIRISH", callback_data="check_subscription")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# --- START BUYRUG'I ---
@dp.message(CommandStart())
async def start_handler(message: types.Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    if user_id not in USERS_DB:
        USERS_DB[user_id] = {
            "first_name": message.from_user.first_name,
            "username": message.from_user.username
        }

    # Obunani tekshirish
    unsub = await check_channel_membership(user_id)
    if unsub and user_id not in ADMINS:
        text = (
            f"👋 Assalomu alaykum, <b>{message.from_user.first_name}</b>!\n\n"
            "⚠️ <b>Botdan foydalanish uchun quyidagi homiy kanallarga obuna bo'lishingiz majburiy!</b>\n\n"
            "<i>Kanallarga a'zo bo'lib, pastdagi «✅ TEKSHIRISH» tugmasini bosing:</i>"
        )
        await message.answer(text, reply_markup=get_sub_keyboard(unsub), parse_mode="HTML")
        return

    text = (
        f"👋 Assalomu alaykum, <b>{message.from_user.first_name}</b>!\n\n"
        "🎬 <b>Kino Olami</b> botiga xush kelibsiz!\n"
        "🍿 Tomosha qilish uchun kino kodini yuboring (masalan: <code>101</code>):"
    )
    await message.answer(text, reply_markup=get_user_main_kb(), parse_mode="HTML")

# --- TEKSHIRISH TUGMASI (CALLBACK) ---
@dp.callback_query(F.data == "check_subscription")
async def verify_sub(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    unsub = await check_channel_membership(user_id)
    if unsub:
        await callback.answer("❌ Hali hamma kanallarga a'zo bo'lmadingiz! Iltimos, a'zo bo'ling.", show_alert=True)
        await callback.message.edit_reply_markup(reply_markup=get_sub_keyboard(unsub))
    else:
        await callback.answer("✅ Rahmat, a'zolik tasdiqlandi!")
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.message.answer(
            "🎉 <b>A'zolik tasdiqlandi!</b>\n\nMarhamat, kino kodini yuboring:",
            reply_markup=get_user_main_kb(),
            parse_mode="HTML"
        )

# --- BEKOR QILISH ---
@dp.message(F.text == "❌ Bekor qilish")
async def cancel_action(message: types.Message, state: FSMContext):
    await state.clear()
    if message.from_user.id in ADMINS:
        await message.answer("Amal bekor qilindi.", reply_markup=get_admin_kb())
    else:
        await message.answer("Amal bekor qilindi.", reply_markup=get_user_main_kb())

# --- ADMIN PANEL ---
@dp.message(Command("admin"))
async def admin_panel(message: types.Message, state: FSMContext):
    await state.clear()
    if message.from_user.id not in ADMINS:
        return
    await message.answer("👨‍💼 <b>Admin paneliga xush kelibsiz!</b>", reply_markup=get_admin_kb(), parse_mode="HTML")

@dp.message(F.text == "🚪 Foydalanuvchi menyusi")
async def back_user_kb(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Foydalanuvchi menyusi:", reply_markup=get_user_main_kb())

@dp.message(F.text == "📊 Statistika")
async def show_stats(message: types.Message):
    if message.from_user.id not in ADMINS:
        return
    text = (
        "📊 <b>Bot Statistikasi:</b>\n\n"
        f"👥 Foydalanuvchilar: <b>{len(USERS_DB)}</b> ta\n"
        f"🎬 Kinolar soni: <b>{len(MOVIES)}</b> ta\n"
        f"📢 Ulanish kanallari: <b>{len(CHANNELS)}</b> ta\n"
        f"👤 Adminlar soni: <b>{len(ADMINS)}</b> ta"
    )
    await message.answer(text, parse_mode="HTML")

# --- KINO QO'SHISH BOSQICHLARI ---
@dp.message(F.text == "➕ Kino qo'shish")
async def start_add_movie(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMINS:
        return
    await message.answer("🎬 <b>Film nomini kiriting:</b>", reply_markup=cancel_kb, parse_mode="HTML")
    await state.set_state(MovieAddStates.waiting_for_name)

@dp.message(MovieAddStates.waiting_for_name)
async def process_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await message.answer("📝 <b>Film tavsifini kiriting:</b>", parse_mode="HTML")
    await state.set_state(MovieAddStates.waiting_for_desc)

@dp.message(MovieAddStates.waiting_for_desc)
async def process_desc(message: types.Message, state: FSMContext):
    await state.update_data(description=message.text.strip())
    await message.answer("📅 <b>Chiqarilgan yilini kiriting (masalan: 2024):</b>", parse_mode="HTML")
    await state.set_state(MovieAddStates.waiting_for_year)

@dp.message(MovieAddStates.waiting_for_year)
async def process_year(message: types.Message, state: FSMContext):
    await state.update_data(year=message.text.strip())
    await message.answer("🌍 <b>Davlatini kiriting:</b>", parse_mode="HTML")
    await state.set_state(MovieAddStates.waiting_for_country)

@dp.message(MovieAddStates.waiting_for_country)
async def process_country(message: types.Message, state: FSMContext):
    await state.update_data(country=message.text.strip())
    await message.answer("🎭 <b>Janrini kiriting:</b>", parse_mode="HTML")
    await state.set_state(MovieAddStates.waiting_for_genre)

@dp.message(MovieAddStates.waiting_for_genre)
async def process_genre(message: types.Message, state: FSMContext):
    await state.update_data(genre=message.text.strip())
    await message.answer("🔢 <b>Kino uchun raqamli kod kiriting (masalan: 105):</b>", parse_mode="HTML")
    await state.set_state(MovieAddStates.waiting_for_code)

@dp.message(MovieAddStates.waiting_for_code)
async def process_code(message: types.Message, state: FSMContext):
    code = message.text.strip()
    if code in MOVIES:
        await message.answer("❌ Bu kodli kino mavjud! Boshqa kod kiriting:")
        return
    await state.update_data(code=code)
    await message.answer("🎥 <b>Kinoning video faylini yuboring:</b>\n<i>(Video bo'lmasa, 'yoq' deb yozing)</i>", parse_mode="HTML")
    await state.set_state(MovieAddStates.waiting_for_video)

@dp.message(MovieAddStates.waiting_for_video)
async def process_video(message: types.Message, state: FSMContext):
    data = await state.get_data()
    v_id = message.video.file_id if message.video else None

    MOVIES[data["code"]] = {
        "title": data["name"],
        "description": data["description"],
        "year": data["year"],
        "country": data["country"],
        "genre": data["genre"],
        "video_file_id": v_id
    }

    await message.answer(
        f"✅ <b>Kino muvaffaqiyatli saqlandi!</b>\n\n"
        f"🎬 <b>Nom:</b> {data['name']}\n"
        f"🔢 <b>Kodi:</b> <code>{data['code']}</code>",
        reply_markup=get_admin_kb(),
        parse_mode="HTML"
    )
    await state.clear()

# --- KINO O'CHIRISH ---
@dp.message(F.text == "🗑 Kino o'chirish")
async def delete_movie_start(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMINS:
        return
    await message.answer("O'chirmoqchi bo'lgan kino kodini kiriting:", reply_markup=cancel_kb)
    await state.set_state(AdminActions.waiting_for_del_movie)

@dp.message(AdminActions.waiting_for_del_movie)
async def delete_movie_finish(message: types.Message, state: FSMContext):
    code = message.text.strip()
    if code in MOVIES:
        del MOVIES[code]
        await message.answer(f"✅ {code} kodli kino o'chirildi!", reply_markup=get_admin_kb())
    else:
        await message.answer("❌ Bunday kodli kino topilmadi.", reply_markup=get_admin_kb())
    await state.clear()

# --- KANALLAR BOSHQARUVI ---
@dp.message(F.text == "📢 Kanallar")
async def show_channels(message: types.Message):
    if message.from_user.id not in ADMINS:
        return
    ch_list = "\n".join([f"• {c}" for c in CHANNELS]) if CHANNELS else "Kanallar yo'q."
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ Kanal qo'shish", callback_data="add_ch")],
            [InlineKeyboardButton(text="🗑 Kanal o'chirish", callback_data="del_ch")]
        ]
    )
    await message.answer(f"📢 <b>Majburiy kanallar ro'yxati:</b>\n\n{ch_list}", reply_markup=kb, parse_mode="HTML")

@dp.callback_query(F.data == "add_ch")
async def call_add_ch(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Kanal usernamesini @ belgisi bilan yuboring (Masalan: @kanal):", reply_markup=cancel_kb)
    await state.set_state(AdminActions.waiting_for_add_channel)
    await callback.answer()

@dp.message(AdminActions.waiting_for_add_channel)
async def process_add_ch(message: types.Message, state: FSMContext):
    ch = message.text.strip()
    if ch.startswith("@") and ch not in CHANNELS:
        CHANNELS.append(ch)
        await message
        
