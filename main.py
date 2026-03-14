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
# SOZLAMALAR
# ============================================================
TOKEN = os.getenv("BOT_TOKEN", "8610997909:AAE43YuVZDWbK-3NsrcAXVdS_dac7FuHeRU")
 
ADMIN_ID = 6292545074
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "itachi201028")
 
# ============================================================
# KANAL SOZLAMALARI
# Kino ko'rish uchun obuna talab qilinadigan kanallar
# Bo'sh qoldiring agar obuna talab qilmasangiz: CHANNELS = []
# Admin panel orqali ham qo'shish mumkin (maksimal 10 ta)
# ============================================================
CHANNELS = []
 
# ============================================================
 
bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())
 
# -------- Admin tugmalari --------
admin_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🎬 Kino qo'shish")],
        [KeyboardButton(text="📁 Barcha kinolar"), KeyboardButton(text="🗑 Kino o'chirish")],
        [KeyboardButton(text="📢 Kanal qo'shish"), KeyboardButton(text="📋 Kanallar ro'yxati")],
        [KeyboardButton(text="📊 Statistika"), KeyboardButton(text="📣 Xabar yuborish")],
        [KeyboardButton(text="🚪 Chiqish")],
    ],
    resize_keyboard=True
)
 
# -------- Fayllar --------
DATA_FILE = "data.json"
STATS_FILE = "stats.json"
CHANNELS_FILE = "channels.json"
data_lock = asyncio.Lock()
 
# -------- Ma'lumot yuklash/saqlash --------
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
 
async def load_channels() -> list:
    """Dinamik kanallarni fayldan yuklaydi"""
    try:
        with open(CHANNELS_FILE, "r", encoding="utf-8") as f:
            saved = json.load(f)
        all_channels = list(CHANNELS)
        for ch in saved:
            if not any(c["id"] == ch["id"] for c in all_channels):
                all_channels.append(ch)
        return all_channels
    except Exception:
        return list(CHANNELS)
 
async def save_channels(channels: list):
    with open(CHANNELS_FILE, "w", encoding="utf-8") as f:
        json.dump(channels, f, indent=4, ensure_ascii=False)
 
async def track_user(user_id: int):
    stats = await load_stats()
    if user_id not in stats["users"]:
        stats["users"].append(user_id)
    stats["requests"] = stats.get("requests", 0) + 1
    await save_stats(stats)
 
# -------- FSM holatlari --------
class AdminFSM(StatesGroup):
    waiting_for_password = State()
    idle = State()
    waiting_for_video = State()
    waiting_for_title = State()
    waiting_for_code = State()
    waiting_for_delete = State()
    waiting_for_channel = State()
    waiting_for_broadcast = State()
 
class UserFSM(StatesGroup):
    waiting_for_movie_code = State()
 
# -------- Kanal obunasini tekshirish --------
async def check_subscriptions(user_id: int) -> list:
    """Obuna bo'lmagan kanallar ro'yxatini qaytaradi"""
    channels = await load_channels()
    if not channels:
        return []  # Kanal yo'q — barchaga ruxsat
 
    not_subscribed = []
    for ch in channels:
        try:
            member = await bot.get_chat_member(chat_id=ch["id"], user_id=user_id)
            if member.status not in ("member", "administrator", "creator"):
                not_subscribed.append(ch)
        except Exception as e:
            print(f"[XATO] Kanal {ch['id']} tekshirishda: {e}")
            not_subscribed.append(ch)
    return not_subscribed
 
async def show_subscribe_message(message: Message, not_subscribed: list):
    buttons = []
    for ch in not_subscribed:
        buttons.append([InlineKeyboardButton(text=f"📢 {ch['name']}", url=ch["link"])])
    buttons.append([InlineKeyboardButton(text="✅ Obuna bo'ldim, tekshirish", callback_data="check_sub")])
 
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    channels_text = "\n".join([f"• <a href='{ch['link']}'>{ch['name']}</a>" for ch in not_subscribed])
 
    await message.answer(
        "⚠️ <b>Kino ko'rish uchun quyidagi kanallarga obuna bo'ling:</b>\n\n"
        f"{channels_text}\n\n"
        "Obuna bo'lgach, <b>✅ Tekshirish</b> tugmasini bosing.",
        reply_markup=kb,
        disable_web_page_preview=True
    )
 
