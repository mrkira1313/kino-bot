import os
import json
import asyncio
import logging
from aiohttp import web, ClientSession
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton,
    InlineQueryResultArticle, InputTextMessageContent,
    FSInputFile
)

# ================= ASOSIY SOZLAMALAR =================
BOT_TOKEN = "8318167396:AAFwWj6MyQW-_sBSRtC3czw2D5w2lcbp3Mk"
MAIN_ADMIN_ID = 6505655178
DEFAULT_CHANNEL = "@FORTIS_OKTO"
RENDER_URL = "https://kino-bot-1-odty.onrender.com"  # Uxlab qolmaslik uchun o'z manzili
DB_FILE = "database.json"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# ================= BAZA BILAN ISHLASH =================
def load_db():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"Bazani o'qishda xato: {e}")
    return {
        "admins": [MAIN_ADMIN_ID],
        "channels": [DEFAULT_CHANNEL],
        "users": [],
        "movies": {
            "1": {
                "title": "Qasoskorlar: Intiho",
                "genre": "Fantastika, Jangari",
                "year": "2019",
                "video_id": None,
                "views": 0
            }
        }
    }

def save_db():
    try:
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(db, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"Bazani saqlashda xato: {e}")

db = load_db()
if MAIN_ADMIN_ID not in db["admins"]:
    db["admins"].append(MAIN_ADMIN_ID)

async def send_backup_to_admin(caption_text="📦 Yangilangan baza zaxirasi"):
    save_db()
    if os.path.exists(DB_FILE):
        try:
            doc = FSInputFile(DB_FILE)
            await bot.send_document(
                chat_id=MAIN_ADMIN_ID,
                document=doc,
                caption=f"{caption_text}\n\n💡 <i>Server qayta yonganda bazani tiklash uchun ushbu faylni botga qayta yuboring.</i>",
                parse_mode="HTML"
            )
        except Exception as e:
            logging.error(f"Backup yuborishda xato: {e}")

# ================= FSM HOLATLARI =================
class AddMovieState(StatesGroup):
    title = State()
    genre = State()
    year = State()
    code = State()
    video = State()

class DelMovieState(StatesGroup):
    code = State()

class ChannelState(StatesGroup):
    add = State()
    remove = State()

class AdminState(StatesGroup):
    add = State()
    remove = State()

class BroadcastState(StatesGroup):
    message = State()

class RestoreDBState(StatesGroup):
    file = State()

# ================= KLAVIATURALAR =================
def user_menu(user_id: int):
    kb = [
        [KeyboardButton(text="🔎 Kino izlash"), KeyboardButton(text="🔥 Top kinolar")],
        [KeyboardButton(text="📊 Statistika"), KeyboardButton(text="ℹ️ Yordam")]
    ]
    if user_id in db["admins"]:
        kb.append([KeyboardButton(text="👨‍💼 Admin Panel")])
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def admin_menu():
    kb = [
        [KeyboardButton(text="➕ Kino qo'shish"), KeyboardButton(text="🗑 Kino o'chirish")],
        [KeyboardButton(text="📋 Kinolar ro'yxati"), KeyboardButton(text="📢 Kanallar")],
        [KeyboardButton(text="📨 Xabar tarqatish"), KeyboardButton(text="👤 Adminlar")],
        [KeyboardButton(text="📦 Bazani olish"), KeyboardButton(text="📥 Bazani tiklash")],
        [KeyboardButton(text="🚪 Oddiy menyu")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

cancel_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="❌ Bekor qilish")]],
    resize_keyboard=True
)

# ================= MAJBURIY OBUNA =================
async def get_unsubscribed_channels(user_id: int):
    if user_id in db["admins"]:
        return []
    unsub = []
    for ch in db["channels"]:
        try:
            member = await bot.get_chat_member(chat_id=ch, user_id=user_id)
            if member.status not in ["creator", "administrator", "member"]:
                unsub.append(ch)
        except Exception as e:
            logging.error(f"Obuna tekshirishda xato ({ch}): {e}")
            unsub.append(ch)
    return unsub

