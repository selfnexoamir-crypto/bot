import asyncio
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command

from config import Config
from states import ProxyFlow
from keyboards import owner_panel, cancel_keyboard, back_to_menu
from proxy_manager import (
    add_proxy, add_proxy_from_link, is_mtproto_link,
    remove_proxy, list_proxies,
    get_active_proxies, reset_all, validate_proxy,
)
from job_queue import get_all_jobs, clear_done_jobs

router = Router()

def _is_owner(uid: int) -> bool:
    return uid == Config.OWNER_ID

# ── Proxy: Add ────────────────────────────────────────────────────────────────
@router.callback_query(F.data == "proxy:add")
async def proxy_add_entry(callback: CallbackQuery, state: FSMContext):
    if not _is_owner(callback.from_user.id):
        await callback.answer("⛔ دسترسی ندارید.", show_alert=True)
        return
    await state.set_state(ProxyFlow.waiting_add)
    await callback.message.edit_text(
        "➕ **افزودن پروکسی**\n\n"
        "**روش ۱ — لینک MTProto:**\n"
        "`https://t.me/proxy?server=...&port=...&secret=...`\n\n"
        "**روش ۲ — دستی:**\n"
        "`host port type [username password]`\n\n"
        "مثال‌ها:\n"
        "`1.2.3.4 1080 socks5`\n"
        "`1.2.3.4 1080 socks5 user pass`\n"
        "`1.2.3.4 8080 http`",
        reply_markup=cancel_keyboard(),
        parse_mode="Markdown"
    )

@router.message(ProxyFlow.waiting_add)
async def proxy_add_receive(message: Message, state: FSMContext):
    if not _is_owner(message.from_user.id):
        return

    text = message.text.strip()

    # ── MTProto link path ─────────────────────────────────────────────────────
    if is_mtproto_link(text):
        result = add_proxy_from_link(text)
        await state.clear()
        if result is None:
            await message.answer(
                "❌ لینک MTProto نامعتبر است.\n"
                "فرمت صحیح:\n`https://t.me/proxy?server=...&port=...&secret=...`",
                reply_markup=cancel_keyboard(), parse_mode="Markdown"
            )
            return
        if result is False:
            await message.answer(
                f"⚠️ این پروکسی قبلاً ثبت شده.",
                reply_markup=owner_panel(), parse_mode="Markdown"
            )
            return
        await message.answer(
            f"✅ پروکسی MTProto اضافه شد:\n"
            f"`{result['host']}:{result['port']}` (mtproto)",
            reply_markup=owner_panel(), parse_mode="Markdown"
        )
        return

    # ── Manual SOCKS/HTTP path ────────────────────────────────────────────────
    parts = text.split()
    if len(parts) < 3:
        await message.answer("⚠️ فرمت: `host port type`", reply_markup=cancel_keyboard(), parse_mode="Markdown")
        return
    host, port_str, ptype = parts[0], parts[1], parts[2].lower()
    if not port_str.isdigit():
        await message.answer("⚠️ پورت باید عدد باشد.", reply_markup=cancel_keyboard())
        return
    if ptype not in ("socks5", "socks4", "http"):
        await message.answer("⚠️ نوع: socks5 / socks4 / http", reply_markup=cancel_keyboard())
        return
    username = parts[3] if len(parts) > 3 else None
    password = parts[4] if len(parts) > 4 else None

    added = add_proxy(host, int(port_str), ptype, username, password)
    await state.clear()
    if added:
        await message.answer(
            f"✅ پروکسی اضافه شد:\n`{host}:{port_str}` ({ptype})",
            reply_markup=owner_panel(), parse_mode="Markdown"
        )
    else:
        await message.answer(
            f"⚠️ پروکسی `{host}:{port_str}` قبلاً ثبت شده.",
            reply_markup=owner_panel(), parse_mode="Markdown"
        )

# ── Proxy: Remove ─────────────────────────────────────────────────────────────
@router.callback_query(F.data == "proxy:remove")
async def proxy_remove_entry(callback: CallbackQuery, state: FSMContext):
    if not _is_owner(callback.from_user.id):
        await callback.answer("⛔ دسترسی ندارید.", show_alert=True)
        return
    proxies = list_proxies()
    if not proxies:
        await callback.answer("هیچ پروکسی‌ای ثبت نشده.", show_alert=True)
        return
    await state.set_state(ProxyFlow.waiting_remove)
    lines = []
    for i, p in enumerate(proxies, 1):
        s = "✅" if p["active"] else "❌"
        lines.append(f"{i}. {s} `{p['host']}:{p['port']}` ({p['type']})")
    await callback.message.edit_text(
        "➖ **حذف پروکسی**\n\n"
        + "\n".join(lines)
        + "\n\nآدرس پروکسی را وارد کنید:\n`host port`",
        reply_markup=cancel_keyboard(),
        parse_mode="Markdown"
    )

