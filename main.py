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

# -------- Sozlamalar --------
TOKEN = os.getenv("BOT_TOKEN", "8293177634:AAE_-9we0HKtTv8xVX8TCNq3bYRKzWHS0UI")
CHANNEL_ID = -1003135489170
CHANNEL_USERNAME = "https://t.me/+gnVLA0l9roNkM2Yy"
CHANNEL_LINK = f"https://t.me/{CHANNEL_USERNAME}"
ADMIN_ID = 7752032178
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "superadmin123")

# -------- Bot va dispatcher --------
bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())

# -------- Admin tugmalar --------
admin_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📁 Barcha kinolar"), KeyboardButton(text="📊 Statistika")]
    ],
    resize_keyboard=True
)

# -------- Kino ma’lumotlari fayli --------
DATA_FILE = "data.json"
data_lock = asyncio.Lock()

async def load_data():
    async with data_lock:
        try:
            with open(DATA_FILE, "r") as f:
                return json.load(f)
        except:
            return {}

async def save_data(data):
    async with data_lock:
        with open(DATA_FILE, "w") as f:
            json.dump(data, f, indent=4)

# -------- FSM --------
class AdminFSM(StatesGroup):
    login = State()
    waiting_for_video = State()
    waiting_for_password = State()

# -------- Kanalga a’zo bo‘lganmi tekshiruvchi funksiya --------
async def is_subscribed(user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status in ("member", "administrator", "creator")
    except:
        return False

# -------- /start --------
@dp.message(F.text == "/start")
async def start_cmd(message: Message, state: FSMContext):
    if message.from_user.id == ADMIN_ID:
        await message.answer("🔐 Admin parolni kiriting:", reply_markup=ReplyKeyboardRemove())
        await state.set_state(AdminFSM.login)
    else:
        if await is_subscribed(message.from_user.id):
            await message.answer("🔑 Kino parolini kiriting:")
        else:
            button = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📢 Kanalga obuna bo‘lish", url=CHANNEL_LINK)],
                [InlineKeyboardButton(text="✅ Obuna bo‘ldim", callback_data="check_sub")]
            ])
            await message.answer(
                "📢 <b>Kino ko‘rish uchun kanalga obuna bo‘ling:</b>\n"
                f"👉 {CHANNEL_LINK}",
                reply_markup=button
            )

# -------- Obunani tekshirish (callback) --------
@dp.callback_query(F.data == "check_sub")
async def check_subscription(callback: types.CallbackQuery):
    if await is_subscribed(callback.from_user.id):
        await callback.message.edit_text("✅ Obuna tasdiqlandi! Endi kino parolini kiriting.")
    else:
        await callback.answer("❌ Hali obuna bo‘lmagansiz!", show_alert=True)

# -------- Admin login --------
@dp.message(AdminFSM.login, F.text)
async def admin_login(message: Message, state: FSMContext):
    if message.text.strip() == ADMIN_PASSWORD:
        await message.answer("✅ Xush kelibsiz, admin!", reply_markup=admin_keyboard)
        await state.set_state(AdminFSM.waiting_for_video)
    else:
        await message.answer("❌ Noto‘g‘ri parol. Qaytadan urinib ko‘ring.")

# -------- Video qabul qilish --------
@dp.message(AdminFSM.waiting_for_video, F.video)
async def admin_video(message: Message, state: FSMContext):
    await state.update_data(video_id=message.video.file_id)
    await message.answer("🔑 Kino uchun parol kiriting:")
    await state.set_state(AdminFSM.waiting_for_password)

# -------- Kino va parolni saqlash --------
@dp.message(AdminFSM.waiting_for_password, F.text)
async def admin_password(message: Message, state: FSMContext):
    password = message.text.strip().lower()
    data = await state.get_data()
    video_id = data["video_id"]

    all_data = await load_data()
    all_data[password] = video_id
    await save_data(all_data)

    await message.answer("✅ Kino saqlandi yana kino kitshingz mumkun!", reply_markup=admin_keyboard)
    await state.set_state(AdminFSM.waiting_for_video)

# -------- Kino ro‘yxati --------
@dp.message(F.text == "📁 Barcha kinolar")
async def kino_list(message: Message):
    data = await load_data()
    if data:
        kinolar = "\n".join([f"🔑 {k}" for k in data.keys()])
        await message.answer(f"🎞 Mavjud kinolar:\n{kinolar}")
    else:
        await message.answer("🚫 Hozircha kino yo‘q.")

# -------- Statistika --------
@dp.message(F.text == "📊 Statistika")
async def statistika(message: Message):
    data = await load_data()
    await message.answer(f"📊 Kinolar soni: <b>{len(data)}</b>")

# -------- Foydalanuvchi parol kiritadi --------
@dp.message(F.text)
async def user_password(message: Message):
    if not await is_subscribed(message.from_user.id):
        await message.answer(
            "❌ Siz hali kanalga obuna bo‘lmagansiz kanlga obuna boling.\n"
            f"👉 {CHANNEL_LINK}"
        )
        return

    password = message.text.strip().lower()
    data = await load_data()

    if password in data:
        await message.answer_video(data[password], caption="🎬 Mana siz so‘ragan kino!")
    else:
        await message.answer("❌ BU parol hizirda mavjyd emas boshqa prol kirtng.")

# -------- Botni ishga tushirish --------
async def main():
    print("🚀 Bot ishga tushdi!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
