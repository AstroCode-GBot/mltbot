import logging, re, html
from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.fsm.storage.memory import MemoryStorage
from config import settings
from database import pool

logging.basicConfig(level=logging.INFO)
bot = Bot(settings.bot_token)
dp = Dispatcher(storage=MemoryStorage())
router = Router()
dp.include_router(router)
BRAND = "\n\nDeveloper: @QUANTUM_NULL"

def main_keyboard():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📚 Browse Classes"), KeyboardButton(text="🔎 Search Files")],
        [KeyboardButton(text="📁 All Files"), KeyboardButton(text="📤 Share Contact", request_contact=True)],
        [KeyboardButton(text="👤 My Profile"), KeyboardButton(text="📩 Contact Admin")],
        [KeyboardButton(text="ℹ️ Help")]
    ], resize_keyboard=True)

async def get_user(uid):
    async with pool().acquire() as c:
        return await c.fetchrow("SELECT * FROM users WHERE user_id=$1", uid)

async def is_admin(uid):
    if uid == settings.owner_id: return True
    async with pool().acquire() as c:
        return bool(await c.fetchval("SELECT 1 FROM admins WHERE user_id=$1", uid))

async def register_user(m: Message):
    u = m.from_user
    name = " ".join(x for x in [u.first_name, u.last_name] if x)
    async with pool().acquire() as c:
        row = await c.fetchrow("INSERT INTO users(user_id,full_name,username) VALUES($1,$2,$3) ON CONFLICT(user_id) DO NOTHING RETURNING user_id", u.id, name, u.username)
        await c.execute("UPDATE users SET full_name=$2, username=$3 WHERE user_id=$1", u.id, name, u.username)
    if row:
        text = f"🆕 <b>NEW USER JOINED</b>\n👤 {html.escape(name)}\n🆔 <code>{u.id}</code>\n🔗 @{u.username or 'N/A'}\n🔐 PENDING{BRAND}"
        for admin_id in set(settings.admin_ids + ((settings.owner_id,) if settings.owner_id else ())):
            try: await bot.send_message(admin_id, text)
            except Exception: logging.exception("Admin notification failed")

async def access_ok(m: Message):
    user = await get_user(m.from_user.id)
    if not user or user["is_blocked"]:
        await m.answer("🔒 <b>ACCESS RESTRICTED</b>\nYour account is unavailable. Please contact an administrator." + BRAND, reply_markup=main_keyboard())
        return False
    if user["verification_status"] != "verified":
        await m.answer("🔒 <b>ACCESS RESTRICTED</b>\nYour account has not been verified yet.\nPlease contact the administrator to request access." + BRAND, reply_markup=main_keyboard())
        return False
    return True

@router.message(CommandStart())
async def start(m: Message):
    await register_user(m)
    user = await get_user(m.from_user.id)
    status = user["verification_status"] if user else "pending"
    if status != "verified":
        await m.answer("🌟 <b>Welcome to MLT CLASSES VAULT!</b>\n\nYour educational resource library.\n📚 Class Materials\n🎥 Recorded Lectures\n📄 PDF Notes\n🔎 Smart File Search\n\nYour account is pending verification. Contact an administrator to request access." + BRAND, reply_markup=main_keyboard())
    else:
        await m.answer("🌟 <b>Welcome back to MLT CLASSES VAULT!</b>\nFind your learning materials below." + BRAND, reply_markup=main_keyboard())

@router.message(Command("help"))
@router.message(F.text == "ℹ️ Help")
async def help_cmd(m: Message):
    await m.answer("<b>MLT CLASSES VAULT — Help</b>\nUse Search Files or Browse Classes to find materials. Access requires administrator verification." + BRAND, reply_markup=main_keyboard())

@router.message(Command("profile"))
@router.message(F.text == "👤 My Profile")
async def profile(m: Message):
    await register_user(m)
    u = await get_user(m.from_user.id)
    await m.answer(f"👤 <b>MY PROFILE</b>\nName: {html.escape(u['full_name'])}\nUsername: @{u['username'] or 'N/A'}\nUID: <code>{u['user_id']}</code>\nVerification: {u['verification_status'].upper()}\nPhone: {u['phone'] or 'Not shared'}\nDownloads: {u['download_count']}\nJoined: {u['joined_at'].strftime('%Y-%m-%d')}{BRAND}", reply_markup=main_keyboard())

@router.message(F.contact)
async def save_contact(m: Message):
    if not m.contact or m.contact.user_id != m.from_user.id:
        return await m.answer("Please share your own contact using the keyboard button." + BRAND)
    async with pool().acquire() as c:
        await c.execute("UPDATE users SET phone=$2 WHERE user_id=$1", m.from_user.id, m.contact.phone_number)
    await m.answer("✅ Contact saved. Thank you!" + BRAND, reply_markup=main_keyboard())
    text = f"📞 <b>NEW CONTACT RECEIVED</b>\nUID: <code>{m.from_user.id}</code>\nPhone: {html.escape(m.contact.phone_number)}{BRAND}"
    for aid in set(settings.admin_ids + ((settings.owner_id,) if settings.owner_id else ())):
        try: await bot.send_message(aid, text)
        except Exception: pass

