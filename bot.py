import os
import random
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

ADMINS = [MAIN_ADMIN_ID]
CHANNELS = [CHANNEL_USERNAME]

# Kinolar bazasi
MOVIES = {
    "101": {
        "title": "Qasoskorlar: Intiho",
        "country": "AQSH",
        "genre": "Fantastika",
        "year": "2019",
        "lang": "O'zbekcha",
        "desc": "Koinotni qutqarish uchun so'nggi kurash.",
        "photo_id": None,
        "video_id": None
    }
}

USERS_DB = {}
FAVORITES = {}  # {user_id: [code1, code2]}

# --- HOLATLAR (FSM) ---
class MovieUploadStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_country = State()
    waiting_for_genre = State()
    waiting_for_year = State()
    waiting_for_lang = State()
    waiting_for_desc = State()
    waiting_for_photo = State()
    waiting_for_video = State()
    waiting_for_code = State()

class AdminActions(StatesGroup):
    waiting_for_broadcast = State()
    waiting_for_add_channel = State()
    waiting_for_del_channel = State()
    waiting_for_del_movie = State()

class SearchStates(StatesGroup):
    waiting_for_query_name = State()
    waiting_for_query_country = State()
    waiting_for_query_genre = State()

# --- MENYULAR ---
def get_user_main_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔎 Kinolarni qidirish")],
            [KeyboardButton(text="❤️ Yoqtirishlar"), KeyboardButton(text="🎲 Tasodifiy kino")],
            [KeyboardButton(text="☎️ Admin")]
        ],
        resize_keyboard=True
    )

def get_admin_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📤 Kino Yuklash"), KeyboardButton(text="🗑 Kino o'chirish")],
            [KeyboardButton(text="📢 Kanallarni sozlash"), KeyboardButton(text="✉️ Xabar Yuborish")],
            [KeyboardButton(text="📊 Statistika"), KeyboardButton(text="🚪 Foydalanuvchi menyusi")]
        ],
        resize_keyboard=True
    )

cancel_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="◀️ Orqaga")]],
    resize_keyboard=True
)

search_inline_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="🔎 Kod orqali", callback_data="search_by_code"),
         InlineKeyboardButton(text="🗒️ Nom orqali", callback_data="search_by_name")],
        [InlineKeyboardButton(text="🌍 Davlati orqali", callback_data="search_by_country"),
         InlineKeyboardButton(text="🎬 Janri orqali", callback_data="search_by_genre")],
        [InlineKeyboardButton(text="🎲 Tasodifiy kino", callback_data="random_movie")]
    ]
)

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
        clean_ch = ch.replace("@", "")
        buttons.append([InlineKeyboardButton(text=f"📢 {i}-kanalga a'zo bo'lish", url=f"https://t.me/{clean_ch}")])
    buttons.append([InlineKeyboardButton(text="🔄 Tekshirish", callback_data="check_subscription")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_movie_card_text(code: str, m: dict):
    return (
        f"🎬 <b>Nomi:</b> {m['title']}\n\n"
        f"🧨 <b>Haqida:</b> {m['desc']}\n\n"
        f"🌎 <b>Davlati:</b> {m['country']}\n"
        f"🇺🇿 <b>Tili:</b> {m['lang']}\n"
        f"#️⃣ <b>Janri:</b> {m['genre']}\n"
        f"🗓 <b>Yili:</b> {m['year']}\n\n"
        f"🟥 <b>Kino kodi:</b> <code>{code}</code>"
    )

def get_movie_actions_kb(code: str, bot_username: str):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="❤️ Yoqtirish", callback_data=f"like_{code}"),
             InlineKeyboardButton(text="📥 Videoni olish", callback_data=f"getvideo_{code}")],
            [InlineKeyboardButton(text="🖇️ Filmni ulashish", url=f"https://t.me/share/url?url=https://t.me/{bot_username}?start={code}")]
        ]
    )

