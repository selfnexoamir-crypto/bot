from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👁 ویو", callback_data="svc:view"),
            InlineKeyboardButton(text="❤️ ری‌اکشن", callback_data="svc:reaction"),
        ],
        [
            InlineKeyboardButton(text="⭐ ممبر", callback_data="svc:member"),
            InlineKeyboardButton(text="👍 لایک", callback_data="svc:like"),
        ],
    ])

def confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ تایید", callback_data="confirm:yes"),
            InlineKeyboardButton(text="❌ لغو", callback_data="confirm:no"),
        ]
    ])

def cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ لغو", callback_data="confirm:no")]
    ])

def owner_panel() -> InlineKeyboardMarkup:
    """Overrides existing — now includes account management buttons."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 مدیریت اکانت‌ها", callback_data="account:menu")],
        [InlineKeyboardButton(text="➕ افزودن پروکسی", callback_data="proxy:add")],
        [InlineKeyboardButton(text="➖ حذف پروکسی", callback_data="proxy:remove")],
        [InlineKeyboardButton(text="📋 لیست پروکسی‌ها", callback_data="proxy:list")],
        [InlineKeyboardButton(text="🧪 تست پروکسی‌ها", callback_data="proxy:validate")],
        [InlineKeyboardButton(text="🔄 ریست پروکسی‌ها", callback_data="proxy:reset")],
        [InlineKeyboardButton(text="📊 وضعیت جاب‌ها", callback_data="admin:jobs")],
        [InlineKeyboardButton(text="🗑 پاک کردن جاب‌های قدیمی", callback_data="admin:clearjobs")],
    ])

def account_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ افزودن اکانت", callback_data="account:add")],
        [InlineKeyboardButton(text="➖ حذف اکانت", callback_data="account:remove")],
        [InlineKeyboardButton(text="📋 لیست اکانت‌ها", callback_data="account:list")],
        [InlineKeyboardButton(text="🔄 ریست اکانت‌ها", callback_data="account:reset")],
        [InlineKeyboardButton(text="🔙 بازگشت", callback_data="owner:panel")],
    ])

def back_to_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏠 منوی اصلی", callback_data="nav:menu")]
    ])
