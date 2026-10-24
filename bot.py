import os
import json
import asyncio
import logging
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    InlineQueryResultVideo, InlineQueryResultArticle, InputTextMessageContent
)

# --- ASOSIY SOZLAMALAR ---
BOT_TOKEN = "8318167396:AAFwWj6MyQW-_sBSRtC3czw2D5w2lcbp3Mk"
MAIN_ADMIN_ID = 6505655178
DEFAULT_CHANNEL = "@FORTIS_OKTO"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# --- BAZA SOZLAMALARI ---
ADMINS = [MAIN_ADMIN_ID]
CHANNELS = [DEFAULT_CHANNEL]
USERS = {}        # {user_id: {"username": str, "first_name": str}}
SAVED_MOVIES = {} # {user_id: set(movie_codes)}
BOT_ACTIVE = True

# Kinolar bazasi
MOVIES = {
    "1001": {
        "name_uz": "Qasoskorlar: Intiho",
        "description": "Koinotni qutqarish uchun qahramonlarning so'nggi kurashi.",
        "year": 2019,
        "country": "AQSH",
        "language": "O'zbekcha",
        "genre": "Fantastika",
        "rating": 8.4,
        "views": 0,
        "video_file_id": None,
        "poster_file_id": None
    }
}

# --- ADMIN HOLATLARI (FSM) ---
class AdminStates(StatesGroup):
    add_name = State()
    add_desc = State()
    add_year = State()
    add_country = State()
    add_lang = State()
    add_genre = State()
    add_code = State()
    add_video = State()
    add_poster = State()
    broadcast_msg = State()
    add_channel = State()
    add_admin = State()
    delete_movie = State()

# --- MAJBURIY OBUNANI TEKSHIRISH ---
async def check_channel_membership(user_id: int):
    unsubscribed = []
    for ch in CHANNELS:
        try:
            member = await bot.get_chat_member(chat_id=ch, user_id=user_id)
            if member.status not in ["creator", "administrator", "member"]:
                unsubscribed.append(ch)
        except Exception as e:
            logging.error(f"Kanal tekshirishda xatolik ({ch}): {e}")
            unsubscribed.append(ch)
    return unsubscribed

def get_sub_keyboard(unsubscribed_channels):
    buttons = []
    for i, ch in enumerate(unsubscribed_channels, 1):
        clean_name = ch.replace("@", "")
        buttons.append([InlineKeyboardButton(text=f"📢 {i}-kanalga a'zo bo'lish", url=f"https://t.me/{clean_name}")])
    buttons.append([InlineKeyboardButton(text="✔️ Tekshirish", callback_data="check_subscription")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# --- MENYULAR ---
def get_main_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔥 Top Filmlar", switch_inline_query_current_chat="top")],
            [InlineKeyboardButton(text="💾 Saqlangan Filmlar", switch_inline_query_current_chat="saved")],
            [InlineKeyboardButton(text="🔍 Film Qidirish", switch_inline_query_current_chat="")],
            [InlineKeyboardButton(text="🎬 Filter", callback_data="filter_main")]
        ]
    )

def get_admin_keyboard():
    status_text = "✅ Faol" if BOT_ACTIVE else "❌ O'chiq"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ Kino Qo'shish", callback_data="admin_add_movie")],
            [InlineKeyboardButton(text="🗑 Kino O'chirish", callback_data="admin_delete_movie")],
            [InlineKeyboardButton(text="📊 Statistika", callback_data="admin_stats")],
            [InlineKeyboardButton(text="📢 Xabar Yuborish", callback_data="admin_broadcast")],
            [InlineKeyboardButton(text="📱 Kanallar", callback_data="admin_channels")],
            [InlineKeyboardButton(text="👥 Adminlar", callback_data="admin_manage_admins")],
            [InlineKeyboardButton(text=f"⚙️ Bot Holati: {status_text}", callback_data="admin_toggle_bot")],
            [InlineKeyboardButton(text="🔙 Asosiy Menu", callback_data="main_menu")]
        ]
    )

