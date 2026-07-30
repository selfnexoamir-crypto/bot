from aiogram import Router
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from config import Config
from keyboards import main_menu, owner_panel

router = Router()

@router.message(CommandStart())
async def cmd_start(message: Message):
    uid = message.from_user.id
    name = message.from_user.first_name or "کاربر"

    await message.answer(
        f"👋 سلام {name}!\n\n"
        f"یک سرویس را انتخاب کنید:",
        reply_markup=main_menu()
    )

    if uid == Config.OWNER_ID:
        await message.answer(
            "👑 **پنل مدیریت مالک:**",
            reply_markup=owner_panel(),
            parse_mode="Markdown"
        )

@router.message(Command("panel"))
async def cmd_panel(message: Message):
    if message.from_user.id != Config.OWNER_ID:
        await message.answer("⛔ دسترسی ندارید.")
        return
    await message.answer("👑 **پنل مدیریت:**", reply_markup=owner_panel(), parse_mode="Markdown")

@router.message(Command("menu"))
async def cmd_menu(message: Message):
    await message.answer("یک سرویس را انتخاب کنید:", reply_markup=main_menu())
