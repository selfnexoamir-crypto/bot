from aiogram.fsm.state import State, StatesGroup

class ViewFlow(StatesGroup):
    waiting_count = State()
    waiting_link  = State()
    waiting_confirm = State()

class ReactionFlow(StatesGroup):
    waiting_link    = State()
    waiting_confirm = State()

class ProxyFlow(StatesGroup):
    waiting_add    = State()
    waiting_remove = State()

class AccountFlow(StatesGroup):
    waiting_phone   = State()   # مالک شماره میده
    waiting_code    = State()   # کد OTP
    waiting_2fa     = State()   # پسورد دو مرحله‌ای (اختیاری)
    waiting_remove  = State()   # حذف اکانت
