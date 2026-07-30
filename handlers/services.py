"""
سرویس‌های ری‌اکشن، ممبر، لایک — placeholder.
معماری همانند view.py است — برای هر سرویس FSMContext جداگانه اضافه کنید.
"""
from aiogram import Router, F
from aiogram.types import CallbackQuery
from keyboards import back_to_menu

router = Router()

NOT_AVAILABLE = (
    "⚠️ این سرویس در حال توسعه است و به زودی اضافه می‌شود."
)

@router.callback_query(F.data == "svc:reaction")
async def svc_reaction(callback: CallbackQuery):
    await callback.message.edit_text(NOT_AVAILABLE, reply_markup=back_to_menu())

@router.callback_query(F.data == "svc:member")
async def svc_member(callback: CallbackQuery):
    await callback.message.edit_text(NOT_AVAILABLE, reply_markup=back_to_menu())

@router.callback_query(F.data == "svc:like")
async def svc_like(callback: CallbackQuery):
    await callback.message.edit_text(NOT_AVAILABLE, reply_markup=back_to_menu())

@router.callback_query(F.data == "nav:menu")
async def nav_menu(callback: CallbackQuery):
    from keyboards import main_menu
    await callback.message.edit_text(
        "یک سرویس را انتخاب کنید:",
        reply_markup=main_menu()
    )