# --- START VA OBUNA ---
@dp.message(CommandStart())
async def start_handler(message: types.Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    if user_id not in USERS_DB:
        USERS_DB[user_id] = {
            "first_name": message.from_user.first_name,
            "username": message.from_user.username
        }

    # /start 101 ko'rinishida havola orqali kelganda
    args = message.text.split()
    target_code = args[1] if len(args) > 1 else None

    unsub = await check_channel_membership(user_id)
    if unsub:
        text = (
            f"👋 <b>Assalomu alaykum, {message.from_user.first_name}!</b>\n\n"
            "⚠️ <b>Botdan to'liq foydalanish uchun quyidagi kanallarimizga obuna bo'ling!</b>\n\n"
            "<i>A'zo bo'lgach, «🔄 Tekshirish» tugmasini bosing:</i>"
        )
        await message.answer(text, reply_markup=get_sub_keyboard(unsub), parse_mode="HTML")
        return

    # Agar start orqali to'g'ridan-to'g'ri kino so'ralgan bo'lsa
    if target_code and target_code in MOVIES:
        await send_movie_presentation(message.chat.id, target_code)
        return

    bot_info = await bot.get_me()
    text = (
        f"🖥️ <b>Asosiy menyudasiz:</b>\n\n"
        f"Kino kodlar: {CHANNEL_USERNAME}"
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
        await callback.answer("✅ A'zolik tasdiqlandi!")
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.message.answer(
            f"🎉 <b>A'zolik tasdiqlandi!</b>\n\nKino kodini yuboring yoki menyudan foydalaning:",
            reply_markup=get_user_main_kb(),
            parse_mode="HTML"
        )

# --- BEKOR QILISH / ORQAGA ---
@dp.message(F.text == "◀️ Orqaga")
async def back_to_menu(message: types.Message, state: FSMContext):
    await state.clear()
    if message.from_user.id in ADMINS:
        await message.answer("<b>🖥 Asosiy menyuga qaytdingiz.</b>", reply_markup=get_admin_kb(), parse_mode="HTML")
    else:
        await message.answer("<b>🖥 Asosiy menyuga qaytdingiz.</b>", reply_markup=get_user_main_kb(), parse_mode="HTML")

@dp.message(Command("admin"))
@dp.message(F.text == "🗄 Boshqarish")
async def admin_panel(message: types.Message, state: FSMContext):
    await state.clear()
    if message.from_user.id not in ADMINS:
        return
    await message.answer("<b>Admin paneliga xush kelibsiz!</b>", reply_markup=get_admin_kb(), parse_mode="HTML")

@dp.message(F.text == "🚪 Foydalanuvchi menyusi")
async def back_user_kb(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Foydalanuvchi menyusi:", reply_markup=get_user_main_kb())

@dp.message(F.text == "☎️ Admin")
async def admin_contact(message: types.Message):
    await message.answer(f"📑 Savol va takliflar bo'lsa adminga murojaat qiling: {CHANNEL_USERNAME}")

# --- KINO YUKLASH (ADMIN UCHUN) ---
@dp.message(F.text == "📤 Kino Yuklash")
async def start_upload_movie(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMINS:
        return
    await message.answer("Kino nomini kiriting:", reply_markup=cancel_kb)
    await state.set_state(MovieUploadStates.waiting_for_name)

@dp.message(MovieUploadStates.waiting_for_name)
async def upload_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await message.answer("Qaysi davlatda ishlab chiqarilgan?")
    await state.set_state(MovieUploadStates.waiting_for_country)

@dp.message(MovieUploadStates.waiting_for_country)
async def upload_country(message: types.Message, state: FSMContext):
    await state.update_data(country=message.text.strip())
    await message.answer("Janrini kiriting:")
    await state.set_state(MovieUploadStates.waiting_for_genre)

@dp.message(MovieUploadStates.waiting_for_genre)
async def upload_genre(message: types.Message, state: FSMContext):
    await state.update_data(genre=message.text.strip())
    await message.answer("Ishlab chiqarilgan yilini kiriting:")
    await state.set_state(MovieUploadStates.waiting_for_year)

@dp.message(MovieUploadStates.waiting_for_year)
async def upload_year(message: types.Message, state: FSMContext):
    await state.update_data(year=message.text.strip())
    await message.answer("Kinoning tilini kiriting:")
    await state.set_state(MovieUploadStates.waiting_for_lang)

@dp.message(MovieUploadStates.waiting_for_lang)
async def upload_lang(message: types.Message, state: FSMContext):
    await state.update_data(lang=message.text.strip())
    await message.answer("Kino haqida qisqa ma'lumot kiriting:")
    await state.set_state(MovieUploadStates.waiting_for_desc)

@dp.message(MovieUploadStates.waiting_for_desc)
async def upload_desc(message: types.Message, state: FSMContext):
    await state.update_data(desc=message.text.strip())
    await message.answer("Kino uchun rasmini (poster) yuboring:")
    await state.set_state(MovieUploadStates.waiting_for_photo)

@dp.message(MovieUploadStates.waiting_for_photo)
async def upload_photo(message: types.Message, state: FSMContext):
    if not message.photo:
        await message.answer("Iltimos, rasm yuboring:")
        return
    await state.update_data(photo_id=message.photo[-1].file_id)
    await message.answer("Kinoning video faylini yuboring:")
    await state.set_state(MovieUploadStates.waiting_for_video)

@dp.message(MovieUploadStates.waiting_for_video)
async def upload_video(message: types.Message, state: FSMContext):
    if not message.video:
        await message.answer("Iltimos, video fayl yuboring:")
        return
    await state.update_data(video_id=message.video.file_id)
    await message.answer("Ushbu kino uchun raqamli kod kiriting (masalan: <code>105</code>):", parse_mode="HTML")
    await state.set_state(MovieUploadStates.waiting_for_code)

@dp.message(MovieUploadStates.waiting_for_code)
async def upload_code(message: types.Message, state: FSMContext):
    code = message.text.strip()
    if code in MOVIES:
        await message.answer("❌ Bu kod bazada mavjud! Boshqa kod yozing:")
        return

    data = await state.get_data()
    MOVIES[code] = {
        "title": data["name"],
        "country": data["country"],
        "genre": data["genre"],
        "year": data["year"],
        "lang": data["lang"],
        "desc": data["desc"],
        "photo_id": data["photo_id"],
        "video_id": data["video_id"]
    }

    bot_info = await bot.get_me()
    caption = get_movie_card_text(code, MOVIES[code])

    # Kanalga post yuborish
    try:
        await bot.send_photo(
            chat_id=CHANNEL_USERNAME,
            photo=data["photo_id"],
            caption=caption,
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="🎥 Kinoni yuklab olish", url=f"https://t.me/{bot_info.username}?start={code}")],
                    [InlineKeyboardButton(text="🖇️ Filmni ulashish", url=f"https://t.me/share/url?url=https://t.me/{bot_info.username}?start={code}")]
                ]
            ),
            parse_mode="HTML"
        )
    except Exception as e:
        logging.error(f"Kanalga post yuborishda xatolik: {e}")

    await message.answer(
        f"✅ <b>Kino saqlandi va kanalga yuklandi!</b>\n\n🎬 {data['name']}\n🔢 Kod: <code>{code}</code>",
        reply_markup=get_admin_kb(),
        parse_mode="HTML"
    )
    await state.clear()