# ============================================================
# /start
# ============================================================
@dp.message(F.text == "/start")
async def start_cmd(message: Message, state: FSMContext):
    user_id = message.from_user.id
 
    if user_id == ADMIN_ID:
        current = await state.get_state()
        admin_states = [
            AdminFSM.idle, AdminFSM.waiting_for_video, AdminFSM.waiting_for_title,
            AdminFSM.waiting_for_code, AdminFSM.waiting_for_delete,
            AdminFSM.waiting_for_channel, AdminFSM.waiting_for_broadcast
        ]
        if current not in [str(s) for s in admin_states]:
            await message.answer(
                "🔐 <b>Admin paneliga xush kelibsiz!</b>\n\nParolni kiriting:",
                reply_markup=ReplyKeyboardRemove()
            )
            await state.set_state(AdminFSM.waiting_for_password)
        else:
            await message.answer("✅ Admin sifatida kirgansiz.", reply_markup=admin_keyboard)
        return
 
    await track_user(user_id)
    not_subscribed = await check_subscriptions(user_id)
 
    if not_subscribed:
        await show_subscribe_message(message, not_subscribed)
    else:
        await message.answer(
            "🎬 <b>Kino botiga xush kelibsiz!</b>\n\n"
            "🔑 Kino kodini kiriting va film yuboriladi:"
        )
        await state.set_state(UserFSM.waiting_for_movie_code)
 
