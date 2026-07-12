import logging
from aiogram import Router, html, F
from aiogram.filters import CommandStart
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

@router.message(CommandStart())
@router.message(F.text == "⬅️ В меню")
@router.message(F.text == "⬅️ В главное меню")
@router.message(F.text == "⬅️ Отмена")
async def start_handler(message: Message, db_session: AsyncSession) -> None:
    logger.info(f"User {message.from_user.id} (@{message.from_user.username or 'no_username'}) accessed main menu via: {message.text or '/start'}")
    user_service = UserService(db_session)
    await user_service.get_or_create_user(
        user_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name
    )

    welcome_text = (
        f"Привет, {html.bold(message.from_user.full_name)}! 👋\n\n"
        f"Я — бот-викторина {html.bold('Quizzard')}. Я могу сгенерировать для тебя "
        f"вопросы на любую тему с помощью ИИ! 🧠✨\n\n"
        f"🎮 Играй в одиночку или соревнуйся с другими в режиме {html.bold('«Рулетка категорий»')}! ⚔️\n\n"
        f"Выбери действие на клавиатуре ниже:"
    )

    await message.answer(welcome_text, reply_markup=get_main_keyboard())

@router.message(F.text == "ℹ️ О боте")
async def about_bot_handler(message: Message) -> None:
    logger.info(f"User {message.from_user.id} (@{message.from_user.username or 'no_username'}) viewed 'About Bot'")
    text = (
        f"ℹ️ {html.bold('О боте Quizzard')}\n\n"
        f"Этот бот — твой персональный генератор умных викторин! "
        f"Просто укажи интересующую тему (например, 'Программирование на Python', "
        f"'История Древнего Рима' или 'Фильмы Кристофера Нолана'), и бот сгенерирует "
        f"для тебя увлекательные вопросы с вариантами ответов.\n\n"
        f"Использует передовую языковую модель для создания вопросов и объяснений."
    )
    await message.answer(text, reply_markup=get_main_keyboard())
