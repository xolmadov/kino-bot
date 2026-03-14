import asyncio
import json
import os
from dotenv import load_dotenv
load_dotenv()

from aiogram import Bot, Dispatcher, types, F
from aiogram.enums import ParseMode
from aiogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import State, StatesGroup
from aiogram.client.default import DefaultBotProperties

# ============================================================
# SOZLAMALAR — shu yerda o'zgartiring
# ============================================================
TOKEN = os.getenv("BOT_TOKEN", "8610997909:AAE43YuVZDWbK-3NsrcAXVdS_dac7FuHeRU")

# CHANNEL_ID ni qanday topasiz:
# 1. @username_to_id_bot ga kanalingizni forward qiling
# 2. Yoki botni kanalga admin qiling va https://api.telegram.org/bot<TOKEN>/getUpdates dan toping
# Misol: -1001234567890  (manfiy raqam, 100... bilan boshlanadi)
CHANNEL_ID = --1002554275258  # <-- O'ZGARTIRING

CHANNEL_LINK = "https://t.me/+55LGlhaAD7A2MTY6"  # <-- O'ZGARTIRING

ADMIN_ID = 7752032178  # <-- O'ZGARTIRING (o'z Telegram ID'ingiz)
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "itachi201028")  # <-- O'ZGARTIRING

# ============================================================

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())

# -------- Admin tugmalari --------
admin_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🎬 Kino qo'shish")],
        [KeyboardButton(text="📁 Barcha kinolar"), KeyboardButton(text="🗑 Kino o'chirish")],
        [KeyboardButton(text="📊 Statistika"), KeyboardButton(text="🚪 Chiqish")],
    ],
    resize_keyboard=True
)

# -------- Ma'lumotlar fayli --------
DATA_FILE = "data.json"
STATS_FILE = "stats.json"
data_lock = asyncio.Lock()

async def load_data() -> dict:
    async with data_lock:
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

async def save_data(data: dict):
    async with data_lock:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

async def load_stats() -> dict:
    try:
        with open(STATS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"users": [], "requests": 0}

async def save_stats(stats: dict):
    with open(STATS_FILE, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=4)

async def track_user(user_id: int):
    stats = await load_stats()
    if user_id not in stats["users"]:
        stats["users"].append(user_id)
    stats["requests"] = stats.get("requests", 0) + 1
    await save_stats(stats)

# -------- FSM holatlari --------
class AdminFSM(StatesGroup):
    waiting_for_password = State()   # Admin parol kiritmagan
    idle = State()                    # Admin kirdi, menyu ko'rsatilgan
    waiting_for_video = State()       # Kino yuklanishini kutmoqda
    waiting_for_code = State()        # Kino kodi kiritilishini kutmoqda
    waiting_for_delete = State()      # O'chirilajak kod kutilmoqda

class UserFSM(StatesGroup):
    waiting_for_movie_code = State()  # Foydalanuvchi kod kiritmoqda

# -------- Kanal tekshiruvi --------
async def is_subscribed(user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status in ("member", "administrator", "creator")
    except Exception as e:
        print(f"[XATO] Kanal tekshiruvda xato: {e}")
        # Agar kanal topilmasa yoki bot admin bo'lmasa xato chiqadi
        # Bu holda False qaytaradi — botni kanalga admin qiling!
        return False

# ============================================================
# /start komandasi
# ============================================================
@dp.message(F.text == "/start")
async def start_cmd(message: Message, state: FSMContext):
    user_id = message.from_user.id

    if user_id == ADMIN_ID:
        current = await state.get_state()
        if current not in [AdminFSM.idle, AdminFSM.waiting_for_video,
                           AdminFSM.waiting_for_code, AdminFSM.waiting_for_delete]:
            await message.answer(
                "🔐 <b>Admin paneliga xush kelibsiz!</b>\n\nParolni kiriting:",
                reply_markup=ReplyKeyboardRemove()
            )
            await state.set_state(AdminFSM.waiting_for_password)
        else:
            await message.answer("✅ Siz allaqachon admin sifatida kirgansiz.", reply_markup=admin_keyboard)
        return

    # Foydalanuvchi
    await track_user(user_id)

    if await is_subscribed(user_id):
        await message.answer(
            "🎬 <b>Kino botiga xush kelibsiz!</b>\n\n"
            "Kino parolini kiriting va film yuboriladi:"
        )
        await state.set_state(UserFSM.waiting_for_movie_code)
    else:
        await show_subscribe_message(message)

async def show_subscribe_message(message: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Kanalga obuna bo'lish", url=CHANNEL_LINK)],
        [InlineKeyboardButton(text="✅ Tekshirish", callback_data="check_sub")]
    ])
    await message.answer(
        "⚠️ <b>Kino ko'rish uchun kanalga obuna bo'lishingiz shart!</b>\n\n"
        f"👉 {CHANNEL_LINK}\n\n"
        "Obuna bo'lgach, <b>✅ Tekshirish</b> tugmasini bosing.",
        reply_markup=kb
    )