# ============================================================
# Obuna tekshirish callback
# ============================================================
@dp.callback_query(F.data == "check_sub")
async def check_subscription_cb(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    not_subscribed = await check_subscriptions(user_id)
 
    if not not_subscribed:
        await callback.message.edit_text(
            "✅ <b>Obuna tasdiqlandi!</b>\n\n🔑 Kino kodini kiriting:"
        )
        await state.set_state(UserFSM.waiting_for_movie_code)
    else:
        names = ", ".join([ch["name"] for ch in not_subscribed])
        await callback.answer(
            f"❌ Hali obuna bo'lmagansiz!\nQolganlar: {names}",
            show_alert=True
        )
 
# ============================================================
# ADMIN — Parol
# ============================================================
@dp.message(AdminFSM.waiting_for_password, F.text)
async def admin_login(message: Message, state: FSMContext):
    if message.text.strip() == ADMIN_PASSWORD:
        await message.answer(
            "✅ <b>Xush kelibsiz, Admin!</b>\n\nAmalni tanlang:",
            reply_markup=admin_keyboard
        )
        await state.set_state(AdminFSM.idle)
    else:
        await message.answer("❌ Noto'g'ri parol!")
 
# ============================================================
# ADMIN — Kino qo'shish
# ============================================================
@dp.message(F.text == "🎬 Kino qo'shish")
async def admin_add_movie(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer(
        "🎥 <b>Kino faylini yuboring.</b>\n\n"
        "💡 Fayl (Document) formatida yuboring — sifat saqlanadi!",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.set_state(AdminFSM.waiting_for_video)
 
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
        "✏️ <b>Kino nomini kiriting:</b>\n\n"
        "Masalan: <code>Spider-Man: No Way Home</code>"
    )
    await state.set_state(AdminFSM.waiting_for_title)
 
@dp.message(AdminFSM.waiting_for_video)
async def admin_wrong_file(message: Message):
    await message.answer("⚠️ Iltimos, video yoki fayl yuboring!")
 
@dp.message(AdminFSM.waiting_for_title, F.text)
async def admin_receive_title(message: Message, state: FSMContext):
    title = message.text.strip()
    if len(title) > 100:
        await message.answer("❌ Nom juda uzun. 100 belgidan kam bo'lsin.")
        return
    await state.update_data(title=title)
    await message.answer(
        "🔑 <b>Kino uchun kod kiriting:</b>\n\n"
        "Masalan: <code>spiderman</code> yoki <code>001</code>"
    )
    await state.set_state(AdminFSM.waiting_for_code)
 
@dp.message(AdminFSM.waiting_for_code, F.text)
async def admin_save_movie(message: Message, state: FSMContext):
    code = message.text.strip().lower()
 
    if not code or len(code) > 30:
        await message.answer("❌ Kod 1-30 belgi bo'lishi kerak.")
        return
 
    all_data = await load_data()
    if code in all_data:
        await message.answer(f"⚠️ <b>'{code}'</b> kodi mavjud! Boshqa kod kiriting.")
        return
 
    data = await state.get_data()
    all_data[code] = {
        "file_id": data["file_id"],
        "type": data.get("file_type", "video"),
        "title": data.get("title", "Nomsiz kino")
    }
    await save_data(all_data)
 
    await message.answer(
        f"✅ <b>Kino saqlandi!</b>\n\n"
        f"🎬 Nomi: <b>{data.get('title', 'Nomsiz')}</b>\n"
        f"🔑 Kodi: <code>{code}</code>",
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
    if not data:
        await message.answer("🚫 Hozircha hech qanday kino yo'q.")
        return
 
    kinolar = "\n".join([
        f"🔑 <code>{k}</code> — 🎬 {v.get('title', 'Nomsiz') if isinstance(v, dict) else 'Nomsiz'}"
        for k, v in data.items()
    ])
    await message.answer(f"🎞 <b>Mavjud kinolar ({len(data)} ta):</b>\n\n{kinolar}")
 
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
 
    kinolar = "\n".join([
        f"• <code>{k}</code> — {v.get('title', 'Nomsiz') if isinstance(v, dict) else 'Nomsiz'}"
        for k, v in data.items()
    ])
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
        title = data[code].get("title", "Nomsiz") if isinstance(data[code], dict) else "Nomsiz"
        del data[code]
        await save_data(data)
        await message.answer(f"✅ <b>'{title}'</b> ({code}) o'chirildi!", reply_markup=admin_keyboard)
    else:
        await message.answer(f"❌ <b>'{code}'</b> kodi topilmadi.", reply_markup=admin_keyboard)
    await state.set_state(AdminFSM.idle)
 
# ============================================================
# ADMIN — Kanal qo'shish
# ============================================================
@dp.message(F.text == "📢 Kanal qo'shish")
async def admin_add_channel_start(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer(
        "📢 <b>Kanal ma'lumotlarini kiriting:</b>\n\n"
        "Format:\n"
        "<code>-1001234567890 | https://t.me/kanal | Kanal nomi</code>\n\n"
        "⚠️ Botni kanalga <b>admin</b> qilib qo'ying!\n"
        "🆔 ID topish: @username_to_id_bot",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.set_state(AdminFSM.waiting_for_channel)
 
@dp.message(AdminFSM.waiting_for_channel, F.text)
async def admin_save_channel(message: Message, state: FSMContext):
    try:
        parts = [p.strip() for p in message.text.split("|")]
        if len(parts) != 3:
            raise ValueError("Format noto'g'ri")
 
        channel_id = int(parts[0])
        channel_link = parts[1]
        channel_name = parts[2]
 
        if not channel_link.startswith("https://t.me/"):
            raise ValueError("Link noto'g'ri")
 
        channels = await load_channels()
 
        if len(channels) >= 10:
            await message.answer(
                "❌ Maksimal 10 ta kanal qo'shish mumkin!\n"
                "Avval eski kanallardan birini o'chiring.",
                reply_markup=admin_keyboard
            )
            await state.set_state(AdminFSM.idle)
            return
 
        if any(c["id"] == channel_id for c in channels):
            await message.answer("⚠️ Bu kanal allaqachon qo'shilgan!", reply_markup=admin_keyboard)
            await state.set_state(AdminFSM.idle)
            return
 
        # Bot admin ekanligini tekshirish
        try:
            me = await bot.get_me()
            member = await bot.get_chat_member(chat_id=channel_id, user_id=me.id)
            if member.status not in ("administrator", "creator"):
                await message.answer(
                    "❌ Bot bu kanalda admin emas!\n"
                    "Botni kanalga admin qilib, qaytadan urinib ko'ring.",
                    reply_markup=admin_keyboard
                )
                await state.set_state(AdminFSM.idle)
                return
        except Exception as e:
            await message.answer(
                f"❌ Kanal topilmadi:\n<code>{e}</code>",
                reply_markup=admin_keyboard
            )
            await state.set_state(AdminFSM.idle)
            return
 
        channels.append({"id": channel_id, "link": channel_link, "name": channel_name})
        await save_channels(channels)
 
        await message.answer(
            f"✅ <b>Kanal qo'shildi!</b>\n\n"
            f"📢 Nomi: <b>{channel_name}</b>\n"
            f"🆔 ID: <code>{channel_id}</code>",
            reply_markup=admin_keyboard
        )
    except ValueError:
        await message.answer(
            "❌ Format noto'g'ri!\n\n"
            "To'g'ri format:\n"
            "<code>-1001234567890 | https://t.me/kanal | Kanal nomi</code>",
            reply_markup=admin_keyboard
        )
    await state.set_state(AdminFSM.idle)
 
# ============================================================
# ADMIN — Kanallar ro'yxati va o'chirish
# ============================================================
@dp.message(F.text == "📋 Kanallar ro'yxati")
async def admin_channels_list(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    channels = await load_channels()
 
    if not channels:
        await message.answer(
            "📋 <b>Hozircha kanal yo'q.</b>\n\n"
            "⚠️ Kanal bo'lmasa, hamma kino ko'ra oladi.\n"
            "Kanal qo'shish uchun 📢 Kanal qo'shish tugmasini bosing."
        )
        return
 
    text = f"📋 <b>Kanallar ({len(channels)}/10):</b>\n\n"
    for i, ch in enumerate(channels, 1):
        text += f"{i}. <b>{ch['name']}</b>\n   🆔 <code>{ch['id']}</code>\n\n"
 
    buttons = [[InlineKeyboardButton(
        text=f"🗑 {ch['name']} o'chirish",
        callback_data=f"del_ch_{ch['id']}"
    )] for ch in channels]
 
    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
 
@dp.callback_query(F.data.startswith("del_ch_"))
async def delete_channel_cb(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    channel_id = int(callback.data.replace("del_ch_", ""))
    channels = await load_channels()
    new_channels = [ch for ch in channels if ch["id"] != channel_id]
    await save_channels(new_channels)
    await callback.answer("✅ Kanal o'chirildi!", show_alert=True)
    await callback.message.delete()
 
# ============================================================
# ADMIN — Statistika
# ============================================================
@dp.message(F.text == "📊 Statistika")
async def statistika(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    data = await load_data()
    stats = await load_stats()
    channels = await load_channels()
    await message.answer(
        f"📊 <b>Bot statistikasi:</b>\n\n"
        f"🎬 Kinolar soni: <b>{len(data)}</b>\n"
        f"👤 Foydalanuvchilar: <b>{len(stats.get('users', []))}</b>\n"
        f"📥 Jami so'rovlar: <b>{stats.get('requests', 0)}</b>\n"
        f"📢 Kanallar: <b>{len(channels)}/10</b>"
    )
 
# ============================================================
# ADMIN — Ommaviy xabar yuborish
# ============================================================
@dp.message(F.text == "📣 Xabar yuborish")
async def admin_broadcast_start(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    stats = await load_stats()
    await message.answer(
        f"📣 <b>Ommaviy xabar yuborish</b>\n\n"
        f"👤 Foydalanuvchilar: <b>{len(stats.get('users', []))}</b>\n\n"
        "Yubormoqchi bo'lgan xabaringizni kiriting:\n"
        "(Bekor qilish uchun /cancel)",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.set_state(AdminFSM.waiting_for_broadcast)
 
@dp.message(AdminFSM.waiting_for_broadcast, F.text == "/cancel")
async def admin_broadcast_cancel(message: Message, state: FSMContext):
    await message.answer("❌ Bekor qilindi.", reply_markup=admin_keyboard)
    await state.set_state(AdminFSM.idle)
 
@dp.message(AdminFSM.waiting_for_broadcast, F.text)
async def admin_broadcast_send(message: Message, state: FSMContext):
    stats = await load_stats()
    users = stats.get("users", [])
 
    if not users:
        await message.answer("👤 Hali foydalanuvchilar yo'q.", reply_markup=admin_keyboard)
        await state.set_state(AdminFSM.idle)
        return
 
    sent = 0
    failed = 0
    status_msg = await message.answer(f"⏳ Yuborilmoqda... (0/{len(users)})")
 
    for i, user_id in enumerate(users):
        try:
            await bot.send_message(user_id, f"📣 <b>Yangilik:</b>\n\n{message.text}")
            sent += 1
        except Exception:
            failed += 1
 
        if (i + 1) % 20 == 0:
            try:
                await status_msg.edit_text(f"⏳ Yuborilmoqda... ({i+1}/{len(users)})")
            except Exception:
                pass
        await asyncio.sleep(0.05)
 
    await status_msg.edit_text(
        f"✅ <b>Xabar yuborildi!</b>\n\n"
        f"✔️ Muvaffaqiyatli: <b>{sent}</b>\n"
        f"❌ Xato (bloklagan): <b>{failed}</b>"
    )
    await message.answer("Admin menyu:", reply_markup=admin_keyboard)
    await state.set_state(AdminFSM.idle)
 
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
# ADMIN — /stats tez buyrug'i
# ============================================================
@dp.message(F.text == "/stats")
async def stats_cmd(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    data = await load_data()
    stats = await load_stats()
    channels = await load_channels()
    await message.answer(
        f"📊 Kinolar: <b>{len(data)}</b> | "
        f"👤 Foydalanuvchilar: <b>{len(stats.get('users', []))}</b> | "
        f"📢 Kanallar: <b>{len(channels)}</b>"
    )
 
# ============================================================
# FOYDALANUVCHI — Kino kodi
# ============================================================
@dp.message(UserFSM.waiting_for_movie_code, F.text)
async def user_enter_code(message: Message, state: FSMContext):
    user_id = message.from_user.id
 
    not_subscribed = await check_subscriptions(user_id)
    if not_subscribed:
        await show_subscribe_message(message, not_subscribed)
        await state.clear()
        return
 
    code = message.text.strip().lower()
    data = await load_data()
 
    if code in data:
        movie = data[code]
        file_id = movie["file_id"] if isinstance(movie, dict) else movie
        ftype = movie.get("type", "video") if isinstance(movie, dict) else "video"
        title = movie.get("title", "Kino") if isinstance(movie, dict) else "Kino"
 
        caption = f"🎬 <b>{title}</b>\n\nBoshqa kino uchun kodni kiriting:"
 
        try:
            if ftype == "document":
                await message.answer_document(file_id, caption=caption)
            else:
                await message.answer_video(file_id, caption=caption)
        except Exception as e:
            print(f"[XATO] Fayl yuborishda: {e}")
            await message.answer("❌ Kino yuborishda xato. Admin bilan bog'laning.")
    else:
        await message.answer(
            f"❌ <b>'{code}'</b> kodi topilmadi.\n\n"
            "To'g'ri kodni kiriting yoki admin bilan bog'laning."
        )
 
# ============================================================
# Boshqa xabarlar
# ============================================================
@dp.message(F.text)
async def handle_text(message: Message, state: FSMContext):
    user_id = message.from_user.id
    current_state = await state.get_state()
 
    if user_id == ADMIN_ID and current_state is None:
        await message.answer("/start yuboring yoki admin paneliga kiring.")
        return
 
    if current_state is None:
        not_subscribed = await check_subscriptions(user_id)
        if not_subscribed:
            await show_subscribe_message(message, not_subscribed)
        else:
            await message.answer("🔑 Kino kodini kiriting:")
            await state.set_state(UserFSM.waiting_for_movie_code)
 
# ============================================================
# Botni ishga tushirish
# ============================================================
async def main():
    print("=" * 40)
    print("🚀 Bot ishga tushdi!")
    print(f"👤 Admin ID: {ADMIN_ID}")
    channels = await load_channels()
    if channels:
        print(f"📢 Kanallar: {[ch['name'] for ch in channels]}")
    else:
        print("📢 Kanallar: Yo'q (hamma kino ko'ra oladi)")
    print("=" * 40)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)
 
if __name__ == "__main__":
    asyncio.run(main())