def sub_keyboard(channels):
    buttons = []
    for idx, ch in enumerate(channels, 1):
        clean = ch.replace("@", "")
        buttons.append([InlineKeyboardButton(text=f"📢 {idx}-kanalga obuna bo'lish", url=f"https://t.me/{clean}")])
    buttons.append([InlineKeyboardButton(text="✅ Obunani tekshirish", callback_data="check_sub")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# ================= START VA OBUNA HANDLERLARI =================
@dp.message(CommandStart())
async def start_cmd(message: types.Message, state: FSMContext):
    await state.clear()
    uid = message.from_user.id
    if uid not in db["users"]:
        db["users"].append(uid)
        save_db()

    unsub = await get_unsubscribed_channels(uid)
    if unsub:
        await message.answer(
            f"👋 Assalomu alaykum, <b>{message.from_user.first_name}</b>!\n\n"
            "⚠️ <b>Botdan to'liq foydalanish va kinolarni tomosha qilish uchun quyidagi kanallarga obuna bo'ling:</b>",
            reply_markup=sub_keyboard(unsub),
            parse_mode="HTML"
        )
        return

    await message.answer(
        f"👋 Assalomu alaykum, <b>{message.from_user.first_name}</b>!\n\n"
        "🎬 <b>Kino Olami botiga xush kelibsiz!</b>\n\n"
        "🍿 Kinoni olish uchun uning <b>kodini</b> yoki <b>nomini</b> yuboring:",
        reply_markup=user_menu(uid),
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "check_sub")
async def check_sub_callback(callback: types.CallbackQuery):
    uid = callback.from_user.id
    unsub = await get_unsubscribed_channels(uid)
    if unsub:
        await callback.answer("❌ Hali barcha kanallarga obuna bo'lmadingiz!", show_alert=True)
    else:
        await callback.answer("✅ Obuna tasdiqlandi!")
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.message.answer(
            "🎉 <b>Obuna tasdiqlandi!</b>\n\n🍿 Marhamat, kino kodini yoki nomini yuboring:",
            reply_markup=user_menu(uid),
            parse_mode="HTML"
        )

# ================= UMUMIY TUGMALAR =================
@dp.message(F.text == "❌ Bekor qilish")
async def cancel_action(message: types.Message, state: FSMContext):
    await state.clear()
    uid = message.from_user.id
    kb = admin_menu() if uid in db["admins"] else user_menu(uid)
    await message.answer("✅ Amal bekor qilindi.", reply_markup=kb)

@dp.message(F.text == "🚪 Oddiy menyu")
async def back_to_user(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("🏠 Asosiy menyu:", reply_markup=user_menu(message.from_user.id))

@dp.message(F.text == "👨‍💼 Admin Panel")
@dp.message(Command("admin"))
async def open_admin(message: types.Message, state: FSMContext):
    await state.clear()
    if message.from_user.id not in db["admins"]:
        return
    await message.answer("👨‍💼 <b>Admin boshqaruv paneli:</b>", reply_markup=admin_menu(), parse_mode="HTML")

@dp.message(F.text == "🔎 Kino izlash")
async def search_info(message: types.Message):
    inline_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Nom bo'yicha qidirish (Inline)", switch_inline_query_current_chat="")]
    ])
    await message.answer(
        "🔎 <b>Kino qidirish usullari:</b>\n\n"
        "1️⃣ Kino <b>kodini</b> yuboring (masalan: <code>101</code>)\n"
        "2️⃣ Kino <b>nomini</b> yozib yuboring\n"
        "3️⃣ Pastdagi tugma orqali barcha kinolar ichidan qidiring:",
        reply_markup=inline_kb,
        parse_mode="HTML"
    )

@dp.message(F.text == "🔥 Top kinolar")
async def top_movies(message: types.Message):
    if not db["movies"]:
        await message.answer("📭 Hozircha bazada kinolar yo'q.")
        return
    sorted_m = sorted(db["movies"].items(), key=lambda x: x[1].get("views", 0), reverse=True)[:10]
    text = "🔥 <b>Eng ko'p ko'rilgan TOP kinolar:</b>\n\n"
    for idx, (code, m) in enumerate(sorted_m, 1):
        text += f"{idx}. 🎬 <b>{m['title']}</b> — Kod: <code>{code}</code> (👁 {m.get('views', 0)})\n"
    text += "\n👉 <i>Kodni nusxalab botga yuboring!</i>"
    await message.answer(text, parse_mode="HTML")

@dp.message(F.text == "📊 Statistika")
async def stats_info(message: types.Message):
    total_views = sum(m.get("views", 0) for m in db["movies"].values())
    await message.answer(
        f"📊 <b>Bot Statistikasi:</b>\n\n"
        f"👥 Foydalanuvchilar: <b>{len(db['users'])}</b> ta\n"
        f"🎬 Jami kinolar: <b>{len(db['movies'])}</b> ta\n"
        f"👁 Jami ko'rishlar: <b>{total_views}</b> marta\n"
        f"📢 Homiy kanallar: <b>{len(db['channels'])}</b> ta",
        parse_mode="HTML"
    )

@dp.message(F.text == "ℹ️ Yordam")
async def help_info(message: types.Message):
    await message.answer(
        "ℹ️ <b>Yordam bo'limi:</b>\n\n"
        "• Botdan kino olish uchun kanalimizga obuna bo'ling va kino kodini yuboring.\n"
        f"• Rasmiy kanal: <b>{DEFAULT_CHANNEL}</b>",
        parse_mode="HTML"
    )

# ================= ADMIN: KINO QO'SHISH VA O'CHIRISH =================
@dp.message(F.text == "➕ Kino qo'shish")
async def add_movie_start(message: types.Message, state: FSMContext):
    if message.from_user.id not in db["admins"]:
        return
    await message.answer("🎬 <b>Kino nomini kiriting:</b>", reply_markup=cancel_kb, parse_mode="HTML")
    await state.set_state(AddMovieState.title)

@dp.message(AddMovieState.title)
async def add_movie_title(message: types.Message, state: FSMContext):
    await state.update_data(title=message.text.strip())
    await message.answer("🎭 <b>Kino janrini kiriting:</b>\n<i>(Masalan: Jangari, Fantastika)</i>", parse_mode="HTML")
    await state.set_state(AddMovieState.genre)

@dp.message(AddMovieState.genre)
async def add_movie_genre(message: types.Message, state: FSMContext):
    await state.update_data(genre=message.text.strip())
    await message.answer("📅 <b>Kino chiqqan yilni kiriting:</b>\n<i>(Masalan: 2024)</i>", parse_mode="HTML")
    await state.set_state(AddMovieState.year)

@dp.message(AddMovieState.year)
async def add_movie_year(message: types.Message, state: FSMContext):
    await state.update_data(year=message.text.strip())
    await message.answer("🔢 <b>Kino uchun kod kiriting:</b>\n<i>(Masalan: 105)</i>", parse_mode="HTML")
    await state.set_state(AddMovieState.code)

@dp.message(AddMovieState.code)
async def add_movie_code(message: types.Message, state: FSMContext):
    code = message.text.strip()
    if code in db["movies"]:
        await message.answer("❌ Bu kod band! Boshqa kod yozing:")
        return
    await state.update_data(code=code)
    await message.answer("📹 <b>Endi kinoning video faylini yuboring:</b>", parse_mode="HTML")
    await state.set_state(AddMovieState.video)

@dp.message(AddMovieState.video)
async def add_movie_video(message: types.Message, state: FSMContext):
    if not message.video:
        await message.answer("⚠️ Iltimos, faqat video yuboring!")
        return
    data = await state.get_data()
    code = data["code"]
    db["movies"][code] = {
        "title": data["title"],
        "genre": data["genre"],
        "year": data["year"],
        "video_id": message.video.file_id,
        "views": 0
    }
    save_db()
    await state.clear()
    await message.answer(
        f"✅ <b>Kino bazaga qo'shildi!</b>\n\n"
        f"🎬 Nomi: <b>{data['title']}</b>\n"
        f"🎭 Janri: {data['genre']}\n"
        f"📅 Yili: {data['year']}\n"
        f"🔢 Kodi: <code>{code}</code>",
        reply_markup=admin_menu(),
        parse_mode="HTML"
    )
    await send_backup_to_admin(f"📦 Yangi kino qo'shildi: {data['title']} (Kod: {code})")

@dp.message(F.text == "🗑 Kino o'chirish")
async def del_movie_start(message: types.Message, state: FSMContext):
    if message.from_user.id not in db["admins"]:
        return
    await message.answer("🗑 O'chirmoqchi bo'lgan kino kodini yuboring:", reply_markup=cancel_kb)
    await state.set_state(DelMovieState.code)

@dp.message(DelMovieState.code)
async def del_movie_confirm(message: types.Message, state: FSMContext):
    code = message.text.strip()
    if code in db["movies"]:
        title = db["movies"][code]["title"]
        del db["movies"][code]
        save_db()
        await message.answer(f"✅ <b>{title}</b> ({code}) bazadan o'chirildi!", reply_markup=admin_menu(), parse_mode="HTML")
        await send_backup_to_admin(f"🗑 Kino o'chirildi: {code}")
    else:
        await message.answer("❌ Bunday kodli kino topilmadi.", reply_markup=admin_menu())
    await state.clear()

@dp.message(F.text == "📋 Kinolar ro'yxati")
async def list_movies(message: types.Message):
    if message.from_user.id not in db["admins"]:
        return
    if not db["movies"]:
        await message.answer("📭 Bazada kinolar yo'q.")
        return
    text = "📋 <b>Barcha kinolar ro'yxati:</b>\n\n"
    for code, m in db["movies"].items():
        text += f"• <code>{code}</code> — <b>{m['title']}</b> ({m.get('year', '')}) | 👁 {m.get('views', 0)}\n"
    await message.answer(text[:4000], parse_mode="HTML")

# ================= ADMIN: KANALLAR BOSHQARUVI =================
@dp.message(F.text == "📢 Kanallar")
async def manage_channels(message: types.Message):
    if message.from_user.id not in db["admins"]:
        return
    chs = "\n".join([f"• <code>{c}</code>" for c in db["channels"]]) or "Yo'q"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Kanal qo'shish", callback_data="ch_add"),
         InlineKeyboardButton(text="➖ Kanal o'chirish", callback_data="ch_del")]
    ])
    await message.answer(f"📢 <b>Majburiy obuna kanallari:</b>\n\n{chs}", reply_markup=kb, parse_mode="HTML")

