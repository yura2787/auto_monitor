from aiogram.fsm.state import State, StatesGroup


class AddFilterFSM(StatesGroup):
    brand = State()
    model = State()
    year_from = State()
    year_to = State()
    price_from = State()
    price_to = State()
    mileage_from = State()
    mileage_to = State()
    condition = State()
    confirm = State()
