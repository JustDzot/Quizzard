from aiogram.fsm.state import State, StatesGroup

class QuizStates(StatesGroup):
    waiting_for_topic = State()
    quiz_in_progress = State()
