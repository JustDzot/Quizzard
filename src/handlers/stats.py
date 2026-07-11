from aiogram import Router, html, F
from aiogram.filters import Command
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession
from src.database.repositories import QuizRepository

router = Router()

def get_main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🎯 Начать викторину")],
        [KeyboardButton(text="📊 Моя статистика"), KeyboardButton(text="ℹ️ О боте")]
    ], resize_keyboard=True)

async def get_stats_message(user_id: int, first_name: str, db_session: AsyncSession) -> str:
    repo = QuizRepository(db_session)
    stats = await repo.get_user_stats(user_id)
    
    if stats["total_quizzes"] == 0:
        text = (
            f"📊 {html.bold('Статистика пользователя')} {html.bold(first_name)}:\n\n"
            f"Вы еще не прошли ни одной викторины до конца. Пора это исправить! 😉"
        )
    else:
        correct_rate = stats['correct_rate']
        text = (
            f"📊 {html.bold('Статистика пользователя')} {html.bold(first_name)}:\n\n"
            f"🏆 Завершено викторин: {html.bold(stats['total_quizzes'])}\n"
            f"✅ Всего правильных ответов: {html.bold(stats['total_score'])} / {stats['total_questions']}\n"
            f"🎯 Процент правильных ответов: {html.bold(f'{correct_rate}%')}"
        )
    return text

@router.message(Command("stats"))
@router.message(F.text == "📊 Моя статистика")
async def stats_handler(message: Message, db_session: AsyncSession) -> None:
    text = await get_stats_message(message.from_user.id, message.from_user.first_name, db_session)
    await message.answer(text, reply_markup=get_main_keyboard())
