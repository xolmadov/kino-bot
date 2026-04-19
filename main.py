import asyncio
import os
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
# BOT VA DISPATCHER
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
# SERIAL QISMLARINI KO'RSATISH
# ============================================================
async def send_series_first(message: Message, code: str, s: dict):
    total = len(s.get("episodes", []))
    if total == 0:
        await message.answer("❌ Bu serialda hali qism yo'q.")
        return
    title = s.get("title", "Serial")
    kb = build_episode_keyboard(code, total, 0)
    total_pages = (total + EP_PER_PAGE - 1) // EP_PER_PAGE
    start = 1
    end = min(EP_PER_PAGE, total)
    await message.answer(
        f"📺 <b>{title}</b> — barcha qismlar ({total} ta)\n"
        f"📄 Sahifa 1/{total_pages} ({start}-{end} qismlar):",
        reply_markup=kb
    )

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
        return
    await state.update_data(series_title=title)
    await message.answer("🔑 <b>Serial kodini kiriting:</b>\nMasalan: <code>squidgame2</code>")
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
    await message.answer("🔢 <b>Nechi qismdan iborat?</b> (sonni kiriting)")
    await state.set_state(AdminFSM.waiting_for_series_count)

@dp.message(AdminFSM.waiting_for_series_count, F.text)
async def admin_series_count(message: Message, state: FSMContext):
    try:
        count = int(message.text.strip())
        if count < 1 or count > 500:
            raise ValueError
    except ValueError:
        await message.answer("❌ 1-500 oralig'ida son kiriting.")
        return
    await state.update_data(series_count=count, series_episodes=[])
    data = await state.get_data()
    await message.answer(
        f"📤 <b>1-qismni yuboring</b>\n"
        f"(Jami: {count} qism)\n"
        f"💡 Document formatida yuboring!"
    )
    await state.set_state(AdminFSM.waiting_for_episode)

@dp.message(AdminFSM.waiting_for_episode, F.video | F.document)
async def admin_receive_episode(message: Message, state: FSMContext):
    data = await state.get_data()
    episodes = data.get("series_episodes", [])
    count = data.get("series_count", 1)

    if message.video:
        file_id, ftype = message.video.file_id, "video"
    else:
        file_id, ftype = message.document.file_id, "document"

    episodes.append({"file_id": file_id, "type": ftype})
    await state.update_data(series_episodes=episodes)

    current = len(episodes)
    if current < count:
        await message.answer(f"✅ {current}-qism qabul qilindi.\n📤 <b>{current + 1}-qismni yuboring:</b>")
    else:
        data = await state.get_data()
        all_series = await load_series()
        code = data["series_code"]
        all_series[code] = {
            "title": data["series_title"],
            "episodes": episodes
        }
        await save_series(all_series)
        uid = message.from_user.id
        await message.answer(
            f"✅ <b>Serial saqlandi!</b>\n\n"
            f"📺 Nomi: <b>{data['series_title']}</b>\n"
            f"🔑 Kodi: <code>{code}</code>\n"
            f"🎞 Qismlar: {count} ta",
            reply_markup=get_admin_keyboard(uid)
        )
        await state.set_state(AdminFSM.idle)

@dp.message(AdminFSM.waiting_for_episode)
async def admin_wrong_episode(message: Message):
    await message.answer("⚠️ Video yoki fayl yuboring!")

