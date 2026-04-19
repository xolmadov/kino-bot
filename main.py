import asyncio
import os
import json
from dotenv import load_dotenv
load_dotenv()

import httpx
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
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

OWNER_ID = 6292545074
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "itachi201028")
CHANNELS = []
EP_PER_PAGE = 10

# ============================================================
# SUPABASE YORDAMCHI FUNKSIYALAR
# ============================================================
async def sb_get(key: str):
    """Supabase dan qiymat olish"""
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"{SUPABASE_URL}/rest/v1/storage",
            params={"key": f"eq.{key}", "select": "value"},
            headers={
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}"
            }
        )
        data = r.json()
        if data:
            return data[0]["value"]
        return None

async def sb_set(key: str, value):
    """Supabase ga qiymat saqlash"""
    async with httpx.AsyncClient() as client:
        await client.post(
            f"{SUPABASE_URL}/rest/v1/storage",
            json={"key": key, "value": value},
            headers={
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "Content-Type": "application/json",
                "Prefer": "resolution=merge-duplicates"
            }
        )

# ============================================================
# MA'LUMOT YUKLASH / SAQLASH
# ============================================================
async def load_data() -> dict:
    val = await sb_get("movies")
    return val if val else {}

async def save_data(data: dict):
    await sb_set("movies", data)

async def load_series() -> dict:
    val = await sb_get("series")
    return val if val else {}

async def save_series(data: dict):
    await sb_set("series", data)

async def load_stats() -> dict:
    val = await sb_get("stats")
    return val if val else {"users": [], "requests": 0}

async def save_stats(stats: dict):
    await sb_set("stats", stats)

async def load_channels() -> list:
    val = await sb_get("channels")
    saved = val if val else []
    all_ch = list(CHANNELS)
    for ch in saved:
        if not any(c["id"] == ch["id"] for c in all_ch):
            all_ch.append(ch)
    return all_ch

async def save_channels(channels: list):
    await sb_set("channels", channels)

async def load_subscribers() -> list:
    val = await sb_get("subscribers")
    return val if val else []

async def save_subscribers(subscribers: list):
    await sb_set("subscribers", subscribers)

async def add_subscriber(user_id: int):
    subscribers = await load_subscribers()
    if user_id not in subscribers:
        subscribers.append(user_id)
        await save_subscribers(subscribers)

async def load_admins() -> dict:
    val = await sb_get("admins")
    return val if val else {}

async def save_admins(admins: dict):
    await sb_set("admins", admins)

async def is_admin(user_id: int) -> bool:
    if user_id == OWNER_ID:
        return True
    admins = await load_admins()
    return str(user_id) in admins

async def track_user(user_id: int):
    stats = await load_stats()
    if user_id not in stats["users"]:
        stats["users"].append(user_id)
    stats["requests"] = stats.get("requests", 0) + 1
    await save_stats(stats)
    await add_subscriber(user_id)

# ============================================================

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())

# ============================================================
# ADMIN KLAVIATURASI
# ============================================================
def get_admin_keyboard(user_id: int) -> ReplyKeyboardMarkup:
    base = [
        [KeyboardButton(text="🎬 Kino qo'shish"), KeyboardButton(text="📺 Serial qo'shish")],
        [KeyboardButton(text="➕ Serialga qism qo'shish")],
        [KeyboardButton(text="📁 Barcha kinolar"), KeyboardButton(text="🗑 Kino o'chirish")],
        [KeyboardButton(text="📢 Kanal qo'shish"), KeyboardButton(text="📋 Kanallar ro'yxati")],
        [KeyboardButton(text="📊 Statistika"), KeyboardButton(text="📣 Xabar yuborish")],
    ]
    if user_id == OWNER_ID:
        base.append([
            KeyboardButton(text="👑 Admin qo'shish"),
            KeyboardButton(text="👥 Adminlar ro'yxati")
        ])
    base.append([KeyboardButton(text="🚪 Chiqish")])
    return ReplyKeyboardMarkup(keyboard=base, resize_keyboard=True)