@router.message(Command("verify"))
async def verify(m: Message):
    if not await is_admin(m.from_user.id): return
    parts = (m.text or "").split()
    if len(parts) != 2 or not parts[1].isdigit():
        return await m.answer("Usage: /verify TELEGRAM_UID" + BRAND)
    uid = int(parts[1])
    async with pool().acquire() as c:
        result = await c.execute("UPDATE users SET verification_status='verified' WHERE user_id=$1", uid)
    try: await bot.send_message(uid, "✅ Your account has been verified. You can now access MLT CLASSES VAULT." + BRAND)
    except Exception: pass
    await m.answer(f"Verification updated: {result}{BRAND}")

@router.message(Command("unverify"))
async def unverify(m: Message):
    if not await is_admin(m.from_user.id): return
    parts=(m.text or "").split()
    if len(parts)!=2 or not parts[1].isdigit(): return await m.answer("Usage: /unverify TELEGRAM_UID"+BRAND)
    async with pool().acquire() as c: await c.execute("UPDATE users SET verification_status='pending' WHERE user_id=$1",int(parts[1]))
    await m.answer("User returned to pending status."+BRAND)

@router.message(Command("ban"))
async def ban(m: Message):
    if not await is_admin(m.from_user.id): return
    p=(m.text or "").split()
    if len(p)!=2 or not p[1].isdigit(): return await m.answer("Usage: /ban UID"+BRAND)
    async with pool().acquire() as c: await c.execute("UPDATE users SET is_blocked=TRUE WHERE user_id=$1",int(p[1]))
    await m.answer("User blocked."+BRAND)

@router.message(Command("unban"))
async def unban(m: Message):
    if not await is_admin(m.from_user.id): return
    p=(m.text or "").split()
    if len(p)!=2 or not p[1].isdigit(): return await m.answer("Usage: /unban UID"+BRAND)
    async with pool().acquire() as c: await c.execute("UPDATE users SET is_blocked=FALSE WHERE user_id=$1",int(p[1]))
    await m.answer("User unblocked."+BRAND)

@router.message(Command("stats"))
@router.message(F.text == "📊 Dashboard")
async def stats(m: Message):
    if not await is_admin(m.from_user.id): return
    async with pool().acquire() as c:
        u=await c.fetchrow("SELECT count(*) total, count(*) FILTER(WHERE verification_status='verified') verified, count(*) FILTER(WHERE verification_status='pending') pending, count(*) FILTER(WHERE is_blocked) blocked FROM users")
        f=await c.fetchrow("SELECT count(*) total, coalesce(sum(file_size),0) bytes, coalesce(sum(download_count),0) downloads FROM files WHERE is_deleted=FALSE")
    await m.answer(f"📊 <b>MLT CLASSES VAULT DASHBOARD</b>\nUsers: {u['total']}\nVerified: {u['verified']}\nPending: {u['pending']}\nBlocked: {u['blocked']}\nFiles: {f['total']}\nStored size: {f['bytes']} bytes\nDownloads: {f['downloads']}{BRAND}")

@router.message(Command("admin"))
async def admin(m: Message):
    if not await is_admin(m.from_user.id): return
    await m.answer("<b>ADMIN COMMANDS</b>\n/stats\n/verify UID\n/unverify UID\n/ban UID\n/unban UID\n/addfile (reply to a file)\n/files\n/users" + BRAND)

@router.message(Command("addfile"))
async def addfile(m: Message):
    if not await is_admin(m.from_user.id): return
    source = m.reply_to_message
    if not source or not (source.document or source.video or source.audio):
        return await m.answer("Reply to a document, video or audio with /addfile." + BRAND)
    media = source.document or source.video or source.audio
    name = getattr(media, "file_name", None) or f"telegram_file_{media.file_unique_id}"
    try:
        stored = await bot.copy_message(settings.storage_channel_id, source.chat.id, source.message_id)
    except Exception as e:
        return await m.answer(f"Storage channel copy failed: {html.escape(str(e)[:300])}{BRAND}")
    import uuid
    public_id = "MLT-" + uuid.uuid4().hex[:8].upper()
    async with pool().acquire() as c:
        await c.execute("""INSERT INTO files(public_id,original_name,display_name,storage_channel_id,storage_message_id,telegram_file_id,file_size,mime_type,uploaded_by)
        VALUES($1,$2,$2,$3,$4,$5,$6,$7,$8)""", public_id, name, settings.storage_channel_id, stored.message_id, media.file_id, media.file_size or 0, getattr(media,"mime_type",None), m.from_user.id)
    await m.answer(f"✅ <b>MATERIAL UPLOADED</b>\nName: {html.escape(name)}\nFile ID: <code>{public_id}</code>\nSize: {media.file_size or 0} bytes\nStorage: Telegram Private Channel{BRAND}")

