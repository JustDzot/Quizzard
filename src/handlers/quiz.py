import logging
from aiogram import Router, html, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from src.states.quiz_states import QuizStates
from src.services.quiz_service import QuizService

logger = logging.getLogger(__name__)
router = Router()

@router.callback_query(F.data == "start_quiz")
async def start_quiz_callback(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(QuizStates.waiting_for_topic)
    await callback.message.edit_text(
        "📝 Напиши тему, по которой ты хочешь пройти викторину.\n\n"
        "Например: 'Язык программирования Python', 'История Древнего Рима', 'Вселенная Гарри Поттера' или 'Основы кулинарии'.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Отмена", callback_data="back_to_menu")]
        ])
    )
    await callback.answer()

@router.message(QuizStates.waiting_for_topic)
async def topic_received_handler(message: Message, state: FSMContext, db_session: AsyncSession) -> None:
    topic = message.text.strip()
    if len(topic) < 2:
        await message.answer("Тема слишком короткая. Напиши что-нибудь более конкретное.")
        return

    # Send status message
    status_msg = await message.answer(
        f"🤖 Генерирую викторину по теме: {html.bold(topic)}...\n"
        "Использую искусственный интеллект. Это может занять около 5-10 секунд. ⏳"
    )

    # Initialize service and generate
    quiz_service = QuizService(db_session)
    session = await quiz_service.start_quiz_session(message.from_user.id, topic, count=5)

    if not session:
        await status_msg.edit_text(
            "❌ Не удалось сгенерировать викторину. \n"
            "Возможно, тема некорректна или возникли проблемы с API. Попробуй другую тему.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🎯 Попробовать снова", callback_data="start_quiz")],
                [InlineKeyboardButton(text="⬅️ В меню", callback_data="back_to_menu")]
            ])
        )
        await state.clear()
        return

    # Delete status message and start quiz
    await status_msg.delete()
    await state.set_state(QuizStates.quiz_in_progress)
    await state.update_data(session_id=session.id)

    # Show first question
    await send_current_question(message, session.id, db_session)

async def send_current_question(message: Message, session_id: int, db_session: AsyncSession) -> None:
    quiz_service = QuizService(db_session)
    question = await quiz_service.get_current_question(session_id)
    session = await quiz_service.repo.get_session_by_id(session_id)

    if not question or not session:
        await message.answer("Произошла ошибка при загрузке вопроса.")
        return

    # Create options keyboard
    builder = InlineKeyboardBuilder()
    for idx, option in enumerate(question.options):
        # We can add emojis to option choices: 1️⃣, 2️⃣, 3️⃣, 4️⃣
        emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣"]
        prefix = emojis[idx] if idx < len(emojis) else f"{idx+1}."
        builder.row(InlineKeyboardButton(text=f"{prefix} {option}", callback_data=f"quiz_ans:{question.id}:{idx}"))

    builder.row(InlineKeyboardButton(text="❌ Прервать викторину", callback_data="quiz_cancel"))

    quiz_progress = f"Вопрос {session.current_question_index + 1} из {session.total_questions}"
    question_text = (
        f"📋 Тема: {html.code(session.topic)}\n"
        f"📊 Прогресс: {html.bold(quiz_progress)}\n\n"
        f"❓ {html.bold(question.question_text)}"
    )

    await message.answer(question_text, reply_markup=builder.as_markup())

