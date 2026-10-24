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
SUPER_ADMIN = 6505655178

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Ma'lumotlar bazasi (xotirada)
BOT_SETTINGS = {
    "active": True,
    "currency": "so'm",
    "vip_price": 25000,
    "studio": "FORTIS CINEMA"
}

ADMINS = [SUPER_ADMIN]
CHANNELS = ["@FORTIS_OKTO"]

MOVIES = {
    "101": {"title": "Qasoskorlar: Intiho", "genre": "Fantastika, Jangari", "year": "2019"},
    "102": {"title": "Avatar: Suv yo'li", "genre": "Fantastika, Sarguzasht", "year": "2022"},
    "105": {"title": "Forsaj 10", "genre": "Jangari, Triller", "year": "2023"}
}

USERS_DB = {}

# Holatlar (FSM)
class AdminStates(StatesGroup):
    waiting_for_broadcast = State()
    waiting_for_add_channel = State()
    waiting_for_del_channel = State()
    waiting_for_add_movie_code = State()
    waiting_for_add_movie_title = State()

# --- MENYULAR ---
user_main_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🎬 Kino izlash")],
        [KeyboardButton(text="💎 VIP"), KeyboardButton(text="💰 Hisobim")],
        [KeyboardButton(text="💳 Pul kiritish"), KeyboardButton(text="📚 Qo'llanma")],
        [KeyboardButton(text="🤝 Reklama va Homiylik")]
    ],
    resize_keyboard=True
)

admin_main_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🔎 Foydalanuvchini boshqarish")],
        [KeyboardButton(text="📢 Kanallar"), KeyboardButton(text="🎬 Kino qo'shish")],
        [KeyboardButton(text="📑 Adminlar"), KeyboardButton(text="🤖 Bot holati")],
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
        [InlineKeyboardButton(text="🏷 Kino nomi orqali", callback_data="search_name"),
         InlineKeyboardButton(text="🕒 So'nggi premyeralar", callback_data="search_latest")],
        [InlineKeyboardButton(text="💬 Janr orqali qidirish", callback_data="search_genre")],
        [InlineKeyboardButton(text="📌 Kod orqali", callback_data="search_code"),
         InlineKeyboardButton(text="👁 Eng ko'p ko'rilgan", callback_data="search_top")],
        [InlineKeyboardButton(text="🖼 Rasm / Afisha orqali", callback_data="search_poster")],
        [InlineKeyboardButton(text="🌐 Onlayn Tomosha / Sayt", url="https://t.me/FORTIS_OKTO")],
        [InlineKeyboardButton(text="📚 Barcha kinolar katalogi", callback_data="all_movies")]
    ]
)

vip_inline_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="💎 30 kun - 25 000 so'm", callback_data="buy_vip_30")],
        [InlineKeyboardButton(text="💎 60 kun - 50 000 so'm", callback_data="buy_vip_60")],
        [InlineKeyboardButton(text="💎 90 kun - 75 000 so'm", callback_data="buy_vip_90")]
    ]
)

# --- USER HANDLERLAR ---
@dp.message(CommandStart())
async def start_cmd(message: types.Message, state: FSMContext):
    await state.clear()
    u_id = message.from_user.id
    if u_id not in USERS_DB:
        USERS_DB[u_id] = {"balance": 0, "is_vip": False}

    text = (
        "👋 <b>Assalomu alaykum!</b>\n"
        "🎬 <b>Kino Olami | Premyeralar</b> botiga xush kelibsiz!\n\n"
        "🍿 Sevimli filmingizni tomosha qilish uchun uning kodini yuboring (masalan: <code>101</code>) "
        "yoki quyidagi menyudan foydalaning: 👇"
    )
    await message.answer(text, reply_markup=user_main_kb, parse_mode="HTML")

@dp.message(F.text == "❌ Bekor qilish")
async def cancel_handler(message: types.Message, state: FSMContext):
    await state.clear()
    if message.from_user.id in ADMINS:
        await message.answer("Bekor qilindi.", reply_markup=admin_main_kb)
    else:
        await message.answer("Bekor qilindi.", reply_markup=user_main_kb)

@dp.message(Command("admin"))
async def admin_cmd(message: types.Message, state: FSMContext):
    await state.clear()
    if message.from_user.id not in ADMINS:
        return
    await message.answer("🛠 <b>Admin paneliga xush kelibsiz!</b>", reply_markup=admin_main_kb, parse_mode="HTML")

