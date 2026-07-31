"""
Account management handler.
مالک می‌تونه چند اکانت تلگرام رو از داخل ربات login کنه.
هر اکانت یه session string ذخیره میشه و worker از pool استفاده می‌کنه.
"""
import asyncio
import logging

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import (
    SessionPasswordNeededError,
    PhoneCodeInvalidError,
    PhoneCodeExpiredError,
    PasswordHashInvalidError,
    FloodWaitError,
)

from config import Config
from states import AccountFlow
from keyboards import owner_panel, account_menu_keyboard, cancel_keyboard
from session_manager import (
    add_session, remove_session, list_sessions, reset_sessions,
)

router = Router()
logger = logging.getLogger(__name__)

# هر مرحله login یه client موقت نیاز داره — اینجا نگه‌اش می‌داریم
_pending_clients: dict[int, TelegramClient] = {}  # owner_id → client


def _is_owner(uid: int) -> bool:
    return uid == Config.OWNER_ID


# ── Account menu ──────────────────────────────────────────────────────────────

@router.callback_query(F.data == "account:menu")
async def account_menu(callback: CallbackQuery):
    if not _is_owner(callback.from_user.id):
        await callback.answer("⛔", show_alert=True)
        return
    sessions = list_sessions()
    count = len(sessions)
    active = sum(1 for s in sessions if s["active"])
    await callback.message.edit_text(
        f"👤 **مدیریت اکانت‌ها**\n\n"
        f"کل: {count} | فعال: {active}",
        reply_markup=account_menu_keyboard(),
        parse_mode="Markdown",
    )


@router.callback_query(F.data == "owner:panel")
async def back_to_owner(callback: CallbackQuery):
    if not _is_owner(callback.from_user.id):
        await callback.answer("⛔", show_alert=True)
        return
    await callback.message.edit_text("⚙️ پنل مدیریت:", reply_markup=owner_panel())


# ── Add account: step 1 — phone ──────────────────────────────────────────────

@router.callback_query(F.data == "account:add")
async def account_add_start(callback: CallbackQuery, state: FSMContext):
    if not _is_owner(callback.from_user.id):
        await callback.answer("⛔", show_alert=True)
        return
    await state.set_state(AccountFlow.waiting_phone)
    await callback.message.edit_text(
        "📱 **افزودن اکانت**\n\n"
        "شماره تلفن رو وارد کن:\n"
        "`+989123456789`",
        reply_markup=cancel_keyboard(),
        parse_mode="Markdown",
    )


@router.message(AccountFlow.waiting_phone)
async def account_add_phone(message: Message, state: FSMContext):
    if not _is_owner(message.from_user.id):
        return

    phone = message.text.strip()
    if not phone.startswith("+") or not phone[1:].isdigit():
        await message.answer(
            "❌ فرمت اشتباه. با + شروع کن:\n`+989123456789`",
            reply_markup=cancel_keyboard(),
            parse_mode="Markdown",
        )
        return

    uid = message.from_user.id
    # cleanup قبلی اگه هست
    if uid in _pending_clients:
        try:
            await _pending_clients[uid].disconnect()
        except Exception:
            pass

    client = TelegramClient(
        StringSession(),
        Config.API_ID,
        Config.API_HASH,
        connection_retries=2,
        receive_updates=False,
    )

    status_msg = await message.answer("⏳ در حال اتصال...")

    try:
        await client.connect()
        result = await client.send_code_request(phone)
        _pending_clients[uid] = client
        await state.update_data(phone=phone, phone_code_hash=result.phone_code_hash)
        await state.set_state(AccountFlow.waiting_code)
        await status_msg.edit_text(
            f"✅ کد به `{phone}` ارسال شد.\n\n"
            "کد ۵ رقمی رو وارد کن:\n"
            "`12345`",
            reply_markup=cancel_keyboard(),
            parse_mode="Markdown",
        )
    except FloodWaitError as e:
        await client.disconnect()
        await status_msg.edit_text(
            f"⏱ FloodWait: {e.seconds} ثانیه صبر کن.",
            reply_markup=account_menu_keyboard(),
        )
        await state.clear()
    except Exception as e:
        await client.disconnect()
        await status_msg.edit_text(
            f"❌ خطا: {type(e).__name__}: {e}",
            reply_markup=account_menu_keyboard(),
        )
        await state.clear()


# ── Add account: step 2 — OTP code ──────────────────────────────────────────

@router.message(AccountFlow.waiting_code)
async def account_add_code(message: Message, state: FSMContext):
    if not _is_owner(message.from_user.id):
        return

    uid = message.from_user.id
    code = message.text.strip().replace(" ", "").replace("-", "")
    data = await state.get_data()
    phone = data["phone"]
    phone_code_hash = data["phone_code_hash"]
    client = _pending_clients.get(uid)

    if client is None:
        await message.answer("❌ session منقضی شد. دوباره شروع کن.", reply_markup=account_menu_keyboard())
        await state.clear()
        return

    try:
        me = await client.sign_in(phone=phone, code=code, phone_code_hash=phone_code_hash)
        session_str = client.session.save()
        name = getattr(me, "first_name", "") or phone
        is_new = add_session(phone, session_str, name)
        await client.disconnect()
        _pending_clients.pop(uid, None)
        await state.clear()
        verb = "اضافه شد" if is_new else "آپدیت شد"
        await message.answer(
            f"✅ اکانت **{name}** (`{phone}`) {verb}.",
            reply_markup=account_menu_keyboard(),
            parse_mode="Markdown",
        )

    except SessionPasswordNeededError:
        await state.set_state(AccountFlow.waiting_2fa)
        await message.answer(
            "🔐 این اکانت تایید دو مرحله‌ای داره.\nپسورد رو وارد کن:",
            reply_markup=cancel_keyboard(),
        )

    except (PhoneCodeInvalidError, PhoneCodeExpiredError) as e:
        await message.answer(
            f"❌ کد اشتباه یا منقضی: {type(e).__name__}\nدوباره وارد کن:",
            reply_markup=cancel_keyboard(),
        )

    except Exception as e:
        try:
            await client.disconnect()
        except Exception:
            pass
        _pending_clients.pop(uid, None)
        await state.clear()
        await message.answer(
            f"❌ خطا: {type(e).__name__}: {e}",
            reply_markup=account_menu_keyboard(),
        )