# ============================================================
# ADMIN — SERIALGA QISM QO'SHISH
# ============================================================
@dp.message(F.text == "➕ Serialga qism qo'shish")
async def admin_add_ep(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    await message.answer("🔑 <b>Serial kodini kiriting:</b>", reply_markup=ReplyKeyboardRemove())
    await state.set_state(AdminFSM.waiting_for_add_ep_code)

@dp.message(AdminFSM.waiting_for_add_ep_code, F.text)
async def admin_add_ep_code(message: Message, state: FSMContext):
    code = message.text.strip().lower()
    all_series = await load_series()
    if code not in all_series:
        await message.answer("❌ Bunday kodli serial topilmadi!")
        return
    s = all_series[code]
    await state.update_data(add_ep_code=code)
    await message.answer(
        f"📺 <b>{s['title']}</b> — hozir {len(s.get('episodes', []))} qism bor.\n"
        f"🔢 Nechta yangi qism qo'shmoqchisiz?"
    )
    await state.set_state(AdminFSM.waiting_for_add_ep_count)

@dp.message(AdminFSM.waiting_for_add_ep_count, F.text)
async def admin_add_ep_count(message: Message, state: FSMContext):
    try:
        count = int(message.text.strip())
        if count < 1 or count > 200:
            raise ValueError
    except ValueError:
        await message.answer("❌ 1-200 oralig'ida son kiriting.")
        return
    await state.update_data(add_ep_count=count, add_ep_files=[])
    data = await state.get_data()
    all_series = await load_series()
    s = all_series[data["add_ep_code"]]
    existing = len(s.get("episodes", []))
    await message.answer(
        f"📤 <b>{existing + 1}-qismni yuboring</b>\n"
        f"💡 Document formatida yuboring!"
    )
    await state.set_state(AdminFSM.waiting_for_add_ep_file)

@dp.message(AdminFSM.waiting_for_add_ep_file, F.video | F.document)
async def admin_add_ep_file(message: Message, state: FSMContext):
    data = await state.get_data()
    files = data.get("add_ep_files", [])
    count = data.get("add_ep_count", 1)
    code = data.get("add_ep_code")

    if message.video:
        file_id, ftype = message.video.file_id, "video"
    else:
        file_id, ftype = message.document.file_id, "document"

    files.append({"file_id": file_id, "type": ftype})
    await state.update_data(add_ep_files=files)

    all_series = await load_series()
    existing = len(all_series[code].get("episodes", []))
    current = len(files)

    if current < count:
        await message.answer(
            f"✅ {existing + current}-qism qabul qilindi.\n"
            f"📤 <b>{existing + current + 1}-qismni yuboring:</b>"
        )
    else:
        for f in files:
            all_series[code]["episodes"].append(f)
        await save_series(all_series)
        total = len(all_series[code]["episodes"])
        uid = message.from_user.id
        await message.answer(
            f"✅ <b>{count} ta yangi qism qo'shildi!</b>\n"
            f"📺 Serial: <b>{all_series[code]['title']}</b>\n"
            f"🎞 Jami qismlar: {total} ta",
            reply_markup=get_admin_keyboard(uid)
        )
        await state.set_state(AdminFSM.idle)

@dp.message(AdminFSM.waiting_for_add_ep_file)
async def admin_wrong_add_ep(message: Message):
    await message.answer("⚠️ Video yoki fayl yuboring!")

# ============================================================
# ADMIN — BARCHA KINOLAR
# ============================================================
@dp.message(F.text == "📁 Barcha kinolar")
async def admin_list_movies(message: Message):
    if not await is_admin(message.from_user.id):
        return
    movies = await load_data()
    series = await load_series()
    text = "📁 <b>Barcha kinolar:</b>\n\n"
    if movies:
        text += "🎬 <b>Kinolar:</b>\n"
        for code, v in movies.items():
            title = v.get("title", "Nomsiz") if isinstance(v, dict) else "Nomsiz"
            text += f"  • <code>{code}</code> — {title}\n"
    else:
        text += "🎬 Kinolar yo'q\n"
    text += "\n"
    if series:
        text += "📺 <b>Seriallar:</b>\n"
        for code, v in series.items():
            title = v.get("title", "Nomsiz")
            ep_count = len(v.get("episodes", []))
            text += f"  • <code>{code}</code> — {title} ({ep_count} qism)\n"
    else:
        text += "📺 Seriallar yo'q\n"
    await message.answer(text[:4000])

# ============================================================
# ADMIN — KINO O'CHIRISH
# ============================================================
@dp.message(F.text == "🗑 Kino o'chirish")
async def admin_delete_movie(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    await message.answer("🗑 <b>O'chirmoqchi bo'lgan kino/serial kodini kiriting:</b>", reply_markup=ReplyKeyboardRemove())
    await state.set_state(AdminFSM.waiting_for_delete)

@dp.message(AdminFSM.waiting_for_delete, F.text)
async def admin_confirm_delete(message: Message, state: FSMContext):
    code = message.text.strip().lower()
    movies = await load_data()
    series = await load_series()
    uid = message.from_user.id
    if code in movies:
        title = movies[code].get("title", "Nomsiz")
        del movies[code]
        await save_data(movies)
        await message.answer(f"✅ <b>'{title}'</b> kinosi o'chirildi.", reply_markup=get_admin_keyboard(uid))
    elif code in series:
        title = series[code].get("title", "Nomsiz")
        del series[code]
        await save_series(series)
        await message.answer(f"✅ <b>'{title}'</b> seriali o'chirildi.", reply_markup=get_admin_keyboard(uid))
    else:
        await message.answer(f"❌ <b>'{code}'</b> kodi topilmadi!", reply_markup=get_admin_keyboard(uid))
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
        "Format: <code>kanal_nomi|kanal_id|https://t.me/kanal</code>\n\n"
        "Misol: <code>Kino Kanal|-1001234567890|https://t.me/kinokanal</code>",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.set_state(AdminFSM.waiting_for_channel)

@dp.message(AdminFSM.waiting_for_channel, F.text)
async def admin_save_channel(message: Message, state: FSMContext):
    uid = message.from_user.id
    try:
        parts = message.text.strip().split("|")
        if len(parts) != 3:
            raise ValueError
        name, ch_id, link = parts[0].strip(), parts[1].strip(), parts[2].strip()
        ch_id = int(ch_id)
        channels = await load_channels()
        if any(c["id"] == ch_id for c in channels):
            await message.answer("⚠️ Bu kanal allaqachon mavjud!", reply_markup=get_admin_keyboard(uid))
            await state.set_state(AdminFSM.idle)
            return
        channels.append({"name": name, "id": ch_id, "link": link})
        await save_channels(channels)
        await message.answer(f"✅ <b>{name}</b> kanali qo'shildi!", reply_markup=get_admin_keyboard(uid))
    except (ValueError, IndexError):
        await message.answer(
            "❌ Noto'g'ri format!\n"
            "Format: <code>kanal_nomi|kanal_id|https://t.me/kanal</code>",
            reply_markup=get_admin_keyboard(uid)
        )
    await state.set_state(AdminFSM.idle)

# ============================================================
# ADMIN — KANALLAR RO'YXATI
# ============================================================
@dp.message(F.text == "📋 Kanallar ro'yxati")
async def admin_list_channels(message: Message):
    if not await is_admin(message.from_user.id):
        return
    channels = await load_channels()
    if not channels:
        await message.answer("📋 Hozircha kanal yo'q.")
        return
    text = "📋 <b>Kanallar ro'yxati:</b>\n\n"
    for i, ch in enumerate(channels, 1):
        text += f"{i}. <b>{ch['name']}</b>\n   ID: <code>{ch['id']}</code>\n   Link: {ch['link']}\n\n"
    await message.answer(text)

# ============================================================
# ADMIN — STATISTIKA
# ============================================================
@dp.message(F.text == "📊 Statistika")
async def admin_stats(message: Message):
    if not await is_admin(message.from_user.id):
        return
    stats = await load_stats()
    movies = await load_data()
    series = await load_series()
    users_count = len(stats.get("users", []))
    requests = stats.get("requests", 0)
    movies_count = len(movies)
    series_count = len(series)
    await message.answer(
        f"📊 <b>Statistika:</b>\n\n"
        f"👥 Foydalanuvchilar: <b>{users_count}</b>\n"
        f"📨 So'rovlar: <b>{requests}</b>\n"
        f"🎬 Kinolar: <b>{movies_count}</b>\n"
        f"📺 Seriallar: <b>{series_count}</b>"
    )

# ============================================================
# ADMIN — XABAR YUBORISH
# ============================================================
@dp.message(F.text == "📣 Xabar yuborish")
async def admin_broadcast_start(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    await message.answer("📣 <b>Barcha foydalanuvchilarga yuboriladigan xabarni kiriting:</b>", reply_markup=ReplyKeyboardRemove())
    await state.set_state(AdminFSM.waiting_for_broadcast)

@dp.message(AdminFSM.waiting_for_broadcast, F.text)
async def admin_broadcast_send(message: Message, state: FSMContext):
    uid = message.from_user.id
    subscribers = await load_subscribers()
    text = message.text.strip()
    success, failed = 0, 0
    for user_id in subscribers:
        try:
            await bot.send_message(user_id, text)
            success += 1
        except Exception:
            failed += 1
    await message.answer(
        f"📣 <b>Xabar yuborildi!</b>\n\n"
        f"✅ Muvaffaqiyatli: {success}\n"
        f"❌ Xato: {failed}",
        reply_markup=get_admin_keyboard(uid)
    )
    await state.set_state(AdminFSM.idle)

# ============================================================
# ADMIN — ADMIN QO'SHISH (faqat OWNER)
# ============================================================
@dp.message(F.text == "👑 Admin qo'shish")
async def admin_add_admin(message: Message, state: FSMContext):
    if message.from_user.id != OWNER_ID:
        return
    await message.answer("👤 <b>Yangi admin Telegram ID sini kiriting:</b>", reply_markup=ReplyKeyboardRemove())
    await state.set_state(AdminFSM.waiting_for_new_admin_id)

@dp.message(AdminFSM.waiting_for_new_admin_id, F.text)
async def admin_save_admin(message: Message, state: FSMContext):
    uid = message.from_user.id
    try:
        new_id = int(message.text.strip())
        admins = await load_admins()
        admins[str(new_id)] = True
        await save_admins(admins)
        await message.answer(f"✅ <b>{new_id}</b> admin qo'shildi!", reply_markup=get_admin_keyboard(uid))
    except ValueError:
        await message.answer("❌ Noto'g'ri ID!", reply_markup=get_admin_keyboard(uid))
    await state.set_state(AdminFSM.idle)

# ============================================================
# ADMIN — ADMINLAR RO'YXATI
# ============================================================
@dp.message(F.text == "👥 Adminlar ro'yxati")
async def admin_list_admins(message: Message):
    if message.from_user.id != OWNER_ID:
        return
    admins = await load_admins()
    text = f"👥 <b>Adminlar ro'yxati:</b>\n\n👑 Bosh Admin: <code>{OWNER_ID}</code>\n\n"
    if admins:
        for aid in admins:
            text += f"🔧 Admin: <code>{aid}</code>\n"
    else:
        text += "Boshqa adminlar yo'q."
    await message.answer(text)

# ============================================================
# ADMIN — CHIQISH
# ============================================================
@dp.message(F.text == "🚪 Chiqish")
async def admin_logout(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    await state.clear()
    await message.answer("🚪 <b>Admin paneldan chiqdingiz.</b>", reply_markup=ReplyKeyboardRemove())

# ============================================================
# FOYDALANUVCHI — KOD YOKI NOM QIDIRISH
# ============================================================
@dp.message(UserFSM.waiting_for_movie_code, F.text)
async def user_search(message: Message, state: FSMContext):
    user_id = message.from_user.id
    not_sub = await check_subscriptions(user_id)
    if not_sub:
        await show_subscribe_message(message, not_sub)
        return

    query = message.text.strip()
    movies = await load_data()
    series = await load_series()

    # To'g'ridan-to'g'ri kod
    if query.lower() in movies:
        code = query.lower()
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

    if query.lower() in series:
        code = query.lower()
        await send_series_first(message, code, series[code])
        return

    # Qidiruv
    results = await search_content(query)
    if not results:
        await message.answer(
            "❌ <b>Hech narsa topilmadi!</b>\n\n"
            "🔍 Boshqa kalit so'z yoki to'g'ri kod kiriting:"
        )
        return

    if len(results) == 1:
        r = results[0]
        if r["kind"] == "movie":
            movie = movies[r["code"]]
            file_id = movie["file_id"]
            ftype = movie.get("type", "video")
            caption = f"🎬 <b>{r['title']}</b>\n\nBoshqa kod yoki nom kiriting:"
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

    # Bir nechta natija
    buttons = []
    for r in results[:10]:
        icon = "🎬" if r["kind"] == "movie" else "📺"
        extra = f" ({r['extra']})" if r["extra"] else ""
        buttons.append([InlineKeyboardButton(
            text=f"{icon} {r['title']}{extra}",
            callback_data=f"pick_{r['kind']}_{r['code']}"
        )])
    await message.answer(
        f"🔍 <b>Qidiruv natijalari ({len(results)} ta):</b>\n\nQaysi birini xohlaysiz?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )

# ============================================================
# BOTNI ISHGA TUSHIRISH
# ============================================================
async def main():
    print("🤖 Bot ishga tushmoqda...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
