from aiogram import Router, html, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession
from src.services.user_service import UserService

router = Router()

@router.message(CommandStart())
async def command_start_handler(message: Message, db_session: AsyncSession) -> None:
    user_service = UserService(db_session)
    await user_service.get_or_create_user(
        user_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🎯 Начать викторину", callback_data="start_quiz"),
        ],
        [
            InlineKeyboardButton(text="📊 Моя статистика", callback_data="show_stats"),
            InlineKeyboardButton(text="ℹ️ О боте", callback_data="about_bot")
        ]
    ])

    welcome_text = (
        f"Привет, {html.bold(message.from_user.full_name)}! 👋\n\n"
        f"Я — бот-викторина {html.bold('Quizzard')}. Я могу сгенерировать для тебя "
        f"вопросы на совершенно любую тему с помощью искусственного интеллекта! 🧠✨\n\n"
        f"Выбери действие ниже, чтобы начать:"
    )

    await message.answer(welcome_text, reply_markup=kb)

@router.callback_query(F.data == "about_bot")
async def callback_about_bot_handler(callback: CallbackQuery) -> None:
    text = (
        f"ℹ️ {html.bold('О боте Quizzard')}\n\n"
        f"Этот бот — твой персональный генератор умных викторин! "
        f"Просто укажи интересующую тему (например, 'Программирование на Python', "
        f"'История Древнего Рима' или 'Фильмы Кристофера Нолана'), и бот сгенерирует "
        f"для тебя увлекательные вопросы с вариантами ответов.\n\n"
        f"Использует передовую языковую модель для создания вопросов и объяснений."
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ В меню", callback_data="back_to_menu")]
    ])
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()

@router.callback_query(F.data == "back_to_menu")
async def callback_back_to_menu_handler(callback: CallbackQuery) -> None:
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🎯 Начать викторину", callback_data="start_quiz"),
        ],
        [
            InlineKeyboardButton(text="📊 Моя статистика", callback_data="show_stats"),
            InlineKeyboardButton(text="ℹ️ О боте", callback_data="about_bot")
        ]
    ])
    welcome_text = (
        f"Привет, {html.bold(callback.from_user.full_name)}! 👋\n\n"
        f"Я — бот-викторина {html.bold('Quizzard')}. Я могу сгенерировать для тебя "
        f"вопросы на совершенно любую тему с помощью искусственного интеллекта! 🧠✨\n\n"
        f"Выбери действие ниже, чтобы начать:"
    )
    await callback.message.edit_text(welcome_text, reply_markup=kb)
    await callback.answer()