@dp.callback_query(F.data == "ch_add")
async def ch_add_cb(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("📢 Kanal username'ini yuboring (masalan: <code>@FORTIS_OKTO</code>):", reply_markup=cancel_kb, parse_mode="HTML")
    await state.set_state(ChannelState.add)

@dp.message(ChannelState.add)
async def ch_add_save(message: types.Message, state: FSMContext):
    ch = message.text.strip()
    if not ch.startswith("@"):
        ch = "@" + ch
    if ch not in db["channels"]:
        db["channels"].append(ch)
        save_db()
    await state.clear()
    await message.answer(f"✅ <b>{ch}</b> majburiy obunaga qo'shildi!\n⚠️ Botni u kanalda Admin qilishni unutmang.", reply_markup=admin_menu(), parse_mode="HTML")

@dp.callback_query(F.data == "ch_del")
async def ch_del_cb(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("🗑 O'chiriladigan kanal username'ini yuboring:", reply_markup=cancel_kb)
    await state.set_state(ChannelState.remove)

@dp.message(ChannelState.remove)
async def ch_del_save(message: types.Message, state: FSMContext):
    ch = message.text.strip()
    if ch in db["channels"]:
        db["channels"].remove(ch)
        save_db()
        await message.answer(f"🗑 <b>{ch}</b> ro'yxatdan o'chirildi.", reply_markup=admin_menu(), parse_mode="HTML")
    else:
        await message.answer("❌ Bunday kanal topilmadi.", reply_markup=admin_menu())
    await state.clear()

# ================= ADMIN: ADMINLAR VA XABAR TARQATISH =================
@dp.message(F.text == "👤 Adminlar")
async def manage_admins(message: types.Message):
    if message.from_user.id not in db["admins"]:
        return
    adm = "\n".join([f"• <code>{a}</code>" for a in db["admins"]])
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Admin qo'shish", callback_data="adm_add"),
         InlineKeyboardButton(text="➖ Admin o'chirish", callback_data="adm_del")]
    ])
    await message.answer(f"👤 <b>Bot adminlari:</b>\n\n{adm}", reply_markup=kb, parse_mode="HTML")