def get_movie_keyboard(code: str, user_id: int):
    is_saved = code in SAVED_MOVIES.get(user_id, set())
    save_text = "❌ Saqlanganlardan O'chirish" if is_saved else "💾 Saqlash"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📤 Ulashish", switch_inline_query=code)],
            [InlineKeyboardButton(text=save_text, callback_data=f"save_{code}")],
            [
                InlineKeyboardButton(text="🔍 Qidirish", switch_inline_query_current_chat=""),
                InlineKeyboardButton(text="🔙 Asosiy Menu", callback_data="main_menu")
            ]
        ]
    )

# --- START BUYRUG'I ---
@dp.message(CommandStart())
async def handle_start(message: types.Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    USERS[user_id] = {
        "username": message.from_user.username or "",
        "first_name": message.from_user.first_name or ""
    }

    if not BOT_ACTIVE and user_id not in ADMINS:
        await message.answer("❌ Botda hozirda texnik ishlar olib borilmoqda. Keyinroq urinib ko'ring.")
        return

    unsub = await check_channel_membership(user_id)
    if unsub and user_id not in ADMINS:
        await message.answer(
            f"👋 Assalomu alaykum, <b>{message.from_user.first_name}</b>!\n\n"
            "❗️ <b>Botdan to'liq foydalanish uchun quyidagi kanallarga a'zo bo'lishingiz kerak:</b>",
            reply_markup=get_sub_keyboard(unsub),
            parse_mode="HTML"
        )
        return

    # /start 1001 ko'rinishida havola orqali ochilganda
    args = message.text.split()
    if len(args) > 1:
        code = args[1].strip()
        if code in MOVIES:
            await send_movie(message.chat.id, code, user_id)
            return

    await message.answer(
        f"👋 Assalomu alaykum, <b>{message.from_user.first_name}</b>!\n\n"
        "🎬 <b>Kino botga xush kelibsiz!</b>\n\nQuyidagi tugmalardan foydalaning:",
        reply_markup=get_main_keyboard(),
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "check_subscription")
async def process_sub_check(callback: types.CallbackQuery):
    unsub = await check_channel_membership(callback.from_user.id)
    if unsub:
        await callback.answer("❌ Siz hali barcha kanallarga obuna bo'lmadingiz!", show_alert=True)
        try:
            await callback.message.edit_reply_markup(reply_markup=get_sub_keyboard(unsub))
        except Exception:
            pass
    else:
        await callback.answer("✅ Obuna tasdiqlandi!")
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.message.answer(
            "👋 Assalomu alaykum!\n\n🎬 <b>Kino botga xush kelibsiz!</b>\n\nQuyidagi tugmalardan foydalaning:",
            reply_markup=get_main_keyboard(),
            parse_mode="HTML"
        )

# --- ADMIN PANEL ---
@dp.message(Command("admin"))
async def handle_admin(message: types.Message, state: FSMContext):
    await state.clear()
    if message.from_user.id not in ADMINS:
        return
    await message.answer("👨‍💼 <b>Admin Panel</b>\n\nKerakli bo'limni tanlang:", reply_markup=get_admin_keyboard(), parse_mode="HTML")

@dp.callback_query(F.data == "admin_panel")
async def back_to_admin(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    if callback.from_user.id not in ADMINS:
        return
    await callback.message.edit_text("👨‍💼 <b>Admin Panel</b>\n\nKerakli bo'limni tanlang:", reply_markup=get_admin_keyboard(), parse_mode="HTML")
    await callback.answer()

@dp.callback_query(F.data == "main_menu")
async def back_to_main(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer("🏠 <b>Asosiy Menu</b>\n\nKerakli bo'limni tanlang:", reply_markup=get_main_keyboard(), parse_mode="HTML")
    await callback.answer()

@dp.callback_query(F.data == "admin_toggle_bot")
async def toggle_bot_active(callback: types.CallbackQuery):
    global BOT_ACTIVE
    if callback.from_user.id not in ADMINS:
        return
    BOT_ACTIVE = not BOT_ACTIVE
    status = "yoqildi" if BOT_ACTIVE else "o'chirildi"
    await callback.answer(f"Bot holati o'zgartirildi: {status}")
    await callback.message.edit_reply_markup(reply_markup=get_admin_keyboard())

# --- KINO QO'SHISH BOSQICHLARI ---
@dp.callback_query(F.data == "admin_add_movie")
async def add_movie_start(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMINS:
        return
    await callback.message.answer("🎬 <b>Kino qo'shish</b>\n\n📝 Film nomini kiriting:", parse_mode="HTML")
    await state.set_state(AdminStates.add_name)
    await callback.answer()

@dp.message(AdminStates.add_name)
async def process_name(message: types.Message, state: FSMContext):
    await state.update_data(name_uz=message.text.strip())
    await message.answer("📝 Film tavsifini kiriting:")
    await state.set_state(AdminStates.add_desc)

@dp.message(AdminStates.add_desc)
async def process_desc(message: types.Message, state: FSMContext):
    await state.update_data(description=message.text.strip())
    await message.answer("📅 Chiqarilgan yilini kiriting (masalan: 2024):")
    await state.set_state(AdminStates.add_year)

@dp.message(AdminStates.add_year)
async def process_year(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("❌ Iltimos, to'g'ri yil kiriting:")
        return
    await state.update_data(year=int(message.text))
    await message.answer("🌍 Ishlab chiqarilgan davlatni kiriting:")
    await state.set_state(AdminStates.add_country)

@dp.message(AdminStates.add_country)
async def process_country(message: types.Message, state: FSMContext):
    await state.update_data(country=message.text.strip())
    await message.answer("🗣 Tilini kiriting (masalan: O'zbekcha):")
    await state.set_state(AdminStates.add_lang)

@dp.message(AdminStates.add_lang)
async def process_lang(message: types.Message, state: FSMContext):
    await state.update_data(language=message.text.strip())
    await message.answer("🎭 Janrini kiriting (masalan: Jangari):")
    await state.set_state(AdminStates.add_genre)

@dp.message(AdminStates.add_genre)
async def process_genre(message: types.Message, state: FSMContext):
    await state.update_data(genre=message.text.strip())
    await message.answer("🔢 Kino uchun noyob kod kiriting (masalan: <code>1002</code>):", parse_mode="HTML")
    await state.set_state(AdminStates.add_code)

@dp.message(AdminStates.add_code)
async def process_code(message: types.Message, state: FSMContext):
    code = message.text.strip()
    if code in MOVIES:
        await message.answer("❌ Bu kod allaqachon mavjud! Boshqa kod kiriting:")
        return
    await state.update_data(code=code)
    await message.answer("🎥 Kinoning video faylini yuboring:")
    await state.set_state(AdminStates.add_video)

@dp.message(AdminStates.add_video)
async def process_video(message: types.Message, state: FSMContext):
    if not message.video:
        await message.answer("❌ Iltimos, video fayl yuboring!")
        return
    await state.update_data(video_file_id=message.video.file_id)
    await message.answer("🖼 Poster rasmini yuboring (yoki rasmsiz bo'lsa 'yoq' deb yozing):")
    await state.set_state(AdminStates.add_poster)

@dp.message(AdminStates.add_poster)
async def process_poster(message: types.Message, state: FSMContext):
    poster_id = message.photo[-1].file_id if message.photo else None
    data = await state.get_data()
    code = data["code"]

    MOVIES[code] = {
        "name_uz": data["name_uz"],
        "description": data["description"],
        "year": data["year"],
        "country": data["country"],
        "language": data["language"],
        "genre": data["genre"],
        "rating": 8.0,
        "views": 0,
        "video_file_id": data["video_file_id"],
        "poster_file_id": poster_id
    }

    await message.answer(
        f"✅ <b>Kino muvaffaqiyatli qo'shildi!</b>\n\n"
        f"🎬 <b>Nom:</b> {data['name_uz']}\n"
        f"🔢 <b>Kod:</b> <code>{code}</code>",
        reply_markup=get_admin_keyboard(),
        parse_mode="HTML"
    )
    await state.clear()

# --- KINO O'CHIRISH ---
@dp.callback_query(F.data == "admin_delete_movie")
async def delete_movie_start(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMINS:
        return
    await callback.message.answer("🗑 O'chirmoqchi bo'lgan kino kodini kiriting:")
    await state.set_state(AdminStates.delete_movie)
    await callback.answer()

@dp.message(AdminStates.delete_movie)
async def delete_movie_finish(message: types.Message, state: FSMContext):
    code = message.text.strip()
    if code in MOVIES:
        name = MOVIES[code]["name_uz"]
        del MOVIES[code]
        await message.answer(f"✅ <b>{name}</b> kinosi o'chirildi!", reply_markup=get_admin_keyboard(), parse_mode="HTML")
    else:
        await message.answer("❌ Bunday kodli kino topilmadi.", reply_markup=get_admin_keyboard())
    await state.clear()

# --- STATISTIKA ---
@dp.callback_query(F.data == "admin_stats")
async def show_stats(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMINS:
        return
    total_users = len(USERS)
    total_movies = len(MOVIES)
    total_views = sum(m.get("views", 0) for m in MOVIES.values())
    text = (
        "📊 <b>Statistika</b>\n\n"
        f"👥 Jami foydalanuvchilar: <b>{total_users}</b>\n"
        f"🎬 Jami kinolar: <b>{total_movies}</b>\n"
        f"👀 Jami ko'rishlar: <b>{total_views}</b>\n"
        f"📢 Kanallar: <b>{len(CHANNELS)}</b>\n"
        f"👤 Adminlar: <b>{len(ADMINS)}</b>"
    )
    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[[InlineKeyboardButton(text="🔙 Orqaga", callback_data="admin_panel")]]]),
        parse_mode="HTML"
    )
    await callback.answer()

# --- KANALLAR BOSHQARUVI ---
@dp.callback_query(F.data == "admin_channels")
async def list_channels(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMINS:
        return
    ch_list = "\n".join([f"• <code>{c}</code>" for c in CHANNELS]) if CHANNELS else "Kanallar mavjud emas."
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ Kanal Qo'shish", callback_data="admin_add_ch")],
            [InlineKeyboardButton(text="🗑 Kanallarni O'chirish", callback_data="admin_clear_ch")],
            [InlineKeyboardButton(text="🔙 Orqaga", callback_data="admin_panel")]
        ]
    )
    await callback.message.edit_text(f"📱 <b>Majburiy kanallar ro'yxati:</b>\n\n{ch_list}", reply_markup=kb, parse_mode="HTML")
    await callback.answer()

@dp.callback_query(F.data == "admin_add_ch")
async def add_channel_start(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Kanal manzilini @ belgisi bilan yuboring (Masalan: @kanal):")
    await state.set_state(AdminStates.add_channel)
    await callback.answer()

@dp.message(AdminStates.add_channel)
async def add_channel_finish(message: types.Message, state: FSMContext):
    ch = message.text.strip()
    if ch.startswith("@") and ch not in CHANNELS:
        CHANNELS.append(ch)
        await message.answer(f"✅ {ch} kanali qo'shildi!", reply_markup=get_admin_keyboard())
    else:
        await message.answer("Xatolik yoki kanal allaqachon mavjud.", reply_markup=get_admin_keyboard())
    await state.clear()

@dp.callback_query(F.data == "admin_clear_ch")
async def clear_channels(callback: types.CallbackQuery):
    CHANNELS.clear()
    CHANNELS.append(DEFAULT_CHANNEL)
    await callback.message.answer("🗑 Kanallar tozalandi (asosiy kanal qoldi).", reply_markup=get_admin_keyboard())
    await callback.answer()

# --- ADMINLAR BOSHQARUVI ---
@dp.callback_query(F.data == "admin_manage_admins")
async def list_admins(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMINS:
        return
    adm_text = "\n".join([f"• <code>{a}</code>" + (" 👑" if a == MAIN_ADMIN_ID else "") for a in ADMINS])
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ Admin Qo'shish", callback_data="admin_add_admin")],
            [InlineKeyboardButton(text="🔙 Orqaga", callback_data="admin_panel")]
        ]
    )
    await callback.message.edit_text(f"👥 <b>Adminlar:</b>\n\n{adm_text}", reply_markup=kb, parse_mode="HTML")
    await callback.answer()

@dp.callback_query(F.data == "admin_add_admin")
async def add_admin_start(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Yangi adminning Telegram ID raqamini yuboring:")
    await state.set_state(AdminStates.add_admin)
    await callback.answer()

@dp.message(AdminStates.add_admin)
async def add_admin_finish(message: types.Message, state: FSMContext):
    if message.text.isdigit():
        new_id = int(message.text)
        if new_id not in ADMINS:
            ADMINS.append(new_id)
            await message.answer(f"✅ ID {new_id} admin qilindi!", reply_markup=get_admin_keyboard())
        else:
            await message.answer("Bu foydalanuvchi allaqachon admin.", reply_markup=get_admin_keyboard())
    else:
        await message.answer("Faqat raqam kiriting.", reply_markup=get_admin_keyboard())
    await state.clear()

# --- XABAR TARQATISH (BROADCAST) ---
@dp.callback_query(F.data == "admin_broadcast")
async def broadcast_start(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Barcha foydalanuvchilarga yuboriladigan xabarni yuboring:")
    await state.set_state(AdminStates.broadcast_msg)
    await callback.answer()

@dp.message(AdminStates.broadcast_msg)
async def broadcast_finish(message: types.Message, state: FSMContext):
    sent = 0
    await message.answer("Xabar tarqatish boshlandi...")
    for uid in list(USERS.keys()):
        try:
            await message.send_copy(chat_id=uid)
            sent += 1
            await asyncio.sleep(0.05)
        except Exception:
            pass
    await message.answer(f"✅ Xabar {sent} ta foydalanuvchiga yuborildi!", reply_markup=get_admin_keyboard())
    await state.clear()

# --- SAQLANGAN KINOLAR (FAVORITES) ---
@dp.callback_query(F.data.startswith("save_"))
async def toggle_save_movie(callback: types.CallbackQuery):
    code = callback.data.split("_")[1]
    user_id = callback.from_user.id
    if user_id not in SAVED_MOVIES:
        SAVED_MOVIES[user_id] = set()

    if code in SAVED_MOVIES[user_id]:
        SAVED_MOVIES[user_id].remove(code)
        await callback.answer("❌ Saqlanganlardan o'chirildi")
    else:
        SAVED_MOVIES[user_id].add(code)
        await callback.answer("✅ Saqlandi!")

    try:
        await callback.message.edit_reply_markup(reply_markup=get_movie_keyboard(code, user_id))
    except Exception:
        pass

# --- KINONI FOYDALANUVCHIGA YUBORISH ---
async def send_movie(chat_id: int, code: str, user_id: int):
    m = MOVIES[code]
    m["views"] = m.get("views", 0) + 1

    caption = (
        f"🎬 <b>{m['name_uz']}</b>\n\n"
        f"📝 {m['description']}\n\n"
        f"📅 Yil: {m['year']}\n"
        f"🌍 Davlat: {m['country']}\n"
        f"🗣 Til: {m['language']}\n"
        f"🎭 Janr: {m['genre']}\n"
        f"⭐️ Reyting: {m['rating']}/10\n"
        f"👀 Ko'rishlar: {m['views']}\n\n"
        f"🔢 Kod: <code>{code}</code>"
    )

    kb = get_movie_keyboard(code, user_id)
    if m.get("video_file_id"):
        await bot.send_video(chat_id=chat_id, video=m["video_file_id"], caption=caption, reply_markup=kb, parse_mode="HTML")
    elif m.get("poster_file_id"):
        await bot.send_photo(chat_id=chat_id, photo=m["poster_file_id"], caption=caption, reply_markup=kb, parse_mode="HTML")
    else:
        await bot.send_message(chat_id=chat_id, text=caption, reply_markup=kb, parse_mo