# ── Add account: step 3 — 2FA password ──────────────────────────────────────

@router.message(AccountFlow.waiting_2fa)
async def account_add_2fa(message: Message, state: FSMContext):
    if not _is_owner(message.from_user.id):
        return

    uid = message.from_user.id
    password = message.text.strip()
    data = await state.get_data()
    phone = data["phone"]
    client = _pending_clients.get(uid)

    if client is None:
        await message.answer("❌ session منقضی شد. دوباره شروع کن.", reply_markup=account_menu_keyboard())
        await state.clear()
        return

    try:
        me = await client.sign_in(password=password)
        session_str = client.session.save()
        name = getattr(me, "first_name", "") or phone
        is_new = add_session(phone, session_str, name)
        await client.disconnect()
        _pending_clients.pop(uid, None)
        await state.clear()
        verb = "اضافه شد" if is_new else "آپدیت شد"
        await message.answer(
            f"✅ اکانت **{name}** (`{phone}`) {verb}.",
            reply_markup=account_menu_keyboard(),
            parse_mode="Markdown",
        )

    except PasswordHashInvalidError:
        await message.answer(
            "❌ پسورد اشتباهه. دوباره وارد کن:",
            reply_markup=cancel_keyboard(),
        )

    except Exception as e:
        try:
            await client.disconnect()
        except Exception:
            pass
        _pending_clients.pop(uid, None)
        await state.clear()
        await message.answer(
            f"❌ خطا: {type(e).__name__}: {e}",
            reply_markup=account_menu_keyboard(),
        )


# ── Remove account ────────────────────────────────────────────────────────────

@router.callback_query(F.data == "account:remove")
async def account_remove_start(callback: CallbackQuery, state: FSMContext):
    if not _is_owner(callback.from_user.id):
        await callback.answer("⛔", show_alert=True)
        return
    sessions = list_sessions()
    if not sessions:
        await callback.answer("هیچ اکانتی ثبت نشده.", show_alert=True)
        return
    lines = []
    for i, s in enumerate(sessions, 1):
        flag = "✅" if s["active"] else "❌"
        lines.append(f"{i}. {flag} {s['name']} | `{s['phone']}`")
    await state.set_state(AccountFlow.waiting_remove)
    await callback.message.edit_text(
        "➖ **حذف اکانت**\n\n"
        + "\n".join(lines)
        + "\n\nشماره تلفن اکانت رو وارد کن:",
        reply_markup=cancel_keyboard(),
        parse_mode="Markdown",
    )


@router.message(AccountFlow.waiting_remove)
async def account_remove_receive(message: Message, state: FSMContext):
    if not _is_owner(message.from_user.id):
        return
    phone = message.text.strip()
    removed = remove_session(phone)
    await state.clear()
    if removed:
        await message.answer(f"✅ اکانت `{phone}` حذف شد.", reply_markup=account_menu_keyboard(), parse_mode="Markdown")
    else:
        await message.answer(f"❌ اکانت `{phone}` پیدا نشد.", reply_markup=account_menu_keyboard(), parse_mode="Markdown")


# ── List accounts ─────────────────────────────────────────────────────────────

@router.callback_query(F.data == "account:list")
async def account_list(callback: CallbackQuery):
    if not _is_owner(callback.from_user.id):
        await callback.answer("⛔", show_alert=True)
        return
    sessions = list_sessions()
    if not sessions:
        await callback.message.edit_text(
            "📋 هیچ اکانتی ثبت نشده.\n\n"
            "⚠️ اگه `TELEGRAM_SESSION_STRING` توی env vars داری، از اون استفاده میشه.",
            reply_markup=account_menu_keyboard(),
        )
        return
    lines = []
    for s in sessions:
        flag = "✅" if s["active"] else f"❌ ({s['fail_count']} خطا)"
        lines.append(f"{flag} **{s['name']}** | `{s['phone']}`")
    await callback.message.edit_text(
        "📋 **اکانت‌ها:**\n\n" + "\n".join(lines),
        reply_markup=account_menu_keyboard(),
        parse_mode="Markdown",
    )


# ── Reset accounts ────────────────────────────────────────────────────────────

@router.callback_query(F.data == "account:reset")
async def account_reset(callback: CallbackQuery):
    if not _is_owner(callback.from_user.id):
        await callback.answer("⛔", show_alert=True)
        return
    reset_sessions()
    await callback.message.edit_text("🔄 همه اکانت‌ها ریست شدند.", reply_markup=account_menu_keyboard())