@router.message(ProxyFlow.waiting_remove)
async def proxy_remove_receive(message: Message, state: FSMContext):
    if not _is_owner(message.from_user.id):
        return
    parts = message.text.strip().split()
    if len(parts) < 2 or not parts[1].isdigit():
        await message.answer("⚠️ فرمت: `host port`", reply_markup=cancel_keyboard(), parse_mode="Markdown")
        return
    host, port = parts[0], int(parts[1])
    removed = remove_proxy(host, port)
    await state.clear()
    if removed:
        await message.answer(f"✅ حذف شد: `{host}:{port}`", reply_markup=owner_panel(), parse_mode="Markdown")
    else:
        await message.answer(f"❌ پیدا نشد: `{host}:{port}`", reply_markup=owner_panel(), parse_mode="Markdown")

# ── Proxy: List ───────────────────────────────────────────────────────────────
@router.callback_query(F.data == "proxy:list")
async def proxy_list(callback: CallbackQuery):
    if not _is_owner(callback.from_user.id):
        await callback.answer("⛔", show_alert=True)
        return
    proxies = list_proxies()
    if not proxies:
        await callback.message.edit_text("📋 هیچ پروکسی‌ای ثبت نشده.", reply_markup=owner_panel())
        return
    lines = []
    for p in proxies:
        s = "✅" if p["active"] else f"❌ ({p['fail_count']} خطا)"
        auth = f" | {p['username']}" if p.get("username") else ""
        lines.append(f"{s} `{p['host']}:{p['port']}` {p['type']}{auth}")
    await callback.message.edit_text(
        "📋 **لیست پروکسی‌ها:**\n\n" + "\n".join(lines),
        reply_markup=owner_panel(), parse_mode="Markdown"
    )

# ── Proxy: Validate ───────────────────────────────────────────────────────────
@router.callback_query(F.data == "proxy:validate")
async def proxy_validate(callback: CallbackQuery):
    if not _is_owner(callback.from_user.id):
        await callback.answer("⛔", show_alert=True)
        return
    proxies = list_proxies()
    if not proxies:
        await callback.message.edit_text("هیچ پروکسی‌ای ثبت نشده.", reply_markup=owner_panel())
        return
    await callback.message.edit_text(f"🧪 در حال تست {len(proxies)} پروکسی...")
    results = await asyncio.gather(*[validate_proxy(p, Config.PROXY_TIMEOUT) for p in proxies])
    passed = sum(results)
    await callback.message.edit_text(
        f"🧪 **نتیجه تست:**\nموفق: {passed}/{len(proxies)}",
        reply_markup=owner_panel(), parse_mode="Markdown"
    )

# ── Proxy: Reset ──────────────────────────────────────────────────────────────
@router.callback_query(F.data == "proxy:reset")
async def proxy_reset(callback: CallbackQuery):
    if not _is_owner(callback.from_user.id):
        await callback.answer("⛔", show_alert=True)
        return
    reset_all()
    await callback.message.edit_text("🔄 همه پروکسی‌ها ریست شدند.", reply_markup=owner_panel())

# ── Admin: Job status ─────────────────────────────────────────────────────────
@router.callback_query(F.data == "admin:jobs")
async def admin_jobs(callback: CallbackQuery):
    if not _is_owner(callback.from_user.id):
        await callback.answer("⛔", show_alert=True)
        return
    jobs = get_all_jobs()
    if not jobs:
        await callback.message.edit_text("📊 هیچ جابی وجود ندارد.", reply_markup=owner_panel())
        return
    lines = []
    status_emoji = {"pending": "⏳", "running": "⚙️", "done": "✅", "failed": "❌"}
    for j in jobs[-10:]:  # آخرین ۱۰ جاب
        emoji = status_emoji.get(j["status"], "❓")
        lines.append(
            f"{emoji} `{j['id']}` | {j['type']} | {j['count']} | ~{j['views_done']} ویو"
        )
    await callback.message.edit_text(
        "📊 **آخرین جاب‌ها:**\n\n" + "\n".join(lines),
        reply_markup=owner_panel(), parse_mode="Markdown"
    )

# ── Admin: Clear done jobs ────────────────────────────────────────────────────
@router.callback_query(F.data == "admin:clearjobs")
async def admin_clearjobs(callback: CallbackQuery):
    if not _is_owner(callback.from_user.id):
        await callback.answer("⛔", show_alert=True)
        return
    removed = clear_done_jobs()
    await callback.message.edit_text(
        f"🗑 {removed} جاب تمام‌شده پاک شد.",
        reply_markup=owner_panel()
    )