@dp.callback_query(F.data == "adm_add")
async def adm_add_cb(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Yangi admin Telegram ID raqamini yuboring:", reply_markup=cancel_kb)
    await state.set_state(AdminState.add)

@dp.message(AdminState.add)
async def adm_add_save(message: types.Message, state: FSMContext):
    if message.text.strip().isdigit():
        new_id = int(message.text.strip())
        if new_id not in db["admins"]:
            db["admins"].append(new_id)
            save_db()
        await message.answer(f"✅ <code>{new_id}</code> admin qilindi!", reply_markup=admin_menu(), parse_mode="HTML")
    else:
        await message.answer("❌ Faqat raqamli ID yuboring.", reply_markup=admin_menu())
    await state.clear()

@dp.callback_query(F.data == "adm_del")
async def adm_del_cb(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("O'chiriladigan admin ID raqamini yuboring:", reply_markup=cancel_kb)
    await state.set_state(AdminState.remove)

@dp.message(AdminState.remove)
async def adm_del_save(message: types.Message, state: FSMContext):
    if message.text.strip().isdigit():
        rem_id = int(message.text.strip())
        if rem_id == MAIN_ADMIN_ID:
            await message.answer("❌ Asosiy adminni o'chirib bo'lmaydi!", reply_markup=admin_menu())
        elif rem_id in db["admins"]:
            db["admins"].remove(rem_id)
            save_db()
            await message.answer(f"🗑 <code>{rem_id}</code> adminlikdan olindi.", reply_markup=admin_menu(), parse_mode="HTML")
    await state.clear()

@dp.message(F.text == "📨 Xabar tarqatish")
async def broadcast_start(message: types.Message, state: FSMContext):
    if message.from_user.id not in db["admins"]:
        return
    await message.answer("📨 Barcha foydalanuvchilarga yuboriladigan xabarni (matn, rasm yoki video) yuboring:", reply_markup=cancel_kb)
    await state.set_state(BroadcastState.message)

@dp.message(BroadcastState.message)
async def broadcast_send(message: types.Message, state: FSMContext):
    await state.clear()
    sent, failed = 0, 0
    status_msg = await message.answer("⏳ Xabar tarqatilmoqda...")
    for uid in db["users"]:
        try:
            await message.copy_to(chat_id=uid)
            sent += 1
            await asyncio.sleep(0.05)
        except Exception:
            failed += 1
    await status_msg.delete()
    await message.answer(
        f"✅ <b>Xabar tarqatish yakunlandi!</b>\n\n"
        f"📬 Yetib bordi: <b>{sent}</b> ta\n"
        f"❌ Yetib bormadi: <b>{failed}</b> ta",
        reply_markup=admin_menu(),
        parse_mode="HTML"
    )

# ================= ADMIN: BAZANI SAQLASH VA TIKLASH =================
@dp.message(F.text == "📦 Bazani olish")
async def manual_backup(message: types.Message):
    if message.from_user.id not in db["admins"]:
        return
    await send_backup_to_admin("📦 Qo'lda olingan baza nusxasi")

@dp.message(F.text == "📥 Bazani tiklash")
async def restore_db_start(message: types.Message, state: FSMContext):
    if message.from_user.id not in db["admins"]:
        return
    await message.answer("📥 Oldin saqlangan <b>database.json</b> faylini shu yerga yuboring:", reply_markup=cancel_kb, parse_mode="HTML")
    await state.set_state(RestoreDBState.file)

@dp.message(RestoreDBState.file, F.document)
async def restore_db_process(message: types.Message, state: FSMContext):
    global db
    try:
        file_info = await bot.get_file(message.document.file_id)
        await bot.download_file(file_info.file_path, DB_FILE)
        db = load_db()
        await state.clear()
        await message.answer(
      