# ============================================================
# FSM
# ============================================================
class AdminFSM(StatesGroup):
    waiting_for_password = State()
    idle = State()
    waiting_for_video = State()
    waiting_for_title = State()
    waiting_for_code = State()
    waiting_for_delete = State()
    waiting_for_series_title = State()
    waiting_for_series_code = State()
    waiting_for_series_count = State()
    waiting_for_episode = State()
    waiting_for_add_ep_code = State()
    waiting_for_add_ep_count = State()
    waiting_for_add_ep_file = State()
    waiting_for_channel = State()
    waiting_for_broadcast = State()
    waiting_for_new_admin_id = State()

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
# SAHIFALANGAN QISMLAR TUGMASI
# ============================================================
def build_episode_keyboard(code: str, total: int, page: int) -> InlineKeyboardMarkup:
    start = page * EP_PER_PAGE + 1
    end = min(start + EP_PER_PAGE - 1, total)
    total_pages = (total + EP_PER_PAGE - 1) // EP_PER_PAGE
    buttons = []
    row = []
    for i in range(start, end + 1):
        row.append(InlineKeyboardButton(text=f"{i}-qism", callback_data=f"ep_{code}_{i}"))
        if len(row) == 4:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"eppage_{code}_{page - 1}"))
    if total_pages > 1:
        nav.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton(text="➡️", callback_data=f"eppage_{code}_{page + 1}"))
    if nav:
        buttons.append(nav)
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# ============================================================
# QIDIRUV
# ============================================================
async def search_content(query: str) -> list:
    query_lower = query.strip().lower()
    results = []
    movies = await load_data()
    for code, v in movies.items():
        title = v.get("title", "") if isinstance(v, dict) else ""
        if query_lower in code or query_lower in title.lower():
            results.append({"code": code, "title": title or "Nomsiz", "kind": "movie", "extra": ""})
    series = await load_series()
    for code, v in series.items():
        title = v.get("title", "")
        ep_count = len(v.get("episodes", []))
        if query_lower in code or query_lower in title.lower():
            results.append({"code": code, "title": title or "Nomsiz", "kind": "series", "extra": f"{ep_count} qism"})
    return results