# --- STATISTIKA ---
@dp.message(F.text == "📊 Statistika")
async def show_stats(message: types.Message):
    if message.from_user.id not in ADMINS:
        return
    text = (
        "📊 <b>Bot Statistikasi:</b>\n\n"
        f"👥 Foydalanuvchilar: <b>{len(USERS_DB)}</b> ta\n"
        f"🎬 Kinolar soni: <b>{len(MOVIES)}</b> ta\n"
        f"📢 Ulanish kanallari: <b>{len(CHANNELS)}</b> ta"
    )
    await message.answer(text, parse_mode="HTML")

# --- KINO O'CHIRISH ---
@dp.message(F.text == "🗑 Kino o'chirish")
async def del_movie_start(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMINS:
        return
    await message.answer("O'chirmoqchi bo'lgan kino kodini kiriting:", reply_markup=cancel_kb)
    await state.set_state(AdminActions.waiting_for_del_movie)

@dp.message(AdminActions.waiting_for_del_movie)
async def del_movie_finish(message: types.Message, state: FSMContext):
    code = message.text.strip()
    if code in MOVIES:
        del MOVIES[code]
        await message.answer(f"✅ {code} kodli kino o'chirildi!", reply_markup=get_admin_kb())
    else:
        await message.answer("❌ Bunday kodli kino topilmadi.", reply_markup=get_admin_kb())
    await state.clear()

# --- KANALLARNI SOZLASH ---
@dp.message(F.text == "📢 Kanallarni sozlash")
async def manage_channels(message: types.Message):
    if message.from_user.id not in ADMINS:
        return
    ch_list = "\n".join([f"• {c}" for c in CHANNELS]) if CHANNELS else "Kanallar mavjud emas."
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ Kanal Qo'shish", callback_data="add_ch"),
             InlineKeyboardButton(text="🗑 Kanallarni O'chirish", callback_data="del_ch")]
        ]
    )
    await message.answer(f"📢 <b>Ulangan kanallar ro'yxati:</b>\n\n{ch_list}", reply_markup=kb, parse_mode="HTML")

