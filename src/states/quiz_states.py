from aiogram.fsm.state import State, StatesGroup

class QuizStates(StatesGroup):
    waiting_for_difficulty = State()
    waiting_for_topic = State()
    generating_quiz = State()
    quiz_in_progress = State()

class MultiplayerStates(StatesGroup):
    searching = State()
    voting = State()
    waiting_for_generation = State()
    game_in_progress = State()
