import re
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from states import ViewFlow
from keyboards import confirm_keyboard, cancel_keyboard, main_menu, back_to_menu
from job_queue import push_job
from proxy_manager import get_active_proxies
from config import Config

router = Router()

# ── Entry: user tapped ویو button ────────────────────────────────────────────
@router.callback_query(F.data == "svc:view")
async def svc_view_entry(callback: CallbackQuery, state: FSMContext):
    await state.set_state(ViewFlow.waiting_count)
    await callback.message.edit_text(
        "👁 **ویو گرفتن**\n\n"
        "📊 تعداد ویو مورد نظر را وارد کنید:\n"
        "_(مثال: 100 یا 500)_",
        reply_markup=cancel_keyboard(),
        parse_mode="Markdown"
    )

# ── Step 1: receive count ─────────────────────────────────────────────────────
@router.message(ViewFlow.waiting_count)
async def view_got_count(message: Message, state: FSMContext):
    text = message.text.strip()
    if not text.isdigit() or int(text) < 1:
        await message.answer("⚠️ لطفاً یک عدد صحیح وارد کنید.", reply_markup=cancel_keyboard())
        return
    count = int(text)
    if count > 10000:
        await message.answer("⚠️ حداکثر ۱۰۰۰۰ ویو در هر درخواست.", reply_markup=cancel_keyboard())
        return

    await state.update_data(view_count=count)
    await state.set_state(ViewFlow.waiting_link)
    await message.answer(
        f"✅ تعداد: **{count}** ویو\n\n"
        "🔗 لینک پست را ارسال کنید:\n"
        "_(مثال: https://t.me/channel/123)_",
        reply_markup=cancel_keyboard(),
        parse_mode="Markdown"
    )

# ── Step 2: receive link ──────────────────────────────────────────────────────
@router.message(ViewFlow.waiting_link)
async def view_got_link(message: Message, state: FSMContext):
    link = message.text.strip()
    if not re.match(r"https?://t\.me/.+/\d+", link):
        await message.answer(
            "⚠️ لینک نامعتبر است.\n"
            "فرمت: `https://t.me/channel/123`",
            reply_markup=cancel_keyboard(),
            parse_mode="Markdown"
        )
        return

    data = await state.get_data()
    count = data["view_count"]
    proxies = get_active_proxies()

    await state.update_data(post_link=link)
    await state.set_state(ViewFlow.waiting_confirm)
    await message.answer(
        f"📋 **تایید عملیات:**\n\n"
        f"🔗 پست: `{link}`\n"
        f"👁 تعداد ویو: **{count}**\n"
        f"📡 پروکسی‌های فعال: **{len(proxies)}**\n\n"
        f"تایید می‌کنید؟",
        reply_markup=confirm_keyboard(),
        parse_mode="Markdown"
    )

# ── Step 3: confirm ───────────────────────────────────────────────────────────
@router.callback_query(ViewFlow.waiting_confirm, F.data == "confirm:yes")
async def view_confirmed(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await state.clear()

    proxies = get_active_proxies()
    if not proxies:
        await callback.message.edit_text(
            "❌ هیچ پروکسی فعالی وجود ندارد.\n"
            "مالک ربات باید پروکسی اضافه کند.",
            reply_markup=back_to_menu()
        )
        return

    # ارسال progress message — worker این پیام رو edit می‌کنه
    progress_msg = await callback.message.edit_text(
        f"⏳ **جاب در صف قرار گرفت...**\n\n"
        f"🔗 `{data['post_link']}`\n"
        f"👁 هدف: {data['view_count']} ویو\n\n"
        f"Worker شروع می‌کند...",
        parse_mode="Markdown"
    )

    await push_job(
        job_type="view",
        user_id=callback.from_user.id,
        chat_id=callback.message.chat.id,
        message_id=progress_msg.message_id,
        post_link=data["post_link"],
        count=data["view_count"],
    )

# ── Cancel from any view state ────────────────────────────────────────────────
@router.callback_query(ViewFlow.waiting_confirm, F.data == "confirm:no")
@router.callback_query(F.data == "confirm:no")
async def view_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "❌ لغو شد.\n\nیک سرویس را انتخاب کنید:",
        reply_markup=main_menu()
    )