@dp.callback_query(F.data == "add_ch")
async def call_add_ch(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Kanal manzilini @ bilan yuboring (Masalan: @kanal):", reply_markup=cancel_kb)
    await state.set_state(AdminActions.waiting_for_add_channel)
    await callback.answer()

@dp.message(AdminActions.waiting_for_add_channel)
async def process_add_ch(message: types.Message, state: FSMContext):
    ch = message.text.strip()
    if ch.startswith("@") and ch not in CHANNELS:
        CHANNELS.append(ch)
        await message.answer(f"✅ {ch} kanali qo'shildi!", reply_markup=get_admin_kb())
    else:
        await message.answer("Kanal manzili noto'g'ri yoki allaqachon mavjud.", reply_markup=get_admin_kb())
    await state.clear()

@dp.callback_query(F.data == "del_ch")
async def call_del_ch(callback: types.CallbackQuery, state: FSMContext):
    CHANNELS.clear()
    CHANNELS.append(CHANNEL_USERNAME)
    await callback.message.answer("🗑 Kanallar tozalandi (asosiy kanal qoldi)!", reply_markup=get_admin_kb())
    await callback.answer()

# --- XABAR TARQATISH ---
@dp.message(F.text == "✉️ Xabar Yuborish")
async def start_broadcast(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMINS:
        return
    await message.answer("Barcha foydalanuvchilarga yuboriladigan xabarni yuboring:", reply_markup=cancel_kb)
    await state.set_state(AdminActions.waiting_for_broadcast)

@dp.message(AdminActions.waiting_for_broadcast)
async def broadcast_send(message: types.Message, state: FSMContext):
    sent = 0
    await message.answer("Xabar tarqatish boshlandi...")
    for uid in list(USERS_DB.keys()):
        try:
            await message.send_copy(chat_id=uid)
            sent += 1
            await asyncio.sleep(0.05)
        except Exception:
            pass
    await message.answer(f"✅ Xabar {sent} ta foydalanuvchiga yuborildi!", reply_markup=get_admin_kb())
    await state.clear()

# --- KINOLARNI QIDIRISH BO'LIMI ---
@dp.message(F.text == "🔎 Kinolarni qidirish")
async def search_menu_btn(message: types.Message):
    user_id = message.from_user.id
    unsub = await check_channel_membership(user_id)
    if unsub:
        await message.answer("⚠️ Botdan foydalanish uchun kanallarga obuna bo'ling!", reply_markup=get_sub_keyboard(unsub))
        return
    await message.answer("👋 <b>Marhamat, quyidagi qidiruv tizimlaridan birini tanlang:</b>", reply_markup=search_inline_kb, parse_mode="HTML")

@dp.callback_query(F.data == "search_by_code")
async def call_search_code(callback: types.CallbackQuery):
    await callback.message.answer("<b>Marhamat, kerakli kino kodini yuboring:</b>", parse_mode="HTML")
    await callback.answer()

@dp.callback_query(F.data == "search_by_name")
async def call_search_name(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("<b>Marhamat, kino nomini yuboring:</b>", reply_markup=cancel_kb, parse_mode="HTML")
    await state.set_state(SearchStates.waiting_for_query_name)
    await callback.answer()

@dp.message(SearchStates.waiting_for_query_name)
async def search_by_name_process(message: types.Message, state: FSMContext):
    q = message.text.strip().lower()
    matches = [code for code, m in MOVIES.items() if q in m["title"].lower()]
    if matches:
        for code in matches[:3]:
            await send_movie_presentation(message.chat.id, code)
    else:
        await message.answer("<b>Kino topilmadi.</b> Qayta urinib ko'ring:", parse_mode="HTML")
    await state.clear()

@dp.callback_query(F.data == "search_by_country")
async def call_search_country(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("<b>Marhamat, kerakli kino ishlab chiqarilgan davlatni yuboring:</b>", reply_markup=cancel_kb, parse_mode="HTML")
    await state.set_state(SearchStates.waiting_for_query_country)
    await callback.answer()

@dp.message(SearchStates.waiting_for_query_country)
async def search_by_country_process(message: types.Message, state: FSMContext):
    q = message.text.strip().lower()
    matches = [code for code, m in MOVIES.items() if q in m["country"].lower()]
    if matches:
        for code in matches[:3]:
            await send_movie_presentation(message.chat.id, code)
    else:
        await message.answer("<b>Bu davlatga oid kino topilmadi.</b>", parse_mode="HTML")
    await state.clear()

@dp.callback_query(F.data == "search_by_genre")
async def call_search_genre(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("<b>Marhamat, kerakli kino janrini yuboring:</b>", reply_markup=cancel_kb, parse_mode="HTML")
    await state.set_state(SearchStates.waiting_for_query_genre)
    await callback.answer()

@dp.message(SearchStates.waiting_for_query_genre)
async def search_by_genre_process(message: types.Message, state: FSMContext):
    q = message.text.strip().lower()
    matches = [code for code, m in MOVIES.items() if q in m["genre"].lower()]
    if matches:
        for code in matches[:3]:
            await send_movie_presentation(message.chat.id, code)
    else:
        await message.answer("<b>Bu janrga oid kino topilmadi.</b>", parse_mode="HTML")
    await state.clear()

# --- TASODIFIY KINO ---
@dp.message(F.text == "🎲 Tasodifiy kino")
@dp.callback_query(F.data == "random_movie")
async def get_random_movie(event: types.Message | types.CallbackQuery):
    user_id = event.from_user.id
    unsub = await check_channel_membership(user_id)
    if unsub:
        if isinstance(event, types.CallbackQuery):
            await event.message.answer("⚠️ Kanallarga obuna bo'ling:", reply_markup=get_sub_keyboard(unsub))
            await event.answer()
        else:
            await event.answer("⚠️ Kanallarga obuna bo'ling:", reply_markup=get_sub_keyboard(unsub))
        return

    if not MOVIES:
        msg = "🤷🏼‍♂️ Tasodifiy kinolar topilmadi!"
        if isinstance(event, types.CallbackQuery):
            await event.answer(msg, show_alert=True)
        else:
            await event.answer(msg)
        return

    rand_code = random.choice(list(MOVIES.keys()))
    chat_id = event.message.chat.id if isinstance(event, types.CallbackQuery) else event.chat.id
    await send_movie_presentation(chat_id, rand_code)
    if isinstance(event, types.CallbackQuery):
        await event.answer()

# --- YOQTIRISHLAR (FAVORITES) ---
@dp.callback_query(F.data.startswith("like_"))
async def add_to_favorites(callback: types.CallbackQuery):
    code = callback.data.split("_")[1]
    u_id = callback.from_user.id
    if u_id not in FAVORITES:
        FAVORITES[u_id] = []
    if code not in FAVORITES[u_id]:
        FAVORITES[u_id].append(code)
        await callback.answer("❤️ Bu kino sizga yoqdi va saqlandi!", show_alert=True)
    else:
        await callback.answer("Bu film allaqachon yoqtirishlar ro'yxatida!", show_alert=True)

@dp.message(F.text == "❤️ Yoqtirishlar")
async def show_favorites(message: types.Message):
    u_id = message.from_user.id
    favs = FAVORITES.get(u_id, [])
    if not favs:
        await message.answer("🤷‍♂️ <b>Hech qanday maʼlumot topilmadi...</b>", parse_mode="HTML")
        return

    buttons = []
    for code in favs:
        if code in MOVIES:
            buttons.append([InlineKeyboardButton(text=f"📥 {MOVIES[code]['title']}", callback_data=f"showfav_{code}")])
    buttons.append([InlineKeyboardButton(text="🗑️ Tozalash", callback_data="clear_favorites")])

    await message.answer("<b>⏬ Saqlangan kinolaringiz:</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")

@dp.callback_query(F.data == "clear_favorites")
async def clear_favs_call(callback: types.CallbackQuery):
    FAVORITES[callback.from_user.id] = []
    await callback.message.edit_text("✅ <b>Yoqtirishlar tozalandi.</b>", parse_mode="HTML")
    await callback.answer()

@dp.callback_query(F.data.startswith("showfav_"))
async def open_fav_movie(callback: types.CallbackQuery):
    code = callback.data.split("_")[1]
    await send_movie_presentation(callback.message.chat.id, code)
    await callback.answer()

# --- VIDEONI YUKLAB BERISH ---
@dp.callback_query(F.data.startswith("getvideo_"))
async def send_video_direct(callback: types.CallbackQuery):
    code = callback.data.split("_")[1]
    if code in MOVIES:
        m = MOVIES[code]
        if m.get("video_id"):
            await callback.message.answer_video(
                video=m["video_id"],
                caption=f"📄 <b>{m['title']}</b>\n\n📥 Kino muvaffaqiyatli yuklandi!",
                parse_mode="HTML"
            )
        else:
            await callback.answer("Kino videosi mavjud emas.", show_alert=True)
    await callback.answer()

# --- KINO KARTASI YUBORUVCHI YORDAMCHI FUNKSIYA ---
async def send_movie_presentation(chat_id: int, code: str):
    if code not in MOVIES:
        await bot.send_message(chat_id, f"❌ <b>{code}</b> kodli kino topilmadi.", parse_mode="HTML")
        return

    m = MOVIES[code]
    bot_info = await bot.get_me()
    caption = get_movie_card_text(code, m)
    kb = get_movie_actions_kb(code, bot_info.username)

    if m.get("photo_id"):
        await bot.send_photo(chat_id=chat_id, photo=m["photo_id"], caption=caption, reply_markup=kb, parse_mode="HTML")
    elif m.get("video_id"):
        await bot.send_video(chat_id=chat_id, video=m["video_id"], caption=caption, reply_markup=kb, parse_mode="HTML")
    else:
        await bot.send_message(chat_id=chat_id, text=caption, reply_markup=kb, parse_mode="HTML")

# --- KOD ORQALI KINO IZLASH ---
@dp.message(F.text.regexp(r'^\d+$'))
async def find_movie_by_code(message: types.Message):
    user_id = message.from_user.id
    unsub = await check_channel_membership(user_id)
    if unsub:
        await message.answer(
            "⚠️ <b>Kinoni ko'rish uchun oldin kanallarga obuna bo'ling!</b>",
            reply_markup=get_sub_keyboard(unsub),
            parse_mode="HTML"
        )
        return

    code = message.text.strip()
    await send_movie_presentation(message.chat.id, code)

# --- QOLGAN MATNLARNI QIDIRISH SIFATIDA TEKSHIRISH ---
@dp.message(F.text)
async def general_text_search(message: types.Message):
    user_id = message.from_user.id
    unsub = await check_channel_membership(user_id)
    if unsub:
        await message.answer("⚠️ Botdan foydalanish uchun kanallarga a'zo bo'ling!", reply_markup=get_sub_keyboard(unsub))
        return

    q = message.text.strip().lower()
    matches = [f"• <code>{code}</code> — {m['title']}" for code, m in MOVIES.items() if q in m["title"].lower()]
    if matches:
        await message.answer("🔎 <b>Topilgan kinolar:</b>\n\n" + "\n".join(matches), parse_mode="HTML")
    else:
        await message.answer("Kino kodini yuboring (masalan: <code>101</code>).", parse_mode="HTML")

# --- VEB SERVER VA ISHGA TUSHIRISH ---
async def handle_ping(request):
    return web.Response(text="Bot is running!")

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