@router.callback_query(QuizStates.quiz_in_progress, F.data.startswith("quiz_ans:"))
async def handle_answer_callback(callback: CallbackQuery, state: FSMContext, db_session: AsyncSession) -> None:
    data_parts = callback.data.split(":")
    question_id = int(data_parts[1])
    option_idx = int(data_parts[2])

    state_data = await state.get_data()
    session_id = state_data.get("session_id")

    if not session_id:
        await callback.answer("Сессия викторины не найдена.", show_alert=True)
        return

    quiz_service = QuizService(db_session)
    res = await quiz_service.submit_answer(session_id, option_idx)

    if not res:
        await callback.answer("Этот ответ устарел или викторина уже пройдена.", show_alert=True)
        return

    is_correct, question = res
    session = await quiz_service.repo.get_session_by_id(session_id)

    # Prepare feedback message
    user_choice = question.options[option_idx]
    correct_choice = question.options[question.correct_option_index]

    if is_correct:
        feedback = f"✅ {html.bold('Верно!')}\n"
    else:
        feedback = (
            f"❌ {html.bold('Неверно!')}\n"
            f"Твой ответ: {html.italic(user_choice)}\n"
            f"Правильный ответ: {html.bold(correct_choice)}\n"
        )

    if question.explanation:
        feedback += f"\n💡 {html.bold('Объяснение:')}\n{question.explanation}"

    # Buttons for next step
    kb_builder = InlineKeyboardBuilder()
    if session.is_completed:
        kb_builder.row(InlineKeyboardButton(text="📊 Показать результаты", callback_data="quiz_finish"))
    else:
        kb_builder.row(InlineKeyboardButton(text="➡️ Следующий вопрос", callback_data="quiz_next"))

    kb_builder.row(InlineKeyboardButton(text="❌ Прервать викторину", callback_data="quiz_cancel"))

    # Edit the message to show response details
    question_context = (
        f"📋 Тема: {html.code(session.topic)}\n"
        f"❓ {html.bold(question.question_text)}\n\n"
        f"{feedback}"
    )

    await callback.message.edit_text(question_context, reply_markup=kb_builder.as_markup())
    await callback.answer()

@router.callback_query(QuizStates.quiz_in_progress, F.data == "quiz_next")
async def handle_next_question(callback: CallbackQuery, state: FSMContext, db_session: AsyncSession) -> None:
    state_data = await state.get_data()
    session_id = state_data.get("session_id")

    if not session_id:
        await callback.message.answer("Сессия викторины не найдена. Пожалуйста, начните заново.")
        await state.clear()
        return

    # Delete current message to keep chat clean and send next question
    await callback.message.delete()
    await send_current_question(callback.message, session_id, db_session)
    await callback.answer()

@router.callback_query(QuizStates.quiz_in_progress, F.data == "quiz_finish")
async def handle_quiz_finish(callback: CallbackQuery, state: FSMContext, db_session: AsyncSession) -> None:
    state_data = await state.get_data()
    session_id = state_data.get("session_id")

    if not session_id:
        await callback.message.answer("Сессия викторины не найдена.")
        await state.clear()
        return

    quiz_service = QuizService(db_session)
    session = await quiz_service.repo.get_session_by_id(session_id)

    if not session:
        await callback.message.answer("Не удалось загрузить данные викторины.")
        await state.clear()
        return

    pct = round((session.score / session.total_questions) * 100) if session.total_questions > 0 else 0
    
    emoji = "🏆"
    if pct >= 80:
        emoji = "🥇 Отличный результат!"
    elif pct >= 50:
        emoji = "🥈 Хороший результат!"
    else:
        emoji = "🥉 Нужно еще потренироваться!"

    finish_text = (
        f"🎉 Викторина по теме {html.code(session.topic)} завершена!\n\n"
        f"{html.bold(emoji)}\n"
        f"📊 Правильных ответов: {html.bold(f'{session.score} из {session.total_questions}')} ({pct}%)\n\n"
        f"Выбери следующее действие:"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎯 Новая викторина", callback_data="start_quiz")],
        [InlineKeyboardButton(text="⬅️ В главное меню", callback_data="back_to_menu")]
    ])

    await callback.message.edit_text(finish_text, reply_markup=kb)
    await state.clear()
    await callback.answer()

@router.callback_query(F.data == "quiz_cancel")
async def handle_quiz_cancel(callback: CallbackQuery, state: FSMContext, db_session: AsyncSession) -> None:
    state_data = await state.get_data()
    session_id = state_data.get("session_id")

    if session_id:
        # Mark as completed (aborted)
        quiz_service = QuizService(db_session)
        session = await quiz_service.repo.get_session_by_id(session_id)
        if session and not session.is_completed:
            await quiz_service.repo.update_session(session.id, session.current_question_index, session.score, is_completed=True)

    await state.clear()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🎯 Начать викторину", callback_data="start_quiz"),
        ],
        [
            InlineKeyboardButton(text="📊 Моя статистика", callback_data="show_stats"),
            InlineKeyboardButton(text="ℹ️ О боте", callback_data="about_bot")
        ]
    ])
    await callback.message.edit_text("Викторина прервана. Вы вернулись в главное меню. 🏠", reply_markup=kb)
    await callback.answer()
