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
