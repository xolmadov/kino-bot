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
    r = await http_client.get(
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
    await http_client.post(
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

# Global HTTP client — RAM tejash uchun
http_client = httpx.AsyncClient(timeout=10)

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
        row.append(InlineKeyboardButton(text=f"{i}ep", callback_data=f"ep_{code}_{i}"))
        if len(row) == 5:
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
    await callback.message.edit_text("📺", reply_markup=kb)
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
        return
    await state.update_data(series_title=title, episodes=[])
    await message.answer(f"✅ Nomi: <b>{title}</b>\n\n🔑 <b>Serial kodini kiriting:</b>")
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
        await message.answer(f"⚠️ <b>'{code}'</b> kodi mavjud!")
        return
    await state.update_data(series_code=code)
    await message.answer("🔢 <b>Nechta qism yuklaysiz hozir?</b> (1-100)\n💡 Keyin yana qo'shish mumkin!")
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
    await message.answer(f"📺 <b>{data['series_title']}</b>\n\n📤 <b>1-qismni yuboring:</b>")
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
        all_series = await load_series()
        code = data["series_code"]
        all_series[code] = {"title": data["series_title"], "kind": "series", "episodes": episodes}
        await save_series(all_series)
        uid = message.from_user.id
        await message.answer(
            f"✅ <b>Serial saqlandi!</b>\n\n"
            f"📺 Nomi: <b>{data['series_title']}</b>\n"
            f"🔑 Kodi: <code>{code}</code>\n"
            f"🎞 Qismlar: <b>{len(episodes)} ta</b>",
            reply_markup=get_admin_keyboard(uid)
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
    await message.answer(f"⚠️ {data.get('current_episode', 1)}-qism uchun video yoki fayl yuboring!")

# ============================================================
# ADMIN — SERIALGA QISM QO'SHISH
# ============================================================
@dp.message(F.text == "➕ Serialga qism qo'shish")
async def admin_add_ep_start(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    series = await load_series()
    if not series:
        await message.answer("❌ Hech qanday serial yo'q.")
        return
    text = "📺 <b>Serial kodini kiriting:</b>\n\n"
    for k, v in series.items():
        ep_count = len(v.get("episodes", []))
        text += f"  • <code>{k}</code> — {v.get('title', 'Nomsiz')} ({ep_count} qism)\n"
    await message.answer(text, reply_markup=ReplyKeyboardRemove())
    await state.set_state(AdminFSM.waiting_for_add_ep_code)

@dp.message(AdminFSM.waiting_for_add_ep_code, F.text)
async def admin_add_ep_code(message: Message, state: FSMContext):
    code = message.text.strip().lower()
    series = await load_series()
    if code not in series:
        await message.answer(f"❌ <b>'{code}'</b> topilmadi. Qaytadan kiriting:")
        return
    s = series[code]
    current_count = len(s.get("episodes", []))
    await state.update_data(add_ep_code=code, add_ep_start_from=current_count + 1)
    await message.answer(
        f"✅ Serial: <b>{s['title']}</b>\n"
        f"🎞 Hozirgi qismlar: <b>{current_count} ta</b>\n\n"
        "🔢 <b>Nechta yangi qism qo'shmoqchisiz?</b> (1-100):"
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
    await message.answer(f"📤 <b>{data.get('add_ep_start_from', 1)}-qismni yuboring:</b>")
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
    start_from = data.get("add_ep_start_from", 1)
    current_num = start_from + uploaded - 1
    new_episodes.append({"file_id": file_id, "type": ftype})
    await state.update_data(new_episodes=new_episodes, add_ep_uploaded=uploaded)
    if uploaded >= total:
        code = data["add_ep_code"]
        series = await load_series()
        series[code]["episodes"] = series[code].get("episodes", []) + new_episodes
        total_now = len(series[code]["episodes"])
        await save_series(series)
        uid = message.from_user.id
        await message.answer(
            f"✅ <b>Qismlar qo'shildi!</b>\n\n"
            f"📺 Serial: <b>{series[code]['title']}</b>\n"
            f"🎞 Jami: <b>{total_now} ta</b> | ➕ Qo'shildi: <b>{total} ta</b>",
            reply_markup=get_admin_keyboard(uid)
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
    n = data.get("add_ep_start_from", 1) + data.get("add_ep_uploaded", 0)
    await message.answer(f"⚠️ {n}-qism uchun video yoki fayl yuboring!")

# ============================================================
# ADMIN — BARCHA KINOLAR
# ============================================================
@dp.message(F.text == "📁 Barcha kinolar")
async def kino_list(message: Message):
    if not await is_admin(message.from_user.id):
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
    if not await is_admin(message.from_user.id):
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
            text += f"  • <code>{k}</code> — {v.get('title', 'Nomsiz')} ({len(v.get('episodes', []))} qism)\n"
    await message.answer(text, reply_markup=ReplyKeyboardRemove())
    await state.set_state(AdminFSM.waiting_for_delete)

@dp.message(AdminFSM.waiting_for_delete, F.text)
async def admin_delete(message: Message, state: FSMContext):
    code = message.text.strip().lower()
    movies = await load_data()
    series = await load_series()
    uid = message.from_user.id
    if code in movies:
        title = movies[code].get("title", "Nomsiz") if isinstance(movies[code], dict) else "Nomsiz"
        del movies[code]
        await save_data(movies)
        await message.answer(f"✅ Kino <b>'{title}'</b> o'chirildi!", reply_markup=get_admin_keyboard(uid))
    elif code in series:
        title = series[code].get("title", "Nomsiz")
        del series[code]
        await save_series(series)
        await message.answer(f"✅ Serial <b>'{title}'</b> o'chirildi!", reply_markup=get_admin_keyboard(uid))
    else:
        await message.answer(f"❌ <b>'{code}'</b> topilmadi.", reply_markup=get_admin_keyboard(uid))
    await state.set_state(AdminFSM.idle)

# ============================================================
# ADMIN — KANAL QO'SHISH
# ============================================================
@dp.message(F.text == "📢 Kanal qo'shish")
async def admin_add_channel(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
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
    uid = message.from_user.id
    try:
        parts = [p.strip() for p in message.text.split("|")]
        if len(parts) != 3:
            raise ValueError()
        ch_id = int(parts[0])
        ch_link = parts[1]
        ch_name = parts[2]
        if not ch_link.startswith("https://"):
            raise ValueError()
    except Exception:
        await message.answer(
            "❌ Noto'g'ri format!\n\n"
            "To'g'ri format:\n<code>-1001234567890 | https://t.me/kanal | Kanal nomi</code>"
        )
        return
    channels = await load_channels()
    if len(channels) >= 10:
        await message.answer("❌ Maksimal 10 ta kanal qo'shish mumkin!", reply_markup=get_admin_keyboard(uid))
        await state.set_state(AdminFSM.idle)
        return
    if any(c["id"] == ch_id for c in channels):
        await message.answer("⚠️ Bu kanal allaqachon qo'shilgan!", reply_markup=get_admin_keyboard(uid))
        await state.set_state(AdminFSM.idle)
        return
    channels.append({"id": ch_id, "link": ch_link, "name": ch_name})
    await save_channels(channels)
    await message.answer(
        f"✅ <b>Kanal qo'shildi!</b>\n\n"
        f"📢 Nomi: <b>{ch_name}</b>\n"
        f"🆔 ID: <code>{ch_id}</code>\n"
        f"📋 Jami: {len(channels)}/10",
        reply_markup=get_admin_keyboard(uid)
    )
    await state.set_state(AdminFSM.idle)

# ============================================================
# ADMIN — KANALLAR RO'YXATI
# ============================================================
@dp.message(F.text == "📋 Kanallar ro'yxati")
async def admin_channels_list(message: Message):
    if not await is_admin(message.from_user.id):
        return
    channels = await load_channels()
    if not channels:
        await message.answer("📋 Kanal yo'q.\n⚠️ Kanal bo'lmasa, hamma ko'ra oladi.")
        return
    text = f"📋 <b>Kanallar ({len(channels)}/10):</b>\n\n"
    for i, ch in enumerate(channels, 1):
        text += f"{i}. <b>{ch['name']}</b> — <code>{ch['id']}</code>\n"
    buttons = [[InlineKeyboardButton(text=f"🗑 {ch['name']}", callback_data=f"del_ch_{ch['id']}")] for ch in channels]
    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

@dp.callback_query(F.data.startswith("del_ch_"))
async def delete_channel_cb(callback: types.CallbackQuery):
    if not await is_admin(callback.from_user.id):
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
    if not await is_admin(message.from_user.id):
        return
    movies = await load_data()
    series = await load_series()
    stats = await load_stats()
    channels = await load_channels()
    admins = await load_admins()
    subscribers = await load_subscribers()
    await message.answer(
        f"📊 <b>Bot statistikasi:</b>\n\n"
        f"🎬 Kinolar: <b>{len(movies)}</b>\n"
        f"📺 Seriallar: <b>{len(series)}</b>\n"
        f"👤 Foydalanuvchilar: <b>{len(stats.get('users', []))}</b>\n"
        f"💾 Doimiy obunachlar: <b>{len(subscribers)}</b>\n"
        f"📥 Jami so'rovlar: <b>{stats.get('requests', 0)}</b>\n"
        f"📢 Kanallar: <b>{len(channels)}/10</b>\n"
        f"🔧 Adminlar: <b>{len(admins)}</b> (+ 1 owner)"
    )

# ============================================================
# ADMIN — OMMAVIY XABAR
# ============================================================
@dp.message(F.text == "📣 Xabar yuborish")
async def admin_broadcast_start(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    subscribers = await load_subscribers()
    await message.answer(
        f"📣 <b>Ommaviy xabar</b>\n"
        f"💾 Doimiy obunachlar: <b>{len(subscribers)}</b>\n\n"
        "Xabarni kiriting (/cancel — bekor qilish):",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.set_state(AdminFSM.waiting_for_broadcast)

@dp.message(AdminFSM.waiting_for_broadcast, F.text == "/cancel")
async def broadcast_cancel(message: Message, state: FSMContext):
    uid = message.from_user.id
    await message.answer("❌ Bekor qilindi.", reply_markup=get_admin_keyboard(uid))
    await state.set_state(AdminFSM.idle)

@dp.message(AdminFSM.waiting_for_broadcast, F.text)
async def broadcast_send(message: Message, state: FSMContext):
    subscribers = await load_subscribers()
    uid = message.from_user.id
    if not subscribers:
        await message.answer("👤 Obunachlar yo'q.", reply_markup=get_admin_keyboard(uid))
        await state.set_state(AdminFSM.idle)
        return
    sent = failed = 0
    status_msg = await message.answer(f"⏳ Yuborilmoqda... 0/{len(subscribers)}")
    for i, u in enumerate(subscribers):
        try:
            await bot.send_message(u, f"📣 <b>Yangilik:</b>\n\n{message.text}")
            sent += 1
        except Exception:
            failed += 1
        if (i + 1) % 20 == 0:
            try:
                await status_msg.edit_text(f"⏳ Yuborilmoqda... {i+1}/{len(subscribers)}")
            except Exception:
                pass
        await asyncio.sleep(0.05)
    await status_msg.edit_text(
        f"✅ <b>Xabar yuborildi!</b>\n✔️ Muvaffaqiyatli: <b>{sent}</b>\n❌ Xato: <b>{failed}</b>"
    )
    await message.answer("Admin menyu:", reply_markup=get_admin_keyboard(uid))
    await state.set_state(AdminFSM.idle)

# ============================================================
# OWNER — ADMIN QO'SHISH
# ============================================================
@dp.message(F.text == "👑 Admin qo'shish")
async def owner_add_admin(message: Message, state: FSMContext):
    if message.from_user.id != OWNER_ID:
        return
    await message.answer(
        "👑 <b>Yangi admin qo'shish</b>\n\n"
        "Admin bo'lajak odamning <b>Telegram ID</b>sini kiriting:\n\n"
        "💡 ID topish: @userinfobot ga /start yuboring\n\n"
        "/cancel — bekor qilish",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.set_state(AdminFSM.waiting_for_new_admin_id)

@dp.message(AdminFSM.waiting_for_new_admin_id, F.text == "/cancel")
async def add_admin_cancel(message: Message, state: FSMContext):
    await message.answer("❌ Bekor qilindi.", reply_markup=get_admin_keyboard(OWNER_ID))
    await state.set_state(AdminFSM.idle)

@dp.message(AdminFSM.waiting_for_new_admin_id, F.text)
async def owner_save_admin(message: Message, state: FSMContext):
    try:
        new_admin_id = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Faqat raqam kiriting (Telegram ID).")
        return
    if new_admin_id == OWNER_ID:
        await message.answer("⚠️ Bu siz o'zingiz — allaqachon bosh adminsiz!")
        return
    admins = await load_admins()
    if str(new_admin_id) in admins:
        name = admins[str(new_admin_id)].get('name', 'Noma\'lum')
        await message.answer(f"⚠️ Bu foydalanuvchi allaqachon admin!\n👤 Ismi: {name}", reply_markup=get_admin_keyboard(OWNER_ID))
        await state.set_state(AdminFSM.idle)
        return
    try:
        chat = await bot.get_chat(new_admin_id)
        name = chat.full_name or f"ID: {new_admin_id}"
        username = f"@{chat.username}" if chat.username else "username yo'q"
    except Exception:
        name = f"ID: {new_admin_id}"
        username = "noma'lum"
    admins[str(new_admin_id)] = {"name": name, "username": username, "added_by": OWNER_ID}
    await save_admins(admins)
    try:
        await bot.send_message(new_admin_id, "🎉 <b>Siz admin qilindingiz!</b>\n\nBotga /start yuboring va parolni kiriting.")
    except Exception:
        pass
    await message.answer(
        f"✅ <b>Yangi admin qo'shildi!</b>\n\n"
        f"👤 Ismi: <b>{name}</b>\n"
        f"🆔 ID: <code>{new_admin_id}</code>\n"
        f"📱 Username: {username}",
        reply_markup=get_admin_keyboard(OWNER_ID)
    )
    await state.set_state(AdminFSM.idle)

# ============================================================
# OWNER — ADMINLAR RO'YXATI VA O'CHIRISH
# ============================================================
@dp.message(F.text == "👥 Adminlar ro'yxati")
async def owner_admins_list(message: Message):
    if message.from_user.id != OWNER_ID:
        return
    admins = await load_admins()
    text = "👥 <b>Adminlar ro'yxati:</b>\n\n"
    text += f"👑 <b>Bosh Admin (siz)</b>\n   🆔 <code>{OWNER_ID}</code>\n\n"
    if not admins:
        text += "🔧 Hozircha qo'shimcha admin yo'q."
        await message.answer(text)
        return
    for uid, info in admins.items():
        name = info.get('name', 'Noma\'lum')
        uname = info.get('username', 'noma\'lum')
        text += f"🔧 <b>{name}</b>\n   🆔 <code>{uid}</code>\n   📱 {uname}\n\n"
    buttons = []
    for uid, info in admins.items():
        name = info.get('name', 'Noma\'lum')
        buttons.append([InlineKeyboardButton(text=f"🗑 {name} o'chirish", callback_data=f"del_admin_{uid}")])
    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

@dp.callback_query(F.data.startswith("del_admin_"))
async def delete_admin_cb(callback: types.CallbackQuery):
    if callback.from_user.id != OWNER_ID:
        await callback.answer("❌ Faqat bosh admin o'chira oladi!", show_alert=True)
        return
    admin_id = callback.data.replace("del_admin_", "")
    admins = await load_admins()
    if admin_id not in admins:
        await callback.answer("❌ Bu admin topilmadi!", show_alert=True)
        return
    name = admins[admin_id].get("name", "Noma'lum")
    del admins[admin_id]
    await save_admins(admins)
    try:
        await bot.send_message(int(admin_id), "ℹ️ Sizning admin huquqlaringiz olib tashlandi.")
    except Exception:
        pass
    await callback.answer(f"✅ {name} admin ro'yxatidan o'chirildi!", show_alert=True)
    await callback.message.delete()

# ============================================================
# ADMIN — CHIQISH
# ============================================================
@dp.message(F.text == "🚪 Chiqish")
async def admin_logout(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    await state.clear()
    await message.answer("👋 Admin paneldan chiqdingiz.", reply_markup=ReplyKeyboardRemove())

@dp.message(F.text == "/stats")
async def stats_cmd(message: Message):
    if not await is_admin(message.from_user.id):
        return
    movies = await load_data()
    series = await load_series()
    stats = await load_stats()
    subscribers = await load_subscribers()
    await message.answer(
        f"🎬 {len(movies)} kino | 📺 {len(series)} serial | "
        f"👤 {len(stats.get('users', []))} user | 💾 {len(subscribers)} obunachi"
    )

# ============================================================
# FOYDALANUVCHI — KOD YOKI NOM
# ============================================================
async def send_series_first(message: Message, code: str, s: dict):
    title = s.get("title", "Serial")
    episodes = s.get("episodes", [])
    total = len(episodes)
    if not episodes:
        await message.answer("❌ Serial qismlari topilmadi.")
        return
    ep = episodes[0]
    caption = f"📺 <b>{title}</b>\n🎞 <b>1ep</b>"
    try:
        if ep["type"] == "document":
            await message.answer_document(ep["file_id"], caption=caption, protect_content=True)
        else:
            await message.answer_video(ep["file_id"], caption=caption, protect_content=True)
    except Exception as e:
        print(f"[XATO] 1-qism: {e}")
        await message.answer("❌ Serial yuborishda xato.")
        return
    if total > 1:
        kb = build_episode_keyboard(code, total, 0)
        await message.answer("📺", reply_markup=kb)

@dp.message(UserFSM.waiting_for_movie_code, F.text)
async def user_enter_code(message: Message, state: FSMContext):
    user_id = message.from_user.id
    not_sub = await check_subscriptions(user_id)
    if not_sub:
        await show_subscribe_message(message, not_sub)
        await state.clear()
        return
    query = message.text.strip()
    code = query.lower()
    movies = await load_data()
    series = await load_series()
    if code in movies:
        movie = movies[code]
        file_id = movie["file_id"]
        ftype = movie.get("type", "video")
        title = movie.get("title", "Kino")
        caption = f"🎬 <b>{title}</b>\n\nBoshqa kod yoki nom kiriting:"
        try:
            if ftype == "document":
                await message.answer_document(file_id, caption=caption, protect_content=True)
            else:
                await message.answer_video(file_id, caption=caption, protect_content=True)
        except Exception:
            await message.answer("❌ Kino yuborishda xato.")
        return
    if code in series:
        await send_series_first(message, code, series[code])
        return
    results = await search_content(query)
    if not results:
        await message.answer(f"❌ <b>'{query}'</b> bo'yicha hech narsa topilmadi.\n\nKod yoki nomni to'g'ri kiriting.")
        return
    if len(results) == 1:
        r = results[0]
        if r["kind"] == "movie":
            movie = movies[r["code"]]
            file_id = movie["file_id"]
            ftype = movie.get("type", "video")
            title = movie.get("title", "Kino")
            caption = f"🎬 <b>{title}</b>\n\nBoshqa kod yoki nom kiriting:"
            try:
                if ftype == "document":
                    await message.answer_document(file_id, caption=caption, protect_content=True)
                else:
                    await message.answer_video(file_id, caption=caption, protect_content=True)
            except Exception:
                await message.answer("❌ Kino yuborishda xato.")
        else:
            await send_series_first(message, r["code"], series[r["code"]])
        return
    buttons = []
    for r in results[:10]:
        icon = "🎬" if r["kind"] == "movie" else "📺"
        extra = f" ({r['extra']})" if r["extra"] else ""
        buttons.append([InlineKeyboardButton(
            text=f"{icon} {r['title']}{extra}",
            callback_data=f"pick_{r['kind']}_{r['code']}"
        )])
    await message.answer(
        f"🔍 <b>'{query}'</b> bo'yicha {len(results)} ta natija:\n\nQaysi birini ko'rmoqchisiz?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )

@dp.message(F.text)
async def handle_text(message: Message, state: FSMContext):
    user_id = message.from_user.id
    current_state = await state.get_state()
    if await is_admin(user_id) and current_state is None:
        await message.answer("/start yuboring.")
        return
    if current_state is None:
        not_sub = await check_subscriptions(user_id)
        if not_sub:
            await show_subscribe_message(message, not_sub)
        else:
            await message.answer("🔑 Kino yoki serial kodini yoki nomini kiriting:")
            await state.set_state(UserFSM.waiting_for_movie_code)

# ============================================================
# ISHGA TUSHIRISH
# ============================================================
async def main():
    print("=" * 40)
    print("🚀 Bot ishga tushdi! (Supabase rejimi)")
    print(f"👑 Owner ID: {OWNER_ID}")
    movies = await load_data()
    series = await load_series()
    subscribers = await load_subscribers()
    print(f"🎬 Kinolar: {len(movies)} ta | 📺 Seriallar: {len(series)} ta")
    print(f"💾 Obunachlar: {len(subscribers)} ta")
    print("=" * 40)
    await bot.delete_webhook(drop_pending_updates=True)
    try:
        await dp.start_polling(bot)
    finally:
        await http_client.aclose()

if __name__ == "__main__":
    asyncio.run(main())