# ============================================================
# Obuna tekshirish (callback)
# ============================================================
@dp.callback_query(F.data == "check_sub")
async def check_subscription(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id

    if await is_subscribed(user_id):
        await callback.message.edit_text(
            "✅ <b>Obuna tasdiqlandi!</b>\n\nEndi kino parolini kiriting:"
        )
        await state.set_state(UserFSM.waiting_for_movie_code)
    else:
        await callback.answer(
            "❌ Hali obuna bo'lmagansiz! Avval kanalga obuna bo'ling.",
            show_alert=True
        )

# ============================================================
# ADMIN — Parol kiritish
# ============================================================
@dp.message(AdminFSM.waiting_for_password, F.text)
async def admin_login(message: Message, state: FSMContext):
    if message.text.strip() == ADMIN_PASSWORD:
        await message.answer(
            "✅ <b>Xush kelibsiz, Admin!</b>\n\nQuyidagi amallardan birini tanlang:",
            reply_markup=admin_keyboard
        )
        await state.set_state(AdminFSM.idle)
    else:
        await message.answer("❌ Noto'g'ri parol! Qaytadan urinib ko'ring.")

# ============================================================
# ADMIN — Kino qo'shish
# ============================================================
@dp.message(F.text == "🎬 Kino qo'shish")
async def admin_add_movie(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer(
        "🎥 <b>Kino faylini yuboring.</b>\n\n"
        "⚠️ Fayl formatida (Document) yuboring — yuqori sifat saqlanadi!",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.set_state(AdminFSM.waiting_for_video)

# Video yoki Document qabul qilish
@dp.message(AdminFSM.waiting_for_video, F.video | F.document)
async def admin_receive_video(message: Message, state: FSMContext):
    if message.video:
        file_id = message.video.file_id
        ftype = "video"
    else:
        file_id = message.document.file_id
        ftype = "document"

    await state.update_data(file_id=file_id, file_type=ftype)
    await message.answer(
        "🔑 <b>Kino uchun parol/kod kiriting:</b>\n\n"
        "Masalan: <code>spiderman2024</code> yoki <code>001</code>"
    )
    await state.set_state(AdminFSM.waiting_for_code)

@dp.message(AdminFSM.waiting_for_video)
async def admin_wrong_file(message: Message):
    await message.answer("⚠️ Iltimos, video yoki fayl yuboring!")

# Kod kiritish va saqlash
@dp.message(AdminFSM.waiting_for_code, F.text)
async def admin_save_movie(message: Message, state: FSMContext):
    code = message.text.strip().lower()

    if not code or len(code) > 30:
        await message.answer("❌ Parol noto'g'ri. 1-30 ta belgi bo'lishi kerak.")
        return

    all_data = await load_data()

    if code in all_data:
        await message.answer(
            f"⚠️ <b>'{code}'</b> kodi allaqachon mavjud!\n"
            "Boshqa kod kiriting yoki avval eskisini o'chiring."
        )
        return

    data = await state.get_data()
    all_data[code] = {
        "file_id": data["file_id"],
        "type": data.get("file_type", "video")
    }
    await save_data(all_data)

    await message.answer(
        f"✅ <b>Kino saqlandi!</b>\n\n"
        f"🔑 Kodi: <code>{code}</code>\n\n"
        "Yana kino qo'shish uchun qaytadan yuboring:",
        reply_markup=admin_keyboard
    )
    await state.set_state(AdminFSM.idle)

# ============================================================
# ADMIN — Barcha kinolar
# ============================================================
@dp.message(F.text == "📁 Barcha kinolar")
async def kino_list(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    data = await load_data()
    if data:
        kinolar = "\n".join([f"🔑 <code>{k}</code>" for k in data.keys()])
        await message.answer(
            f"🎞 <b>Mavjud kinolar ({len(data)} ta):</b>\n\n{kinolar}"
        )
    else:
        await message.answer("🚫 Hozircha hech qanday kino yo'q.")

# ============================================================
# ADMIN — Kino o'chirish
# ============================================================
@dp.message(F.text == "🗑 Kino o'chirish")
async def admin_delete_start(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    data = await load_data()
    if not data:
        await message.answer("🚫 O'chiriladigan kino yo'q.")
        return
    kinolar = "\n".join([f"• <code>{k}</code>" for k in data.keys()])
    await message.answer(
        f"🗑 <b>O'chiriladigan kino kodini kiriting:</b>\n\n{kinolar}",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.set_state(AdminFSM.waiting_for_delete)

@dp.message(AdminFSM.waiting_for_delete, F.text)
async def admin_delete_movie(message: Message, state: FSMContext):
    code = message.text.strip().lower()
    data = await load_data()

    if code in data:
        del data[code]
        await save_data(data)
        await message.answer(
            f"✅ <b>'{code}'</b> kodi o'chirildi!",
            reply_markup=admin_keyboard
        )
    else:
        await message.answer(
            f"❌ <b>'{code}'</b> kodi topilmadi.",
            reply_markup=admin_keyboard
        )
    await state.set_state(AdminFSM.idle)

# ============================================================
# ADMIN — Statistika
# ============================================================
@dp.message(F.text == "📊 Statistika")
async def statistika(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    data = await load_data()
    stats = await load_stats()
    await message.answer(
        f"📊 <b>Statistika:</b>\n\n"
        f"🎬 Kinolar soni: <b>{len(data)}</b>\n"
        f"👤 Foydalanuvchilar: <b>{len(stats.get('users', []))}</b>\n"
        f"📥 Jami so'rovlar: <b>{stats.get('requests', 0)}</b>"
    )

# ============================================================
# ADMIN — Chiqish
# ============================================================
@dp.message(F.text == "🚪 Chiqish")
async def admin_logout(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    await state.clear()
    await message.answer("👋 Admin paneldan chiqdingiz.", reply_markup=ReplyKeyboardRemove())

# ============================================================
# FOYDALANUVCHI — Kino kodi kiritish
# ============================================================
@dp.message(UserFSM.waiting_for_movie_code, F.text)
async def user_enter_code(message: Message, state: FSMContext):
    user_id = message.from_user.id

    # Obunani yana tekshiramiz
    if not await is_subscribed(user_id):
        await show_subscribe_message(message)
        await state.clear()
        return

    code = message.text.strip().lower()
    data = await load_data()

    if code in data:
        movie = data[code]
        file_id = movie["file_id"] if isinstance(movie, dict) else movie
        ftype = movie.get("type", "video") if isinstance(movie, dict) else "video"

        try:
            if ftype == "document":
                await message.answer_document(
                    file_id,
                    caption="🎬 <b>Mana siz so'ragan kino!</b>\n\nBoshqa kino uchun kodni kiriting:"
                )
            else:
                await message.answer_video(
                    file_id,
                    caption="🎬 <b>Mana siz so'ragan kino!</b>\n\nBoshqa kino uchun kodni kiriting:"
                )
        except Exception as e:
            print(f"[XATO] Fayl yuborishda: {e}")
            await message.answer("❌ Kino yuborishda xato yuz berdi. Admin bilan bog'laning.")
    else:
        await message.answer(
            f"❌ <b>'{code}'</b> kodi topilmadi.\n\n"
            "Iltimos, to'g'ri kodni kiriting yoki admin bilan bog'laning."
        )

# ============================================================
# Boshqa xabarlar (holatga qarab)
# ============================================================
@dp.message(F.text)
async def handle_text(message: Message, state: FSMContext):
    user_id = message.from_user.id
    current_state = await state.get_state()

    # Admin tugmalari holatida
    if user_id == ADMIN_ID and current_state is None:
        await message.answer(
            "ℹ️ /start buyrug'ini yuboring yoki admin paneliga kiring.",
        )
        return

    # Oddiy foydalanuvchi uchun
    if current_state is None:
        if await is_subscribed(user_id):
            await message.answer("🔑 Kino kodini kiriting:")
            await state.set_state(UserFSM.waiting_for_movie_code)
        else:
            await show_subscribe_message(message)

# ============================================================
# Botni ishga tushirish
# ============================================================
async def main():
    print("🚀 Bot ishga tushdi!")
    print(f"📢 Kanal ID: {CHANNEL_ID}")
    print(f"👤 Admin ID: {ADMIN_ID}")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