@router.message(Command("files"))
@router.message(F.text == "📁 All Files")
async def all_files(m: Message):
    if not await access_ok(m): return
    async with pool().acquire() as c:
        rows=await c.fetch("SELECT public_id,display_name FROM files WHERE is_deleted=FALSE ORDER BY uploaded_at DESC LIMIT 10")
    if not rows: return await m.answer("No materials found yet."+BRAND)
    kb=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=r["display_name"][:60],callback_data=f"get:{r['public_id']}")] for r in rows])
    await m.answer("📁 <b>AVAILABLE MATERIALS</b>"+BRAND,reply_markup=kb)

@router.message(Command("search"))
@router.message(F.text == "🔎 Search Files")
async def search_hint(m: Message):
    if not await access_ok(m): return
    await m.answer("🔎 Send a keyword to search materials."+BRAND)

@router.message(F.text == "📚 Browse Classes")
async def browse(m: Message):
    if not await access_ok(m): return
    async with pool().acquire() as c: rows=await c.fetch("SELECT id,name FROM categories ORDER BY name")
    if not rows: return await m.answer("No categories have been added yet."+BRAND)
    kb=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=r["name"],callback_data=f"cat:{r['id']}")] for r in rows])
    await m.answer("📚 <b>BROWSE CATEGORIES</b>"+BRAND,reply_markup=kb)

@router.message(F.text)
async def search_text(m: Message):
    if m.text.startswith("/"): return
    if not await access_ok(m): return
    q=m.text.strip()
    async with pool().acquire() as c:
        rows=await c.fetch("""SELECT public_id,display_name FROM files WHERE is_deleted=FALSE AND
        (display_name ILIKE $1 OR original_name ILIKE $1 OR coalesce(subject,'') ILIKE $1 OR coalesce(class_name,'') ILIKE $1 OR $2=ANY(aliases) OR $2=ANY(tags))
        ORDER BY uploaded_at DESC LIMIT 10""",f"%{q}%",q.lower())
    if not rows: return await m.answer("No matching files found. Try another keyword."+BRAND)
    kb=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=r["display_name"][:60],callback_data=f"get:{r['public_id']}")] for r in rows])
    await m.answer(f"📚 <b>SEARCH RESULTS</b> for: {html.escape(q)}"+BRAND,reply_markup=kb)

@router.callback_query(F.data.startswith("get:"))
async def get_file(q: CallbackQuery):
    user=await get_user(q.from_user.id)
    if not user or user["is_blocked"] or user["verification_status"]!="verified":
        await q.answer("Verification required.",show_alert=True); return
    public_id=q.data.split(":",1)[1]
    async with pool().acquire() as c:
        row=await c.fetchrow("SELECT * FROM files WHERE public_id=$1 AND is_deleted=FALSE",public_id)
    if not row: return await q.answer("File not found.",show_alert=True)
    try:
        await bot.copy_message(q.from_user.id,row["storage_channel_id"],row["storage_message_id"])
        async with pool().acquire() as c:
            await c.execute("UPDATE files SET download_count=download_count+1 WHERE id=$1",row["id"])
            await c.execute("UPDATE users SET download_count=download_count+1 WHERE user_id=$1",q.from_user.id)
            await c.execute("INSERT INTO downloads(user_id,file_id) VALUES($1,$2)",q.from_user.id,row["id"])
        await q.answer("Sent.")
    except Exception:
        logging.exception("File delivery failed")
        await q.answer("Delivery failed. Please contact an administrator.",show_alert=True)

@router.callback_query(F.data.startswith("cat:"))
async def category_files(q: CallbackQuery):
    user=await get_user(q.from_user.id)
    if not user or user["is_blocked"] or user["verification_status"]!="verified":
        await q.answer("Verification required.",show_alert=True); return
    cid=int(q.data.split(":")[1])
    async with pool().acquire() as c:
        rows=await c.fetch("SELECT public_id,display_name FROM files WHERE category_id=$1 AND is_deleted=FALSE ORDER BY uploaded_at DESC LIMIT 20",cid)
    if not rows: return await q.message.answer("No files in this category."+BRAND)
    kb=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=r["display_name"][:60],callback_data=f"get:{r['public_id']}")] for r in rows])
    await q.message.answer("📚 <b>CATEGORY MATERIALS</b>"+BRAND,reply_markup=kb)
    await q.answer()

@router.message(F.text == "📩 Contact Admin")
async def contact_hint(m: Message):
    await m.answer("Send your message to the administrators in this chat. (Contact relay setup is not enabled in this starter build.)"+BRAND)

