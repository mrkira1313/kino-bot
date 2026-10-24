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

ADMINS = [MAIN_ADMIN_ID]
CHANNELS = ["@FORTIS_OKTO"]

# Baza
MOVIES = {
    "101": {
        "title": "Qasoskorlar: Intiho",
        "genre": "Fantastika, Jangari",
        "year": "2019",
        "country": "AQSH",
        "views": 0,
        "episodes": {1: None}
    }
}

USERS_DB = {}

# --- HOLATLAR (FSM) ---
class MovieStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_genre = State()
    waiting_for_year = State()
    waiting_for_country = State()
    waiting_for_code = State()
    waiting_for_video = State()
    waiting_for_add_part_code = State()
    waiting_for_add_part_video = State()

class AdminActions(StatesGroup):
    waiting_for_broadcast = State()
    waiting_for_add_channel = State()
    waiting_for_del_channel = State()
    waiting_for_del_movie = State()

# --- MENYULAR ---
def get_user_main_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔎 Kino izlash")],
            [KeyboardButton(text="💎 VIP"), KeyboardButton(text="💰 Hisobim")],
            [KeyboardButton(text="🔥 Top kinolar"), KeyboardButton(text="📚 Qo'llanma")],
            [KeyboardButton(text="🤝 Reklama va Homiylik")]
        ],
        resize_keyboard=True
    )

def get_admin_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Kino qo'shish"), KeyboardButton(text="📥 Qism qo'shish")],
            [KeyboardButton(text="🗑 Kino o'chirish"), KeyboardButton(text="📢 Kanallar")],
            [KeyboardButton(text="📊 Statistika"), KeyboardButton(text="✉️ Xabar yuborish")],
            [KeyboardButton(text="🚪 Foydalanuvchi menyusi")]
        ],
        resize_keyboard=True
    )

cancel_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="❌ Bekor qilish")]],
    resize_keyboard=True
)

search_inline_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="📌 Kod orqali", callback_data="search_code"),
         InlineKeyboardButton(text="👁 Eng ko'p ko'rilgan", callback_data="search_top")]
    ]
)

vip_inline_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="💎 30 kun - 25 000 so'm", callback_data="buy_vip_30")],
        [InlineKeyboardButton(text="💎 60 kun - 50 000 so'm", callback_data="buy_vip_60")],
        [InlineKeyboardButton(text="💎 90 kun - 75 000 so'm", callback_data="buy_vip_90")]
    ]
)

# --- MAJBURIY OBUNA TEKSHIRUVI ---
async def check_channel_membership(user_id: int):
    if USERS_DB.get(user_id, {}).get("is_vip", False):
        return []
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
            "username": message.from_user.username,
            "balance": 0,
            "is_vip": False
        }

    unsub = await check_channel_membership(user_id)
    if unsub:
        text = (
            f"👋 Assalomu alaykum, <b>{message.from_user.first_name}</b>!\n\n"
            "⚠️ <b>Botdan to'liq foydalanish uchun homiy kanalga obuna bo'ling!</b>\n\n"
            "<i>A'zo bo'lgach, «✅ TEKSHIRISH» tugmasini bosing:</i>"
        )
        await message.answer(text, reply_markup=get_sub_keyboard(unsub), parse_mode="HTML")
        return

    text = (
        f"👋 Assalomu alaykum, <b>{message.from_user.first_name}</b>!\n\n"
        "🎬 <b>Kino Olami | Premyeralar</b> botiga xush kelibsiz!\n"
        "🍿 Kino kodini yuboring (masalan: <code>101</code>):"
    )
    await message.answer(text, reply_markup=get_user_main_kb(), parse_mode="HTML")

@dp.callback_query(F.data == "check_subscription")
async def verify_sub(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    unsub = await check_channel_membership(user_id)
    if unsub:
        await callback.answer("❌ Hali hamma kanallarga a'zo bo'lmadingiz!", show_alert=True)
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
            "🎉 <b>A'zolik tasdiqlandi!</b>\n\nMarhamat, kino kodini yuboring:",
            reply_markup=get_user_main_kb(),
            parse_mode="HTML"
        )

