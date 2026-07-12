import logging
from aiogram import Router, html, F
from aiogram.filters import Command
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession
from src.services.user_service import UserService

logger = logging.getLogger(__name__)
router = Router()

def get_main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🎯 Начать викторину"), KeyboardButton(text="👥 Найти соперника (Дуэль)")],
        [KeyboardButton(text="👤 Мой профиль"), KeyboardButton(text="ℹ️ О боте")]
    ], resize_keyboard=True)

async def get_profile_message(user_id: int, first_name: str, db_session: AsyncSession) -> str:
    user_service = UserService(db_session)
    profile = await user_service.get_user_profile(user_id, first_name)
    
    user = profile["user"]
    level_info = profile["level_info"]
    sp_stats = profile["sp_stats"]
    total_duels = profile["total_duels"]
    winrate = profile["winrate"]
    
    # Format single player stats
    if sp_stats["total_quizzes"] == 0:
        sp_text = "Нет сыгранных игр 🤷‍♂️"
    else:
        correct_rate = sp_stats["correct_rate"]
        sp_text = (
            f"Завершено викторин: {html.bold(sp_stats['total_quizzes'])}\n"
            f"• Точность: {html.bold(f'{correct_rate}%')} ({sp_stats['total_score']} / {sp_stats['total_questions']})"
        )
    
    # Format multiplayer stats
    if total_duels == 0:
        mp_text = "Нет сыгранных дуэлей ⚔️"
    else:
        mp_text = (
            f"Сыграно: {html.bold(total_duels)}\n"
            f"• Победы: {html.bold(user.wins)} | Поражения: {html.bold(user.losses)} | Ничьи: {html.bold(user.draws)}\n"
            f"• Процент побед: {html.bold(f'{winrate}%')}"
        )

    text = (
        f"👤 {html.bold('Профиль игрока')} {html.bold(first_name)}\n"
        f"🎖 Уровень: {html.bold(level_info['level'])} [{html.code(level_info['title'])}]\n"
        f"✨ Опыт: {html.bold(user.xp)} / {level_info['xp_next_level']} XP\n"
        f"<code>[{level_info['bar']}]</code> {level_info['progress_pct']}%\n\n"
        f"🎯 {html.bold('Одиночные игры:')}\n"
        f"• {sp_text}\n\n"
        f"⚔️ {html.bold('Статистика дуэлей:')}\n"
        f"• {mp_text}"
    )
    return text

@router.message(Command("profile"))
@router.message(Command("stats"))
@router.message(F.text == "👤 Мой профиль")
@router.message(F.text == "📊 Моя статистика")
async def profile_handler(message: Message, db_session: AsyncSession) -> None:
    logger.info(f"User {message.from_user.id} (@{message.from_user.username or 'no_username'}) requested profile")
    text = await get_profile_message(message.from_user.id, message.from_user.first_name, db_session)
    await message.answer(text, reply_markup=get_main_keyboard())
