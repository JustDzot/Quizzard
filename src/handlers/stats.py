from aiogram import Router, html, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession
from src.database.repositories import QuizRepository

router = Router()

async def get_stats_message(user_id: int, first_name: str, db_session: AsyncSession) -> tuple[str, InlineKeyboardMarkup]:
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
        
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎯 Начать викторину", callback_data="start_quiz")],
        [InlineKeyboardButton(text="⬅️ В меню", callback_data="back_to_menu")]
    ])
    
    return text, kb

@router.message(Command("stats"))
async def command_stats_handler(message: Message, db_session: AsyncSession) -> None:
    text, kb = await get_stats_message(message.from_user.id, message.from_user.first_name, db_session)
    await message.answer(text, reply_markup=kb)

@router.callback_query(F.data == "show_stats")
async def callback_stats_handler(callback: CallbackQuery, db_session: AsyncSession) -> None:
    text, kb = await get_stats_message(callback.from_user.id, callback.from_user.first_name, db_session)
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()