# --- BEKOR QILISH VA ADMIN PANEL ---
@dp.message(F.text == "❌ Bekor qilish")
async def cancel_action(message: types.Message, state: FSMContext):
    await state.clear()
    if message.from_user.id in ADMINS:
        await message.answer("Bekor qilindi.", reply_markup=get_admin_kb())
    else:
        await message.answer("Bekor qilindi.", reply_markup=get_user_main_kb())

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
    total_views = sum(m.get("views", 0) for m in MOVIES.values())
    text = (
        "📊 <b>Bot Statistikasi:</b>\n\n"
        f"👥 Foydalanuvchilar: <b>{len(USERS_DB)}</b> ta\n"
        f"🎬 Kinolar soni: <b>{len(MOVIES)}</b> ta\n"
        f"👀 Jami ko'rishlar: <b>{total_views}</b> marta\n"
        f"📢 Ulanish kanallari: <b>{len(CHANNELS)}</b> ta"
    )
    await message.answer(text, parse_mode="HTML")

# --- KINO QO'SHISH ---
@dp.message(F.text == "➕ Kino qo'shish")
async def start_add_movie(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMINS:
        return
    await message.answer("🎬 <b>Film / Anime nomini kiriting:</b>", reply_markup=cancel_kb, parse_mode="HTML")
    await state.set_state(MovieStates.waiting_for_name)

@dp.message(MovieStates.waiting_for_name)
async def process_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await message.answer("🎭 <b>Janrini kiriting:</b>", parse_mode="HTML")
    await state.set_state(MovieStates.waiting_for_genre)

@dp.message(MovieStates.waiting_for_genre)
async def process_genre(message: types.Message, state: FSMContext):
    await state.update_data(genre=message.text.strip())
    await message.answer("📅 <b>Yilini kiriting:</b>", parse_mode="HTML")
    await state.set_state(MovieStates.waiting_for_year)

@dp.message(MovieStates.waiting_for_year)
async def process_year(message: types.Message, state: FSMContext):
    await state.update_data(year=message.text.strip())
    await message.answer("🌍 <b>Davlatini kiriting:</b>", parse_mode="HTML")
    await state.set_state(MovieStates.waiting_for_country)

@dp.message(MovieStates.waiting_for_country)
async def process_country(message: types.Message, state: FSMContext):
    await state.update_data(country=message.text.strip())
    await message.answer("🔢 <b>Kino uchun raqamli kod kiriting:</b>", parse_mode="HTML")
    await state.set_state(MovieStates.waiting_for_code)

@dp.message(MovieStates.waiting_for_code)
async def process_code(message: types.Message, state: FSMContext):
    code = message.text.strip()
    if code in MOVIES:
        await message.answer("❌ Bu kod bazada mavjud! Boshqa kod kiriting:")
        return
    await state.update_data(code=code)
    await message.answer("🎥 <b>Kinoning 1-qism videosini yuboring:</b>", parse_mode="HTML")
    await state.set_state(MovieStates.waiting_for_video)

@dp.message(MovieStates.waiting_for_video)
async def process_video(message: types.Message, state: FSMContext):
    if not message.video:
        await message.answer("Iltimos, video fayl yuboring:")
        return
    data = await state.get_data()
    v_id = message.video.file_id

    MOVIES[data["code"]] = {
        "title": data["name"],
        "genre": data["genre"],
        "year": data["year"],
        "country": data["country"],
        "views": 0,
        "episodes": {1: v_id}
    }

    await message.answer(
        f"✅ <b>Kino saqlandi!</b>\n\n🎬 {data['name']}\n🔢 Kod: <code>{data['code']}</code> (1-qism)",
        reply_markup=get_admin_kb(),
        parse_mode="HTML"
    )
    await state.clear()

# --- QISM QO'SHISH ---
@dp.message(F.text == "📥 Qism qo'shish")
async def start_add_part(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMINS:
        return
    await message.answer("Qism qo'shiladigan kino kodini kiriting:", reply_markup=cancel_kb)
    await state.set_state(MovieStates.waiting_for_add_part_code)

@dp.message(MovieStates.waiting_for_add_part_code)
async def process_part_code(message: types.Message, state: FSMContext):
    code = message.text.strip()
    if code not in MOVIES:
        await message.answer("❌ Bunday kodli film topilmadi. Qayta kiriting:")
        return
    await state.update_data(target_code=code)
    current_episodes = len(MOVIES[code]["episodes"])
    await message.answer(
        f"Kino: <b>{MOVIES[code]['title']}</b>\nHozirda {current_episodes} ta qism bor.\n\n"
        f"<b>{current_episodes + 1}-qism videosini yuboring:</b>",
        parse_mode="HTML"
    )
    await state.set_state(MovieStates.waiting_for_add_part_video)

@dp.message(MovieStates.waiting_for_add_part_video)
async def process_part_video(message: types.Message, state: FSMContext):
    if not message.video:
        await message.answer("Iltimos, video yuboring:")
        return
    data = await state.get_data()
    code = data["target_code"]
    new_part = len(MOVIES[code]["episodes"]) + 1
    MOVIES[code]["episodes"][new_part] = message.video.file_id

    await message.answer(
        f"✅ <b>{MOVIES[code]['title']}</b> filmiga {new_part}-qism qo'shildi!",
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
    ch_list = "\n".join([f"• {c}" for c in CHANNELS]) if CHANNELS else "Kanallar mavjud emas."
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ Kanal qo'shish", callback_data="add_ch")],
            [InlineKeyboardButton(text="🗑 Kanal o'chirish", callback_data="del_ch")]
        ]
    )
    await message.answer(f"📢 <b>Majburiy obuna kanallari:</b>\n\n{ch_list}", reply_markup=kb, parse_mode="HTML")

@dp.callback_query(F.data == "add_ch")
async def call_add_ch(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Kanal usernamesini @ bilan yuboring (Masalan: @kanal):", reply_markup=cancel_kb)
    await state.set_state(AdminActions.waiting_for_add_channel)
    await callback.answer()

@dp.message(AdminActions.waiting_for_add_channel)
async def process_add_ch(message: types.Message, state: FSMContext):
    ch = message.text.strip()
    if ch.startswith("@") and ch not in CHANNELS:
        CHANNELS.append(ch)
        await message.answer(f"✅ {ch} kanali ulandi!", reply_markup=get_admin_kb())
    else:
        await message.answer("Xatolik yoki kanal mavjud.", reply_markup=get_admin_kb())
    await state.clear()

@dp.callback_query(F.data == "del_ch")
async def call_del_ch(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("O'chirmoqchi bo'lgan kanal usernamesini kiriting:", reply_markup=cancel_kb)
    await state.set_state(AdminActions.waiting_for_del_channel)
    await callback.answer()

@dp.message(AdminActions.waiting_for_del_channel)
async def process_del_ch(message: types.Message, state: FSMContext):
    ch = message.text.strip()
    if ch in CHANNELS:
        CHANNELS.remove(ch)
        await message.answer(f"✅ {ch} o'chirildi!", reply_markup=get_admin_kb())
    else:
        await message.answer("Bunday kanal topilmadi.", reply_markup=get_admin_kb())
    await state.clear()

# --- XABAR TARQATISH ---
@dp.message(F.text == "✉️ Xabar yuborish")
async def start_broadcast(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMINS:
        return
    await message.answer("Barcha foydalanuvchilarga yuboriladigan xabarni yuboring:", reply_markup=cancel_kb)
    await state.set_state(AdminActions.waiting_for_broadcast)

@dp.message(AdminActions.waiting_for_broadcast)
async def broadcast_send(message: types.Message, state: FSMContext):
    sent = 0
    await message.answer("Xabar tarqatilmoqda...")
    for uid in list(USERS_DB.keys()):
        try:
            await message.send_copy(chat_id=uid)
            sent += 1
            await asyncio.sleep(0.05)
        except Exception:
            pass
    await message.answer(f"✅ Xabar {sent} ta foydalanuvchiga yuborildi!", reply_markup=get_admin_kb())
    await state.clear()

# --- KINO YUBORISH VA QISMLARNI ALMASHTIRISH ---
def make_movie_keyboard(code: str, active_part: int, total_parts: int):
    buttons = []
    if total_parts > 1:
        row = []
        for p in range(1, total_parts + 1):
            btn_text = f"[{p}]" if p == active_part else str(p)
            row.append(InlineKeyboardButton(text=btn_text, callback_data=f"part_{code}_{p}"))
            if len(row) == 5:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)
    buttons.append([InlineKeyboardButton(text="↗️ Do'stlarga ulashish", switch_inline_query=code)])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

@dp.callback_query(F.data.startswith("part_"))
async def switch_episode(callback: types.CallbackQuery):
    _, code, part = callback.data.split("_")
    part = int(part)
    if code in MOVIES and part in MOVIES[code]["episodes"]:
        v_id = MOVIES[code]["episodes"][part]
        m = MOVIES[code]
        caption = (
            f"🎬 <b>{m['title']}</b> ({part}-qism)\n"
            f"🎭 <b>Janr:</b> {m['genre']}\n"
            f"⭐️ <b>Yili:</b> {m['year']} | 🌍 {m['country']}\n"
            f"🔢 <b>Kodi:</b> <code>{code}</code>\n\n"
            f"📢 <b>Kanal:</b> @FORTIS_OKTO"
        )
        try:
            await callback.message.delete()
        except Exception:
            pass
            
        if v_id:
            await callback.message.answer_video(
                video=v_id,
                caption=caption,
                reply_markup=make_movie_keyboard(code, part, len(m["episodes"])),
                parse_mode="HTML"
            )
        else:
            await callback.message.answer(
                caption,
                reply_markup=make_movie_keyboard(code, part, len(m["episodes"])),
                parse_mode="HTML"
            )
    await callback.answer()

@dp.message(F.text.regexp(r'^\d+$'))
async def send_movie_by_code(message: types.Message):
    user_id = message.from_user.id
    unsub = await check_channel_membership(user_id)
    if unsub:
        await message.answer(
            "⚠️ <b>Kinoni ko'rish uchun oldin homiy kanalga obuna bo'ling!</b>\n\n"
            "<i>A'zo bo'lgach, «✅ TEKSHIRISH» tugmasini bosing:</i>",
            reply_markup=get_sub_keyboard(unsub),
            parse_mode="HTML"
        )
        return

    code = message.text.strip()
    if code in MOVIES:
        m = MOVIES[code]
        m["views"] = m.get("views", 0) + 1
        total_parts = len(m["episodes"])
        v_id = m["episodes"].get(1)
        
        caption = (
            f"🎬 <b>Film nomi:</b> {m['title']}\n"
            f"🎭 <b>Janr:</b> {m['genre']}\n"
            f"⭐️ <b>Yili:</b> {m['year']} | 🌍 {m['country']}\n"
            f"👀 <b>Ko'rishlar:</b> {m['views']} marta\n"
            f"🔢 <b>Kodi:</b> <code>{code}</code>\n\n"
            f"📢 <b>Kanal:</b> @FORTIS_OKTO"
        )
        
        kb = make_movie_keyboard(code, 1, total_parts)
        if v_id:
            await message.answer_video(video=v_id, caption=caption, reply_markup=kb, parse_mode="HTML")
        else:
            await message.answer(caption, reply_markup=kb, parse_mode="HTML")
    else:
        await message.answer(f"❌ <b>{code}</b> raqamli kino bazadan topilmadi.")

# --- FOYDALANUVCHI MENYULARI ---
@dp.message(F.text == "🔎 Kino izlash")
async def user_search_btn(message: types.Message):
    user_id = message.from_user.id
    unsub = await check_channel_membership(user_id)
    if unsub:
        await message.answer("⚠️ Botdan foydalanish uchun homiy kanalga obuna bo'ling!", reply_markup=get_sub_keyboard(unsub))
        return
    await message.answer("<b>Qidiruv turini tanlang:</b>", reply_markup=search_inline_kb, parse_mode="HTML")

@dp.callback_query(F.data == "search_code")
async def call_search_code(callback: types.CallbackQuery):
    await callback.message.answer("🍿 Kinoni olish uchun kodini yuboring (masalan: <code>101</code>):", parse_mode="HTML")
    await callback.answer()

@dp.callback_query(F.data == "search_top")
async def call_search_top(callback: types.CallbackQuery):
    sorted_movies = sorted(MOVIES.items(), key=lambda x: x[1].get("views", 0), reverse=True)[:5]
    text = "👁 <b>Eng ko'p ko'rilgan kinolar:</b>\n\n"
    for code, m in sorted_movies:
        text += f"• <code>{code}</code> — {m['title']} ({m.get('views', 0)} marta)\n"
    
