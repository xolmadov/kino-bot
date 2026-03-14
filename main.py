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
CHANNELS = []
 
# ============================================================
 
bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())
 
admin_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🎬 Kino qo'shish"), KeyboardButton(text="📺 Serial qo'shish")],
        [KeyboardButton(text="➕ Serialga qism qo'shish")],
        [KeyboardButton(text="📁 Barcha kinolar"), KeyboardButton(text="🗑 Kino o'chirish")],
        [KeyboardButton(text="📢 Kanal qo'shish"), KeyboardButton(text="📋 Kanallar ro'yxati")],
        [KeyboardButton(text="📊 Statistika"), KeyboardButton(text="📣 Xabar yuborish")],
        [KeyboardButton(text="🚪 Chiqish")],
    ],
    resize_keyboard=True
)
 
DATA_FILE = "data.json"
SERIES_FILE = "series.json"
STATS_FILE = "stats.json"
CHANNELS_FILE = "channels.json"
data_lock = asyncio.Lock()
series_lock = asyncio.Lock()
 
# ============================================================
# MA'LUMOT YUKLASH / SAQLASH
# ============================================================
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
 
async def load_series() -> dict:
    async with series_lock:
        try:
            with open(SERIES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
 
async def save_series(data: dict):
    async with series_lock:
        with open(SERIES_FILE, "w", encoding="utf-8") as f:
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
    try:
        with open(CHANNELS_FILE, "r", encoding="utf-8") as f:
            saved = json.load(f)
        all_ch = list(CHANNELS)
        for ch in saved:
            if not any(c["id"] == ch["id"] for c in all_ch):
                all_ch.append(ch)
        return all_ch
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
 
# ============================================================
# FSM
# ============================================================
class AdminFSM(StatesGroup):
    waiting_for_password = State()
    idle = State()
    # Kino
    waiting_for_video = State()
    waiting_for_title = State()
    waiting_for_code = State()
    waiting_for_delete = State()
    # Yangi serial
    waiting_for_series_title = State()
    waiting_for_series_code = State()
    waiting_for_series_count = State()
    waiting_for_episode = State()
    # Mavjud serialga qism qo'shish
    waiting_for_add_ep_code = State()
    waiting_for_add_ep_count = State()
    waiting_for_add_ep_file = State()
    # Kanal
    waiting_for_channel = State()
    # Xabar
    waiting_for_broadcast = State()
 
class UserFSM(StatesGroup):
    waiting_for_movie_code = State()
 
# ============================================================
# KANAL TEKSHIRUVI
# ============================================================
async def check_subscriptions(user_id: int) -> list:
    channels = await load_channels()
    if not channels:
        return []
    not_sub = []
    for ch in channels:
        try:
            member = await bot.get_chat_member(chat_id=ch["id"], user_id=user_id)
            if member.status not in ("member", "administrator", "creator"):
                not_sub.append(ch)
        except Exception as e:
            print(f"[XATO] Kanal {ch['id']}: {e}")
            not_sub.append(ch)
    return not_sub
 
async def show_subscribe_message(message: Message, not_sub: list):
    buttons = [[InlineKeyboardButton(text=f"📢 {ch['name']}", url=ch["link"])] for ch in not_sub]
    buttons.append([InlineKeyboardButton(text="✅ Obuna bo'ldim, tekshirish", callback_data="check_sub")])
    channels_text = "\n".join([f"• <a href='{ch['link']}'>{ch['name']}</a>" for ch in not_sub])
    await message.answer(
        "⚠️ <b>Kino/serial ko'rish uchun kanallarga obuna bo'ling:</b>\n\n"
        f"{channels_text}\n\n"
        "Obuna bo'lgach, ✅ <b>Tekshirish</b> tugmasini bosing.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        disable_web_page_preview=True
    )
 
# ============================================================
# /start
# ============================================================
@dp.message(F.text == "/start")
async def start_cmd(message: Message, state: FSMContext):
    user_id = message.from_user.id
 
    if user_id == ADMIN_ID:
        cur = await state.get_state()
        admin_states = [
            str(AdminFSM.idle), str(AdminFSM.waiting_for_video), str(AdminFSM.waiting_for_title),
            str(AdminFSM.waiting_for_code), str(AdminFSM.waiting_for_delete),
            str(AdminFSM.waiting_for_series_title), str(AdminFSM.waiting_for_series_code),
            str(AdminFSM.waiting_for_series_count), str(AdminFSM.waiting_for_episode),
            str(AdminFSM.waiting_for_add_ep_code), str(AdminFSM.waiting_for_add_ep_count),
            str(AdminFSM.waiting_for_add_ep_file),
            str(AdminFSM.waiting_for_channel), str(AdminFSM.waiting_for_broadcast),
        ]
        if cur not in admin_states:
            await message.answer(
                "🔐 <b>Admin paneliga xush kelibsiz!</b>\n\nParolni kiriting:",
                reply_markup=ReplyKeyboardRemove()
            )
            await state.set_state(AdminFSM.waiting_for_password)
        else:
            await message.answer("✅ Admin sifatida kirgansiz.", reply_markup=admin_keyboard)
        return
 
    await track_user(user_id)
    not_sub = await check_subscriptions(user_id)
    if not_sub:
        await show_subscribe_message(message, not_sub)
    else:
        await message.answer(
            "🎬 <b>Kino/Serial botiga xush kelibsiz!</b>\n\n"
            "🔑 Kino yoki serial kodini kiriting:"
        )
        await state.set_state(UserFSM.waiting_for_movie_code)
 
# ============================================================
# OBUNA TEKSHIRISH
# ============================================================
@dp.callback_query(F.data == "check_sub")
async def check_sub_cb(callback: types.CallbackQuery, state: FSMContext):
    not_sub = await check_subscriptions(callback.from_user.id)
    if not not_sub:
        await callback.message.edit_text("✅ <b>Obuna tasdiqlandi!</b>\n\n🔑 Kod kiriting:")
        await state.set_state(UserFSM.waiting_for_movie_code)
    else:
        names = ", ".join([ch["name"] for ch in not_sub])
        await callback.answer(f"❌ Hali obuna bo'lmagansiz!\nQolganlar: {names}", show_alert=True)
 
# ============================================================
# ADMIN — Parol
# ============================================================
@dp.message(AdminFSM.waiting_for_password, F.text)
async def admin_login(message: Message, state: FSMContext):
    if message.text.strip() == ADMIN_PASSWORD:
        await message.answer("✅ <b>Xush kelibsiz, Admin!</b>", reply_markup=admin_keyboard)
        await state.set_state(AdminFSM.idle)
    else:
        await message.answer("❌ Noto'g'ri parol!")
 
# ============================================================
# ADMIN — KINO QO'SHISH
# ============================================================
@dp.message(F.text == "🎬 Kino qo'shish")
async def admin_add_movie(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer(
        "🎥 <b>Kino faylini yuboring:</b>\n\n💡 Document formatida yuboring!",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.set_state(AdminFSM.waiting_for_video)
 
@dp.message(AdminFSM.waiting_for_video, F.video | F.document)
async def admin_receive_video(message: Message, state: FSMContext):
    if message.video:
        file_id, ftype = message.video.file_id, "video"
    else:
        file_id, ftype = message.document.file_id, "document"
    await state.update_data(file_id=file_id, file_type=ftype)
    await message.answer("✏️ <b>Kino nomini kiriting:</b>")
    await state.set_state(AdminFSM.waiting_for_title)
 
@dp.message(AdminFSM.waiting_for_video)
async def admin_wrong_file(message: Message):
    await message.answer("⚠️ Iltimos, video yoki fayl yuboring!")
 
@dp.message(AdminFSM.waiting_for_title, F.text)
async def admin_movie_title(message: Message, state: FSMContext):
    title = message.text.strip()
    if len(title) > 100:
        await message.answer("❌ Nom 100 belgidan kam bo'lsin.")
        return
    await state.update_data(title=title)
    await message.answer("🔑 <b>Kino kodini kiriting:</b>\nMasalan: <code>avatar2</code>")
    await state.set_state(AdminFSM.waiting_for_code)
 
@dp.message(AdminFSM.waiting_for_code, F.text)
async def admin_save_movie(message: Message, state: FSMContext):
    code = message.text.strip().lower()
    if not code or len(code) > 30:
        await message.answer("❌ Kod 1-30 belgi bo'lishi kerak.")
        return
    all_data = await load_data()
    all_series = await load_series()
    if code in all_data or code in all_series:
        await message.answer(f"⚠️ <b>'{code}'</b> kodi allaqachon mavjud!")
        return
    data = await state.get_data()
    all_data[code] = {
        "file_id": data["file_id"],
        "type": data.get("file_type", "video"),
        "title": data.get("title", "Nomsiz"),
        "kind": "movie"
    }
    await save_data(all_data)
    await message.answer(
        f"✅ <b>Kino saqlandi!</b>\n\n"
        f"🎬 Nomi: <b>{data.get('title')}</b>\n"
        f"🔑 Kodi: <code>{code}</code>",
        reply_markup=admin_keyboard
    )
    await state.set_state(AdminFSM.idle)
 
# ============================================================
# ADMIN — YANGI SERIAL QO'SHISH
# ============================================================
@dp.message(F.text == "📺 Serial qo'shish")
async def admin_add_series(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer(
        "📺 <b>Serial nomini kiriting:</b>\nMasalan: <code>Breaking Bad</code>",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.set_state(AdminFSM.waiting_for_series_title)
 
@dp.message(AdminFSM.waiting_for_series_title, F.text)
async def admin_series_title(message: Message, state: FSMContext):
    title = message.text.strip()
    if len(title) > 100:
        await message.answer("❌ Nom 100 belgidan kam bo'lsin.")
        return
    await state.update_data(series_title=title, episodes=[])
    await message.answer(
        f"✅ Nomi: <b>{title}</b>\n\n"
        "🔑 <b>Serial kodini kiriting:</b>\nMasalan: <code>breaking</code>"
    )
    await state.set_state(AdminFSM.waiting_for_series_code)
 
@dp.message(AdminFSM.waiting_for_series_code, F.text)
async def admin_series_code(message: Message, state: FSMContext):
    code = message.text.strip().lower()
    if not code or len(code) > 30:
        await message.answer("❌ Kod 1-30 belgi bo'lishi kerak.")
        return
    all_data = await load_data()
    all_series = await load_series()
    if code in all_data or code in all_series:
        await message.answer(f"⚠️ <b>'{code}'</b> kodi mavjud! Boshqa kod kiriting.")
        return
    await state.update_data(series_code=code)
    await message.answer(
        "🔢 <b>Nechta qism yuklaysiz hozir?</b>\n\n"
        "Raqam kiriting (1-100):\n"
        "💡 Keyin yana qo'shish mumkin!"
    )
    await state.set_state(AdminFSM.waiting_for_series_count)
 
@dp.message(AdminFSM.waiting_for_series_count, F.text)
async def admin_series_count(message: Message, state: FSMContext):
    try:
        count = int(message.text.strip())
        if count < 1 or count > 100:
            raise ValueError()
    except ValueError:
        await message.answer("❌ 1 dan 100 gacha raqam kiriting.")
        return
 
    await state.update_data(total_to_upload=count, current_episode=1, episodes=[])
    data = await state.get_data()
    await message.answer(
        f"📺 <b>{data['series_title']}</b>\n\n"
        f"📤 <b>1-qismni yuboring:</b>"
    )
    await state.set_state(AdminFSM.waiting_for_episode)
 
@dp.message(AdminFSM.waiting_for_episode, F.video | F.document)
async def admin_receive_episode(message: Message, state: FSMContext):
    if message.video:
        file_id, ftype = message.video.file_id, "video"
    else:
        file_id, ftype = message.document.file_id, "document"
 
    data = await state.get_data()
    episodes = data.get("episodes", [])
    current = data.get("current_episode", 1)
    total_to_upload = data.get("total_to_upload", 1)
 
    episodes.append({"file_id": file_id, "type": ftype})
    await state.update_data(episodes=episodes, current_episode=current + 1)
 
    if current >= total_to_upload:
        # Saqlash
        all_series = await load_series()
        code = data["series_code"]
        all_series[code] = {
            "title": data["series_title"],
            "kind": "series",
            "episodes": episodes
        }
        await save_series(all_series)
        await message.answer(
            f"✅ <b>Serial saqlandi!</b>\n\n"
            f"📺 Nomi: <b>{data['series_title']}</b>\n"
            f"🔑 Kodi: <code>{code}</code>\n"
            f"🎞 Qismlar: <b>{len(episodes)} ta</b>\n\n"
            "💡 Keyinchalik <b>➕ Serialga qism qo'shish</b> orqali yangi qismlar qo'sha olasiz!",
            reply_markup=admin_keyboard
        )
        await state.set_state(AdminFSM.idle)
    else:
        await message.answer(
            f"✅ <b>{current}-qism saqlandi!</b>\n\n"
            f"📤 <b>{current + 1}-qismni yuboring</b> ({current}/{total_to_upload}):"
        )
 
@dp.message(AdminFSM.waiting_for_episode)
async def admin_episode_wrong(message: Message, state: FSMContext):
    data = await state.get_data()
    current = data.get("current_episode", 1)
    await message.answer(f"⚠️ {current}-qism uchun video yoki fayl yuboring!")
 
# ============================================================
# ADMIN — MAVJUD SERIALGA QISM QO'SHISH
# ============================================================
@dp.message(F.text == "➕ Serialga qism qo'shish")
async def admin_add_ep_start(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    series = await load_series()
    if not series:
        await message.answer("🚫 Hozircha hech qanday serial yo'q.")
        return
 
    text = "📺 <b>Qaysi serialga qism qo'shmoqchisiz?</b>\n\nKodini kiriting:\n\n"
    for code, s in series.items():
        ep_count = len(s.get("episodes", []))
        text += f"• <code>{code}</code> — {s.get('title', 'Nomsiz')} ({ep_count} qism)\n"
 
    await message.answer(text, reply_markup=ReplyKeyboardRemove())
    await state.set_state(AdminFSM.waiting_for_add_ep_code)
 
@dp.message(AdminFSM.waiting_for_add_ep_code, F.text)
async def admin_add_ep_code(message: Message, state: FSMContext):
    code = message.text.strip().lower()
    series = await load_series()
 
    if code not in series:
        await message.answer(f"❌ <b>'{code}'</b> kodi topilmadi. Qaytadan kiriting:")
        return
 
    s = series[code]
    current_count = len(s.get("episodes", []))
    await state.update_data(add_ep_code=code, add_ep_current=current_count + 1)
 
    await message.answer(
        f"✅ Serial: <b>{s['title']}</b>\n"
        f"🎞 Hozirgi qismlar: <b>{current_count} ta</b>\n\n"
        "🔢 <b>Nechta yangi qism qo'shmoqchisiz?</b>\n"
        "Raqam kiriting (1-100):"
    )
    await state.set_state(AdminFSM.waiting_for_add_ep_count)
 
@dp.message(AdminFSM.waiting_for_add_ep_count, F.text)
async def admin_add_ep_count(message: Message, state: FSMContext):
    try:
        count = int(message.text.strip())
        if count < 1 or count > 100:
            raise ValueError()
    except ValueError:
        await message.answer("❌ 1 dan 100 gacha raqam kiriting.")
        return
 
    data = await state.get_data()
    await state.update_data(add_ep_total=count, add_ep_uploaded=0, new_episodes=[])
 
    await message.answer(
        f"📤 <b>{data['add_ep_current']}-qismni yuboring:</b>"
    )
    await state.set_state(AdminFSM.waiting_for_add_ep_file)
 
@dp.message(AdminFSM.waiting_for_add_ep_file, F.video | F.document)
async def admin_add_ep_file(message: Message, state: FSMContext):
    if message.video:
        file_id, ftype = message.video.file_id, "video"
    else:
        file_id, ftype = message.document.file_id, "document"
 
    data = await state.get_data()
    new_episodes = data.get("new_episodes", [])
    uploaded = data.get("add_ep_uploaded", 0) + 1
    total = data.get("add_ep_total", 1)
    current_num = data.get("add_ep_current", 1)
 
    new_episodes.append({"file_id": file_id, "type": ftype})
    await state.update_data(new_episodes=new_episodes, add_ep_uploaded=uploaded,
                            add_ep_current=current_num + 1)
 
    if uploaded >= total:
        # Serialga qo'shish
        code = data["add_ep_code"]
        series = await load_series()
        old_episodes = series[code].get("episodes", [])
        series[code]["episodes"] = old_episodes + new_episodes
        total_now = len(series[code]["episodes"])
        await save_series(series)
 
        await message.answer(
            f"✅ <b>Qismlar qo'shildi!</b>\n\n"
            f"📺 Serial: <b>{series[code]['title']}</b>\n"
            f"🎞 Jami qismlar: <b>{total_now} ta</b>\n"
            f"➕ Qo'shildi: <b>{total} ta</b>",
            reply_markup=admin_keyboard
        )
        await state.set_state(AdminFSM.idle)
    else:
        await message.answer(
            f"✅ <b>{current_num}-qism saqlandi!</b>\n\n"
            f"📤 <b>{current_num + 1}-qismni yuboring</b> ({uploaded}/{total}):"
        )
 
@dp.message(AdminFSM.waiting_for_add_ep_file)
async def admin_add_ep_wrong(message: Message, state: FSMContext):
    data = await state.get_data()
    current = data.get("add_ep_current", 1)
    await message.answer(f"⚠️ {current}-qism uchun video yoki fayl yuboring!")
 
# ============================================================
# ADMIN — BARCHA KINOLAR VA SERIALLAR
# ============================================================
@dp.message(F.text == "📁 Barcha kinolar")
async def kino_list(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    movies = await load_data()
    series = await load_series()
    text = ""
    if movies:
        text += f"🎬 <b>Kinolar ({len(movies)} ta):</b>\n"
        for k, v in movies.items():
            title = v.get("title", "Nomsiz") if isinstance(v, dict) else "Nomsiz"
            text += f"  🔑 <code>{k}</code> — {title}\n"
        text += "\n"
    if series:
        text += f"📺 <b>Seriallar ({len(series)} ta):</b>\n"
        for k, v in series.items():
            ep_count = len(v.get("episodes", []))
            text += f"  🔑 <code>{k}</code> — {v.get('title', 'Nomsiz')} ({ep_count} qism)\n"
    if not text:
        await message.answer("🚫 Hozircha hech narsa yo'q.")
    else:
        await message.answer(text)
 
# ============================================================
# ADMIN — O'CHIRISH
# ============================================================
@dp.message(F.text == "🗑 Kino o'chirish")
async def admin_delete_start(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    movies = await load_data()
    series = await load_series()
    if not movies and not series:
        await message.answer("🚫 O'chiriladigan narsa yo'q.")
        return
    text = "🗑 <b>O'chirish uchun kodni kiriting:</b>\n\n"
    if movies:
        text += "🎬 Kinolar:\n"
        for k, v in movies.items():
            title = v.get("title", "Nomsiz") if isinstance(v, dict) else "Nomsiz"
            text += f"  • <code>{k}</code> — {title}\n"
    if series:
        text += "\n📺 Seriallar:\n"
        for k, v in series.items():
            ep_count = len(v.get("episodes", []))
            text += f"  • <code>{k}</code> — {v.get('title', 'Nomsiz')} ({ep_count} qism)\n"
    await message.answer(text, reply_markup=ReplyKeyboardRemove())
    await state.set_state(AdminFSM.waiting_for_delete)
 
@dp.message(AdminFSM.waiting_for_delete, F.text)
async def admin_delete(message: Message, state: FSMContext):
    code = message.text.strip().lower()
    movies = await load_data()
    series = await load_series()
    if code in movies:
        title = movies[code].get("title", "Nomsiz") if isinstance(movies[code], dict) else "Nomsiz"
        del movies[code]
        await save_data(movies)
        await message.answer(f"✅ Kino <b>'{title}'</b> o'chirildi!", reply_markup=admin_keyboard)
    elif code in series:
        title = series[code].get("title", "Nomsiz")
        del series[code]
        await save_series(series)
        await message.answer(f"✅ Serial <b>'{title}'</b> o'chirildi!", reply_markup=admin_keyboard)
    else:
        await message.answer(f"❌ <b>'{code}'</b> topilmadi.", reply_markup=admin_keyboard)
    await state.set_state(AdminFSM.idle)
 
# ============================================================
# ADMIN — KANAL QO'SHISH
# ============================================================
@dp.message(F.text == "📢 Kanal qo'shish")
async def admin_add_channel(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer(
        "📢 <b>Kanal ma'lumotlarini kiriting:</b>\n\n"
        "Format:\n<code>-1001234567890 | https://t.me/kanal | Kanal nomi</code>\n\n"
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
            raise ValueError()
        channel_id = int(parts[0])
        channel_link = parts[1]
        channel_name = parts[2]
        if not channel_link.startswith("https://t.me/"):
            raise ValueError()
        channels = await load_channels()
        if len(channels) >= 10:
            await message.answer("❌ Maksimal 10 ta kanal!", reply_markup=admin_keyboard)
            await state.set_state(AdminFSM.idle)
            return
        if any(c["id"] == channel_id for c in channels):
            await message.answer("⚠️ Bu kanal allaqachon qo'shilgan!", reply_markup=admin_keyboard)
            await state.set_state(AdminFSM.idle)
            return
        me = await bot.get_me()
        member = await bot.get_chat_member(chat_id=channel_id, user_id=me.id)
        if member.status not in ("administrator", "creator"):
            await message.answer("❌ Bot kanalda admin emas!", reply_markup=admin_keyboard)
            await state.set_state(AdminFSM.idle)
            return
        channels.append({"id": channel_id, "link": channel_link, "name": channel_name})
        await save_channels(channels)
        await message.answer(
            f"✅ <b>Kanal qo'shildi!</b>\n📢 {channel_name}",
            reply_markup=admin_keyboard
        )
    except ValueError:
        await message.answer(
            "❌ Format noto'g'ri!\n\n"
            "<code>-1001234567890 | https://t.me/kanal | Kanal nomi</code>",
            reply_markup=admin_keyboard
        )
    except Exception as e:
        await message.answer(f"❌ Xato: <code>{e}</code>", reply_markup=admin_keyboard)
    await state.set_state(AdminFSM.idle)
 
# ============================================================
# ADMIN — KANALLAR RO'YXATI
# ============================================================
@dp.message(F.text == "📋 Kanallar ro'yxati")
async def admin_channels_list(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    channels = await load_channels()
    if not channels:
        await message.answer("📋 Kanal yo'q.\n⚠️ Kanal bo'lmasa, hamma ko'ra oladi.")
        return
    text = f"📋 <b>Kanallar ({len(channels)}/10):</b>\n\n"
    for i, ch in enumerate(channels, 1):
        text += f"{i}. <b>{ch['name']}</b> — <code>{ch['id']}</code>\n"
    buttons = [[InlineKeyboardButton(
        text=f"🗑 {ch['name']}", callback_data=f"del_ch_{ch['id']}"
    )] for ch in channels]
    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
 
@dp.callback_query(F.data.startswith("del_ch_"))
async def delete_channel_cb(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    ch_id = int(callback.data.replace("del_ch_", ""))
    channels = await load_channels()
    await save_channels([ch for ch in channels if ch["id"] != ch_id])
    await callback.answer("✅ Kanal o'chirildi!", show_alert=True)
    await callback.message.delete()
 
# ============================================================
# ADMIN — STATISTIKA
# ============================================================
@dp.message(F.text == "📊 Statistika")
async def statistika(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    movies = await load_data()
    series = await load_series()
    stats = await load_stats()
    channels = await load_channels()
    await message.answer(
        f"📊 <b>Bot statistikasi:</b>\n\n"
        f"🎬 Kinolar: <b>{len(movies)}</b>\n"
        f"📺 Seriallar: <b>{len(series)}</b>\n"
        f"👤 Foydalanuvchilar: <b>{len(stats.get('users', []))}</b>\n"
        f"📥 Jami so'rovlar: <b>{stats.get('requests', 0)}</b>\n"
        f"📢 Kanallar: <b>{len(channels)}/10</b>"
    )
 
# ============================================================
# ADMIN — OMMAVIY XABAR
# ============================================================
@dp.message(F.text == "📣 Xabar yuborish")
async def admin_broadcast_start(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    stats = await load_stats()
    await message.answer(
        f"📣 <b>Ommaviy xabar</b>\n\n"
        f"👤 Foydalanuvchilar: <b>{len(stats.get('users', []))}</b>\n\n"
        "Xabarni kiriting (/cancel — bekor qilish):",
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
        await message.answer("👤 Foydalanuvchilar yo'q.", reply_markup=admin_keyboard)
        await state.set_state(AdminFSM.idle)
        return
    sent = failed = 0
    status_msg = await message.answer(f"⏳ Yuborilmoqda... 0/{len(users)}")
    for i, uid in enumerate(users):
        try:
            await bot.send_message(uid, f"📣 <b>Yangilik:</b>\n\n{message.text}")
            sent += 1
        except Exception:
            failed += 1
        if (i + 1) % 20 == 0:
            try:
                await status_msg.edit_text(f"⏳ Yuborilmoqda... {i+1}/{len(users)}")
            except Exception:
                pass
        await asyncio.sleep(0.05)
    await status_msg.edit_text(
        f"✅ <b>Xabar yuborildi!</b>\n✔️ Muvaffaqiyatli: <b>{sent}</b>\n❌ Xato: <b>{failed}</b>"
    )
    await message.answer("Admin menyu:", reply_markup=admin_keyboard)
    await state.set_state(AdminFSM.idle)
 
# ============================================================
# ADMIN — CHIQISH
# ============================================================
@dp.message(F.text == "🚪 Chiqish")
async def admin_logout(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    await state.clear()
    await message.answer("👋 Admin paneldan chiqdingiz.", reply_markup=ReplyKeyboardRemove())
 
@dp.message(F.text == "/stats")
async def stats_cmd(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    movies = await load_data()
    series = await load_series()
    stats = await load_stats()
    await message.answer(
        f"🎬 {len(movies)} kino | 📺 {len(series)} serial | 👤 {len(stats.get('users', []))} user"
    )
 
# ============================================================
# FOYDALANUVCHI — Serial qismini yuborish (callback)
# ============================================================
@dp.callback_query(F.data.startswith("ep_"))
async def send_episode(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    if len(parts) < 3:
        return
    code = parts[1]
    try:
        ep_num = int(parts[2])
    except ValueError:
        return
 
    not_sub = await check_subscriptions(callback.from_user.id)
    if not_sub:
        await callback.answer("❌ Avval kanallarga obuna bo'ling!", show_alert=True)
        return
 
    series = await load_series()
    if code not in series:
        await callback.answer("❌ Serial topilmadi!", show_alert=True)
        return
 
    s = series[code]
    episodes = s.get("episodes", [])
    idx = ep_num - 1
    if idx < 0 or idx >= len(episodes):
        await callback.answer("❌ Qism topilmadi!", show_alert=True)
        return
 
    ep = episodes[idx]
    caption = f"📺 <b>{s['title']}</b>\n🎞 <b>{ep_num}-qism</b>"
    await callback.answer()
    try:
        if ep["type"] == "document":
            await callback.message.answer_document(ep["file_id"], caption=caption)
        else:
            await callback.message.answer_video(ep["file_id"], caption=caption)
    except Exception as e:
        print(f"[XATO] Qism yuborishda: {e}")
        await callback.message.answer("❌ Qismni yuborishda xato yuz berdi.")
 
# ============================================================
# FOYDALANUVCHI — Kod kiritish
# ============================================================
@dp.message(UserFSM.waiting_for_movie_code, F.text)
async def user_enter_code(message: Message, state: FSMContext):
    user_id = message.from_user.id
    not_sub = await check_subscriptions(user_id)
    if not_sub:
        await show_subscribe_message(message, not_sub)
        await state.clear()
        return
 
    code = message.text.strip().lower()
    movies = await load_data()
    series = await load_series()
 
    # ---- KINO ----
    if code in movies:
        movie = movies[code]
        file_id = movie["file_id"] if isinstance(movie, dict) else movie
        ftype = movie.get("type", "video") if isinstance(movie, dict) else "video"
        title = movie.get("title", "Kino") if isinstance(movie, dict) else "Kino"
        caption = f"🎬 <b>{title}</b>\n\nBoshqa kod kiriting:"
        try:
            if ftype == "document":
                await message.answer_document(file_id, caption=caption)
            else:
                await message.answer_video(file_id, caption=caption)
        except Exception as e:
            print(f"[XATO] Kino: {e}")
            await message.answer("❌ Kino yuborishda xato.")
        return
 
    # ---- SERIAL ----
    if code in series:
        s = series[code]
        title = s.get("title", "Serial")
        episodes = s.get("episodes", [])
        total = len(episodes)
 
        if not episodes:
            await message.answer("❌ Serial qismlari topilmadi.")
            return
 
        # 1-qismni yuborish
        ep = episodes[0]
        caption = f"📺 <b>{title}</b>\n🎞 <b>1-qism</b>"
        try:
            if ep["type"] == "document":
                await message.answer_document(ep["file_id"], caption=caption)
            else:
                await message.answer_video(ep["file_id"], caption=caption)
        except Exception as e:
            print(f"[XATO] 1-qism: {e}")
            await message.answer("❌ Serial yuborishda xato.")
            return
 
        # Qismlar tugmalari (▶️ belgisiz)
        if total > 1:
            buttons = []
            row = []
            for i in range(1, total + 1):
                row.append(InlineKeyboardButton(
                    text=f"{i}-qism",
                    callback_data=f"ep_{code}_{i}"
                ))
                if len(row) == 4:
                    buttons.append(row)
                    row = []
            if row:
                buttons.append(row)
 
            await message.answer(
                f"📺 <b>{title}</b> — barcha qismlar ({total} ta):",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
            )
        return
 
    # ---- TOPILMADI ----
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
        await message.answer("/start yuboring.")
        return
    if current_state is None:
        not_sub = await check_subscriptions(user_id)
        if not_sub:
            await show_subscribe_message(message, not_sub)
        else:
            await message.answer("🔑 Kino yoki serial kodini kiriting:")
            await state.set_state(UserFSM.waiting_for_movie_code)
 
# ============================================================
# ISHGA TUSHIRISH
# ============================================================
async def main():
    print("=" * 40)
    print("🚀 Bot ishga tushdi!")
    print(f"👤 Admin ID: {ADMIN_ID}")
    channels = await load_channels()
    movies = await load_data()
    series = await load_series()
    print(f"🎬 Kinolar: {len(movies)} ta")
    print(f"📺 Seriallar: {len(series)} ta")
    if channels:
        print(f"📢 Kanallar: {[ch['name'] for ch in channels]}")
    else:
        print("📢 Kanallar: Yo'q")
    print("=" * 40)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)
 
if __name__ == "__main__":
    asyncio.run(main())