# ============================================================
# /start
# ============================================================
@dp.message(F.text == "/start")
async def start_cmd(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if await is_admin(user_id):
        cur = await state.get_state()
        admin_active_states = [
            str(AdminFSM.idle), str(AdminFSM.waiting_for_video), str(AdminFSM.waiting_for_title),
            str(AdminFSM.waiting_for_code), str(AdminFSM.waiting_for_delete),
            str(AdminFSM.waiting_for_series_title), str(AdminFSM.waiting_for_series_code),
            str(AdminFSM.waiting_for_series_count), str(AdminFSM.waiting_for_episode),
            str(AdminFSM.waiting_for_add_ep_code), str(AdminFSM.waiting_for_add_ep_count),
            str(AdminFSM.waiting_for_add_ep_file), str(AdminFSM.waiting_for_channel),
            str(AdminFSM.waiting_for_broadcast), str(AdminFSM.waiting_for_new_admin_id),
        ]
        if cur not in admin_active_states:
            await message.answer(
                "🔐 <b>Admin paneliga xush kelibsiz!</b>\n\nParolni kiriting:",
                reply_markup=ReplyKeyboardRemove()
            )
            await state.set_state(AdminFSM.waiting_for_password)
        else:
            await message.answer("✅ Admin sifatida kirgansiz.", reply_markup=get_admin_keyboard(user_id))
        return
    await track_user(user_id)
    not_sub = await check_subscriptions(user_id)
    if not_sub:
        await show_subscribe_message(message, not_sub)
    else:
        await message.answer(
            "🎬 <b>Kino/Serial botiga xush kelibsiz!</b>\n\n"
            "🔑 Kino yoki serial <b>kodi</b> yoki <b>nomini</b> kiriting:"
        )
        await state.set_state(UserFSM.waiting_for_movie_code)

# ============================================================
# OBUNA TEKSHIRISH
# ============================================================
@dp.callback_query(F.data == "check_sub")
async def check_sub_cb(callback: types.CallbackQuery, state: FSMContext):
    not_sub = await check_subscriptions(callback.from_user.id)
    if not not_sub:
        await callback.message.edit_text(
            "✅ <b>Obuna tasdiqlandi!</b>\n\n"
            "🔑 Kino yoki serial <b>kodi</b> yoki <b>nomini</b> kiriting:"
        )
        await state.set_state(UserFSM.waiting_for_movie_code)
    else:
        names = ", ".join([ch["name"] for ch in not_sub])
        await callback.answer(f"❌ Hali obuna bo'lmagansiz!\nQolganlar: {names}", show_alert=True)

# ============================================================
# SAHIFA ALMASHTIRISH
# ============================================================
@dp.callback_query(F.data.startswith("eppage_"))
async def episode_page_cb(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    code = parts[1]
    try:
        page = int(parts[2])
    except (ValueError, IndexError):
        return
    series = await load_series()
    if code not in series:
        await callback.answer("❌ Serial topilmadi!", show_alert=True)
        return
    total = len(series[code].get("episodes", []))
    title = series[code].get("title", "Serial")
    total_pages = (total + EP_PER_PAGE - 1) // EP_PER_PAGE
    start = page * EP_PER_PAGE + 1
    end = min(start + EP_PER_PAGE - 1, total)
    kb = build_episode_keyboard(code, total, page)
    await callback.message.edit_text(
        f"📺 <b>{title}</b> — barcha qismlar ({total} ta)\n"
        f"📄 Sahifa {page + 1}/{total_pages} ({start}-{end} qismlar):",
        reply_markup=kb
    )
    await callback.answer()

@dp.callback_query(F.data == "noop")
async def noop_cb(callback: types.CallbackQuery):
    await callback.answer()

# ============================================================
# QISMNI YUBORISH
# ============================================================
@dp.callback_query(F.data.startswith("ep_"))
async def send_episode(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    code = parts[1]
    try:
        ep_num = int(parts[2])
    except (ValueError, IndexError):
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
            await callback.message.answer_document(ep["file_id"], caption=caption, protect_content=True)
        else:
            await callback.message.answer_video(ep["file_id"], caption=caption, protect_content=True)
    except Exception as e:
        print(f"[XATO] Qism: {e}")
        await callback.message.answer("❌ Qismni yuborishda xato.")

# ============================================================
# QIDIRUV NATIJASINI TANLASH
# ============================================================
@dp.callback_query(F.data.startswith("pick_"))
async def pick_content(callback: types.CallbackQuery):
    parts = callback.data.split("_", 2)
    if len(parts) < 3:
        return
    kind, code = parts[1], parts[2]
    not_sub = await check_subscriptions(callback.from_user.id)
    if not_sub:
        await callback.answer("❌ Avval kanallarga obuna bo'ling!", show_alert=True)
        return
    await callback.answer()
    if kind == "movie":
        movies = await load_data()
        if code not in movies:
            await callback.message.answer("❌ Kino topilmadi.")
            return
        movie = movies[code]
        file_id = movie["file_id"]
        ftype = movie.get("type", "video")
        title = movie.get("title", "Kino")
        caption = f"🎬 <b>{title}</b>\n\nBoshqa kod yoki nom kiriting:"
        try:
            if ftype == "document":
                await callback.message.answer_document(file_id, caption=caption, protect_content=True)
            else:
                await callback.message.answer_video(file_id, caption=caption, protect_content=True)
        except Exception:
            await callback.message.answer("❌ Kino yuborishda xato.")
    elif kind == "series":
        series = await load_series()
        if code not in series:
            await callback.message.answer("❌ Serial topilmadi.")
            return
        await send_series_first(callback.message, code, series[code])

# ============================================================
# ADMIN — Parol
# ============================================================
@dp.message(AdminFSM.waiting_for_password, F.text)
async def admin_login(message: Message, state: FSMContext):
    if message.text.strip() == ADMIN_PASSWORD:
        user_id = message.from_user.id
        role = "👑 Bosh Admin" if user_id == OWNER_ID else "🔧 Admin"
        await message.answer(f"✅ <b>Xush kelibsiz! ({role})</b>", reply_markup=get_admin_keyboard(user_id))
        await state.set_state(AdminFSM.idle)
    else:
        await message.answer("❌ Noto'g'ri parol!")

# ============================================================
# ADMIN — KINO QO'SHISH
# ============================================================
@dp.message(F.text == "🎬 Kino qo'shish")
async def admin_add_movie(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    await message.answer("🎥 <b>Kino faylini yuboring:</b>\n💡 Document formatida yuboring!", reply_markup=ReplyKeyboardRemove())
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
    await message.answer("⚠️ Video yoki fayl yuboring!")

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
        await message.answer(f"⚠️ <b>'{code}'</b> kodi mavjud!")
        return
    data = await state.get_data()
    all_data[code] = {
        "file_id": data["file_id"],
        "type": data.get("file_type", "video"),
        "title": data.get("title", "Nomsiz"),
        "kind": "movie"
    }
    await save_data(all_data)
    uid = message.from_user.id
    await message.answer(
        f"✅ <b>Kino saqlandi!</b>\n\n"
        f"🎬 Nomi: <b>{data.get('title')}</b>\n"
        f"🔑 Kodi: <code>{code}</code>",
        reply_markup=get_admin_keyboard(uid)
    )
    await state.set_state(AdminFSM.idle)

# ============================================================
# ADMIN — SERIAL QO'SHISH
# ============================================================
@dp.message(F.text == "📺 Serial qo'shish")
async def admin_add_series(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    await message.answer("📺 <b>Serial nomini kiriting:</b>", reply_markup=ReplyKeyboardRemove())
    await state.set_state(AdminFSM.waiting_for_series_title)

@dp.message(AdminFSM.waiting_for_series_title, F.text)
async def admin_series_title(message: Message, state: FSMContext):
    title = message.text.strip()
    if len(title) > 100:
        await message.answer("❌ Nom 100 belgidan kam bo'lsin.")