@dp.message(F.text == "🚪 Foydalanuvchi menyusi")
async def back_to_user(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Asosiy foydalanuvchi menyusi:", reply_markup=user_main_kb)

# --- KANALLARNI BOSHQARISH ---
@dp.message(F.text == "📢 Kanallar")
async def handle_channels_menu(message: types.Message):
    if message.from_user.id not in ADMINS:
        return
    
    channels_text = "\n".join([f"• {ch}" for ch in CHANNELS]) if CHANNELS else "Ulanish kanallari mavjud emas."
    
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ Kanal qo'shish", callback_data="add_channel")],
            [InlineKeyboardButton(text="➖ Kanalni o'chirish", callback_data="del_channel")]
        ]
    )
    await message.answer(
        f"📢 <b>Majburiy a'zolik kanallari ro'yxati:</b>\n\n{channels_text}",
        reply_markup=kb,
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "add_channel")
async def call_add_channel(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMINS:
        return
    await callback.message.answer(
        "Kanal usernamesini @ belgisi bilan yuboring (Masalan: <code>@mening_kanalim</code>):\n\n"
        "<i>Eslatma: Bot ushbu kanalda administrator bo'lishi shart!</i>",
        reply_markup=cancel_kb,
        parse_mode="HTML"
    )
    await state.set_state(AdminStates.waiting_for_add_channel)
    await callback.answer()

@dp.message(AdminStates.waiting_for_add_channel)
async def process_add_channel(message: types.Message, state: FSMContext):
    ch = message.text.strip()
    if not ch.startswith("@"):
        await message.answer("Kanal manzili @ bilan boshlanishi kerak (masalan: @kanal_nomi). Qaytadan yuboring:")
        return
    if ch not in CHANNELS:
        CHANNELS.append(ch)
        await message.answer(f"✅ {ch} kanali muvaffaqiyatli qo'shildi!", reply_markup=admin_main_kb)
    else:
        await message.answer(f"Ushbu kanal allaqachon mavjud.", reply_markup=admin_main_kb)
    await state.clear()

@dp.callback_query(F.data == "del_channel")
async def call_del_channel(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMINS:
        return
    if not CHANNELS:
        await callback.message.answer("O'chirish uchun kanallar mavjud emas.")
        await callback.answer()
        return
    await callback.message.answer(
        "O'chirmoqchi bo'lgan kanal usernamesini yuboring (Masalan: @kanal):",
        reply_markup=cancel_kb
    )
    await state.set_state(AdminStates.waiting_for_del_channel)
    await callback.answer()

@dp.message(AdminStates.waiting_for_del_channel)
async def process_del_channel(message: types.Message, state: FSMContext):
    ch = message.text.strip()
    if ch in CHANNELS:
        CHANNELS.remove(ch)
        await message.answer(f"✅ {ch} o'chirildi!", reply_markup=admin_main_kb)
    else:
        await message.answer("Bunday kanal topilmadi.", reply_markup=admin_main_kb)
    await state.clear()

# --- XABAR YUBORISH (RASSILKA) ---
@dp.message(F.text == "✉️ Xabar yuborish")
async def start_broadcast(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMINS:
        return
    await message.answer(
        "Barcha foydalanuvchilarga yuborilishi kerak bo'lgan xabarni (matn, rasm, video) yuboring:",
        reply_markup=cancel_kb
    )
    await state.set_state(AdminStates.waiting_for_broadcast)

@dp.message(AdminStates.waiting_for_broadcast)
async def do_broadcast(message: types.Message, state: FSMContext):
    sent = 0
    await message.answer("Xabar tarqatish boshlandi...")
    for uid in list(USERS_DB.keys()):
        try:
            await message.send_copy(chat_id=uid)
            sent += 1
            await asyncio.sleep(0.05)
        except Exception:
            pass
    await message.answer(f"✅ Xabar {sent} ta foydalanuvchiga muvaffaqiyatli yetkazildi!", reply_markup=admin_main_kb)
    await state.clear()

# --- KINO QO'SHISH ---
@dp.message(F.text == "🎬 Kino qo'shish")
async def add_movie_start(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMINS:
        return
    await message.answer("Yangi kino uchun raqamli kod kiriting (masalan: 106):", reply_markup=cancel_kb)
    await state.set_state(AdminStates.waiting_for_add_movie_code)

@dp.message(AdminStates.waiting_for_add_movie_code)
async def add_movie_code(message: types.Message, state: FSMContext):
    code = message.text.strip()
    if not code.isdigit():
        await message.answer("Kino kodi faqat raqamlardan iborat bo'lishi kerak. Qayta kiriting:")
        return
    await state.update_data(m_code=code)
    await message.answer("Kino nomini va tavsifini kiriting (masalan: Batman | Jangari | 2022):")
    await state.set_state(AdminStates.waiting_for_add_movie_title)

@dp.message(AdminStates.waiting_for_add_movie_title)
async def add_movie_finish(message: types.Message, state: FSMContext):
    data = await state.get_data()
    code = data["m_code"]
    title = message.text.strip()
    MOVIES[code] = {"title": title, "genre": "Kino Olami Premyera", "year": "2024"}
    await message.answer(f"✅ <b>{code}</b> kodli kino qo'shildi: {title}", reply_markup=admin_main_kb, parse_mode="HTML")
    await state.clear()

# --- STATISTIKA VA STATUS ---
@dp.message(F.text == "📊 Statistika")
async def admin_stat(message: types.Message):
    if message.from_user.id not in ADMINS:
        return
    await message.answer(
        f"📊 <b>Statistika:</b>\n\n"
        f"👥 Foydalanuvchilar: {len(USERS_DB)} ta\n"
        f"🎬 Kinolar soni: {len(MOVIES)} ta\n"
        f"📢 Ulanish kanallari: {len(CHANNELS)} ta",
        parse_mode="HTML"
    )

@dp.message(F.text == "🤖 Bot holati")
async def admin_state(message: types.Message):
    if message.from_user.id not in ADMINS:
        return
    holat = "Yoqilgan ✅" if BOT_SETTINGS["active"] else "To'xtatilgan ⛔️"
    await message.answer(f"🤖 <b>Bot holati:</b> {holat}", parse_mode="HTML")

# --- QIDIRUV VA FOYDALANUVCHI BO'LIMLARI ---
@dp.message(F.text == "🎬 Kino izlash")
async def handle_search_btn(message: types.Message):
    await message.answer("<b>Qidiruv tipini tanlang :</b>", reply_markup=search_inline_kb, parse_mode="HTML")

@dp.message(F.text == "💎 VIP")
async def handle_vip_btn(message: types.Message):
    text = (
        "💎 <b>VIP obuna imkoniyatlari:</b>\n"
        "• VIP premyera kanaliga to'g'ridan-to'g'ri havola\n"
        "• Majburiy kanallarga a'zo bo'lmasdan kinolarni olish\n"
        "• Reklamalarsiz tezkor tomosha\n\n"
        "<i>Kerakli muddatni tanlang:</i>"
    )
    await message.answer(text, reply_markup=vip_inline_kb, parse_mode="HTML")

@dp.message(F.text == "💰 Hisobim")
async def handle_balance_btn(message: types.Message):
    u_id = message.from_user.id
    u_data = USERS_DB.get(u_id, {"balance": 0, "is_vip": False})
    status = "VIP Obunachi 💎" if u_data["is_vip"] else "Oddiy a'zo"
    await message.answer(
        f"🆔 <b>ID:</b> <code>{u_id}</code>\n"
        f"💰 <b>Balans:</b> {u_data['balance']} so'm\n"
        f"💎 <b>Status:</b> {status}",
        parse_mode="HTML"
    )

@dp.message(F.text == "💳 Pul kiritish")
async def handle_deposit_btn(message: types.Message):
    deposit_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔹 Click", callback_data="pay_click"),
             InlineKeyboardButton(text="🔹 Payme", callback_data="pay_payme")]
        ]
    )
    await message.answer("To'lov tizimini tanlang:", reply_markup=deposit_kb)

@dp.message(F.text == "📚 Qo'llanma")
async def handle_guide_btn(message: types.Message):
    text = (
        "📖 <b>Botdan foydalanish qo'llanmasi:</b>\n\n"
        "1. Kanalimizdagi postdan kino kodini oling.\n"
        "2. Botga o'sha kodni yuboring va film sizga taqdim etiladi.\n"
        "3. VIP a'zolar uchun kanalga a'zo bo'lish talabi mavjud emas."
    )
    await message.answer(text, parse_mode="HTML")

@dp.message(F.text == "🤝 Reklama va Homiylik")
async def handle_promo_btn(message: types.Message):
    await message.answer("📢 Reklama va hamkorlik uchun: @FORTIS_OKTO")

@dp.message(F.text.regexp(r'^\d+$'))
async def find_movie(message: types.Message):
    code = message.text.strip()
    if code in MOVIES:
        m = MOVIES[code]
        card = (
            f"🎬 <b>Film nomi:</b> {m['title']}\n"
            f"🔢 <b>Kodi:</b> <code>{code}</code>\n"
            f"🌍 <b>Tili:</b> O‘zbekcha dublyaj (HD)\n"
            f"🎭 <b>Janr:</b> {m['genre']}\n"
            f"⭐️ <b>Yili:</b> {m['year']}\n"
            f"📢 <b>Kanalimiz:</b> @FORTIS_OKTO"
        )
        actions = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="↗️ Do'stlarga ulashish", switch_inline_query=code)]
            ]
        )
        await message.answer(card, reply_markup=actions, parse_mode="HTML")
    else:
        await message.answer(f"❌ <b>{code}</b> raqamli kino topilmadi.")

# --- RENDER PORTI UCHUN SOXTA VEB-SERVER ---
async def handle_ping(request):
    return web.Response(text="Bot is running!")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

# --- ASOSIY ISHGA TUSHIRISH ---
async def main():
    await start_web_server()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
    
