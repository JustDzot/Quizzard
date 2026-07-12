import logging
import time
from aiogram import Router, html, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession

from src.states.quiz_states import QuizStates
from src.services.quiz_service import QuizService

logger = logging.getLogger(__name__)
router = Router()

def get_main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🎯 Начать викторину"), KeyboardButton(text="👥 Найти соперника (Дуэль)")],
        [KeyboardButton(text="👤 Мой профиль"), KeyboardButton(text="ℹ️ О боте")]
    ], resize_keyboard=True)

def get_difficulty_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[
        [
            KeyboardButton(text="🟢 Легкая"),
            KeyboardButton(text="🟡 Средняя"),
            KeyboardButton(text="🔴 Сложная")
        ],
        [KeyboardButton(text="⬅️ Отмена")]
    ], resize_keyboard=True)

def get_cancel_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="⬅️ Отмена")]
    ], resize_keyboard=True)

def get_quiz_options_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[
        [
            KeyboardButton(text="A"),
            KeyboardButton(text="B"),
            KeyboardButton(text="C"),
            KeyboardButton(text="D")
        ],
        [KeyboardButton(text="❌ Прервать викторину")]
    ], resize_keyboard=True)

def get_next_question_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="➡️ Следующий вопрос")],
        [KeyboardButton(text="❌ Прервать викторину")]
    ], resize_keyboard=True)

def get_finish_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📊 Показать результаты")],
        [KeyboardButton(text="❌ Прервать викторину")]
    ], resize_keyboard=True)

@router.message(F.text == "🎯 Начать викторину")
async def start_quiz_message_handler(message: Message, state: FSMContext) -> None:
    logger.info(f"User {message.from_user.id} (@{message.from_user.username or 'no_username'}) clicked 'Start Quiz'")
    await state.set_state(QuizStates.waiting_for_difficulty)
    await message.answer(
        "🎮 Выбери уровень сложности викторины:",
        reply_markup=get_difficulty_keyboard()
    )

@router.message(QuizStates.waiting_for_difficulty, F.text.in_({"🟢 Легкая", "🟡 Средняя", "🔴 Сложная"}))
async def difficulty_received_handler(message: Message, state: FSMContext) -> None:
    text = message.text
    logger.info(f"User {message.from_user.id} (@{message.from_user.username or 'no_username'}) selected difficulty: {text}")
    mapping = {
        "🟢 Легкая": "easy",
        "🟡 Средняя": "medium",
        "🔴 Сложная": "hard"
    }
    difficulty = mapping.get(text, "medium")
    await state.update_data(difficulty=difficulty)
    await state.set_state(QuizStates.waiting_for_topic)
    
    await message.answer(
        f"Выбранная сложность: {html.bold(text)}\n\n"
        "📝 Теперь напиши тему, по которой ты хочешь пройти викторину.\n"
        "Например: 'Язык программирования Python', 'История Древнего Рима', 'Вселенная Гарри Поттера' или 'Основы кулинарии'.",
        reply_markup=get_cancel_keyboard()
    )

@router.message(QuizStates.waiting_for_topic)
async def topic_received_handler(message: Message, state: FSMContext, db_session: AsyncSession) -> None:
    if message.text == "⬅️ Отмена":
        logger.info(f"User {message.from_user.id} (@{message.from_user.username or 'no_username'}) canceled topic prompt.")
        await state.clear()
        await message.answer("Отменено.", reply_markup=get_main_keyboard())
        return

    topic = message.text.strip()
    if len(topic) < 2:
        await message.answer("Тема слишком короткая. Напиши что-нибудь более конкретное.")
        return

    # Transition to generating state immediately to prevent user from sending more messages during generation
    await state.set_state(QuizStates.generating_quiz)

    state_data = await state.get_data()
    difficulty = state_data.get("difficulty", "medium")
    logger.info(f"User {message.from_user.id} (@{message.from_user.username or 'no_username'}) requested quiz with topic: '{topic}' (difficulty: {difficulty})")

    diff_titles = {
        "easy": "Легкая 🟢",
        "medium": "Средняя 🟡",
        "hard": "Сложная 🔴"
    }
    diff_label = diff_titles.get(difficulty, "Средняя 🟡")

    # Send status message
    status_msg = await message.answer(
        f"🤖 Генерирую викторину по теме: {html.bold(topic)} ({diff_label})...\n"
        "Использую искусственный интеллект. Это может занять некоторое время. ⏳"
    )

    last_update_time = 0.0

    async def on_chunk(accumulated_text: str):
        nonlocal last_update_time
        current_time = time.time()
        # Update no more than once per 1.5 seconds to respect Telegram rate limits
        if current_time - last_update_time >= 1.5:
            last_update_time = current_time
            
            # Extract questions using regex from partial JSON
            import re
            questions = re.findall(r'"question_text"\s*:\s*"((?:[^"\\]|\\.)*)"', accumulated_text)
            questions = [q.replace('\\"', '"').replace('\\\\', '\\') for q in questions]
            
            if questions:
                list_text = "\n".join([f"{idx+1}. {q}" for idx, q in enumerate(questions)])
                preview_text = (
                    f"🤖 Генерирую викторину по теме: {html.bold(topic)} ({diff_label})...\n\n"
                    f"🧠 {html.bold('Сгенерировано вопросов:')} {len(questions)} из 5\n"
                    f"{list_text}"
                )
            else:
                preview_text = (
                    f"🤖 Генерирую викторину по теме: {html.bold(topic)} ({diff_label})...\n\n"
                    f"⏳ {html.bold('Статус:')} Инициализация и создание вопросов..."
                )
                
            try:
                await status_msg.edit_text(preview_text)
            except Exception:
                pass

    # Initialize service and generate
    quiz_service = QuizService(db_session)
    session = await quiz_service.start_quiz_session(
        user_id=message.from_user.id,
        topic=topic,
        difficulty=difficulty,
        count=5,
        on_chunk=on_chunk
    )

    if not session:
        logger.warning(f"Failed to generate quiz for User {message.from_user.id} with topic '{topic}'")
        await message.answer(
            "❌ Не удалось сгенерировать викторину. \n"
            "Возможно, тема некорректна или возникли проблемы с API. Попробуй другую тему.",
            reply_markup=get_main_keyboard()
        )
        await state.clear()
        return

    logger.info(f"Quiz successfully generated for User {message.from_user.id} with topic '{topic}'. Session ID: {session.id}")
    await state.set_state(QuizStates.quiz_in_progress)
    await state.update_data(session_id=session.id)

    # Show first question
    await send_current_question(message, session.id, db_session)

@router.message(QuizStates.generating_quiz)
async def generating_quiz_message_handler(message: Message) -> None:
    logger.info(f"User {message.from_user.id} (@{message.from_user.username or 'no_username'}) sent message '{message.text}' while quiz generation was in progress. Ignored.")
    await message.answer("⚠️ Пожалуйста, подождите, ваша викторина ещё генерируется! ⏳")

async def send_current_question(message: Message, session_id: int, db_session: AsyncSession) -> None:
    quiz_service = QuizService(db_session)
    question = await quiz_service.get_current_question(session_id)
    session = await quiz_service.repo.get_session_by_id(session_id)

    if not question or not session:
        await message.answer("Произошла ошибка при загрузке вопроса.", reply_markup=get_main_keyboard())
        return

    # Create options text with A. B. C. D. prefixes
    prefixes = ["A", "B", "C", "D"]
    options_lines = []
    for idx, option in enumerate(question.options):
        prefix = prefixes[idx] if idx < len(prefixes) else f"{idx+1}"
        options_lines.append(f"{html.bold(prefix + '.')} {option}")
    options_text = "\n".join(options_lines)

    quiz_progress = f"Вопрос {session.current_question_index + 1} из {session.total_questions}"
    question_text = (
        f"📋 Тема: {html.code(session.topic)}\n"
        f"📊 Прогресс: {html.bold(quiz_progress)}\n\n"
        f"❓ {html.bold(question.question_text)}\n\n"
        f"{options_text}"
    )

    await message.answer(question_text, reply_markup=get_quiz_options_keyboard())

@router.message(QuizStates.quiz_in_progress, F.text.in_({"A", "B", "C", "D"}))
async def handle_answer_message(message: Message, state: FSMContext, db_session: AsyncSession) -> None:
    state_data = await state.get_data()
    session_id = state_data.get("session_id")

    if not session_id:
        await message.answer("Сессия викторины не найдена. Пожалуйста, начните заново.", reply_markup=get_main_keyboard())
        await state.clear()
        return

    mapping = {"A": 0, "B": 1, "C": 2, "D": 3}
    option_idx = mapping.get(message.text)

    quiz_service = QuizService(db_session)
    res = await quiz_service.submit_answer(session_id, option_idx)

    if not res:
        await message.answer("Этот ответ устарел или викторина уже пройдена.", reply_markup=get_main_keyboard())
        await state.clear()
        return

    is_correct, question = res
    session = await quiz_service.repo.get_session_by_id(session_id)
    
    logger.info(
        f"User {message.from_user.id} (@{message.from_user.username or 'no_username'}) answered '{message.text}' "
        f"(option index {option_idx}) in Session ID {session_id}. Correct: {is_correct}. "
        f"(Progress: {session.current_question_index}/{session.total_questions}, Score: {session.score})"
    )

    # Format options text indicating user choice and correct answer
    prefixes = ["A", "B", "C", "D"]
    options_lines = []
    for idx, option in enumerate(question.options):
        prefix_str = f"{prefixes[idx]}."
        line = f"{prefix_str} {option}"
        if idx == option_idx and idx == question.correct_option_index:
            line = f"🟢 {html.bold(line)} {html.bold('(Верно! ✅)')}"
        elif idx == option_idx:
            line = f"🔴 {html.bold(line)} {html.bold('(Твой ответ ❌)')}"
        elif idx == question.correct_option_index:
            line = f"🟢 {html.bold(line)} {html.bold('(Правильный ответ ✅)')}"
        else:
            line = f"⚪️ {line}"
        options_lines.append(line)
    options_text = "\n".join(options_lines)

    # Prepare feedback message
    feedback = ""
    if is_correct:
        feedback += f"✅ {html.bold('Верно!')}\n"
    else:
        feedback += f"❌ {html.bold('Неверно!')}\n"

    if question.explanation:
        feedback += f"\n💡 {html.bold('Объяснение:')}\n{question.explanation}"

    # Buttons for next step depending on progress
    if session.is_completed:
        markup = get_finish_keyboard()
    else:
        markup = get_next_question_keyboard()

    question_context = (
        f"📋 Тема: {html.code(session.topic)}\n"
        f"❓ {html.bold(question.question_text)}\n\n"
        f"{options_text}\n\n"
        f"{feedback}"
    )

    await message.answer(question_context, reply_markup=markup)

@router.message(QuizStates.quiz_in_progress, F.text == "➡️ Следующий вопрос")
async def handle_next_question(message: Message, state: FSMContext, db_session: AsyncSession) -> None:
    state_data = await state.get_data()
    session_id = state_data.get("session_id")

    if not session_id:
        await message.answer("Сессия викторины не найдена. Пожалуйста, начните заново.", reply_markup=get_main_keyboard())
        await state.clear()
        return

    logger.info(f"User {message.from_user.id} (@{message.from_user.username or 'no_username'}) requested next question for Session ID {session_id}")
    await send_current_question(message, session_id, db_session)

@router.message(QuizStates.quiz_in_progress, F.text == "📊 Показать результаты")
async def handle_quiz_finish(message: Message, state: FSMContext, db_session: AsyncSession) -> None:
    state_data = await state.get_data()
    session_id = state_data.get("session_id")

    if not session_id:
        await message.answer("Сессия викторины не найдена.", reply_markup=get_main_keyboard())
        await state.clear()
        return

    quiz_service = QuizService(db_session)
    session = await quiz_service.repo.get_session_by_id(session_id)

    if not session:
        await message.answer("Не удалось загрузить данные викторины.", reply_markup=get_main_keyboard())
        await state.clear()
        return

    pct = round((session.score / session.total_questions) * 100) if session.total_questions > 0 else 0
    logger.info(f"User {message.from_user.id} (@{message.from_user.username or 'no_username'}) finished quiz. Final score: {session.score}/{session.total_questions} ({pct}%) for Session ID {session_id}")
    
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
        f"Вы возвращаетесь в главное меню."
    )

    await message.answer(finish_text, reply_markup=get_main_keyboard())
    await state.clear()

@router.message(F.text == "❌ Прервать викторину")
@router.message(F.text == "⬅️ Отмена")
async def handle_quiz_cancel(message: Message, state: FSMContext, db_session: AsyncSession) -> None:
    state_data = await state.get_data()
    session_id = state_data.get("session_id")

    logger.info(f"User {message.from_user.id} (@{message.from_user.username or 'no_username'}) canceled/aborted the quiz (Session ID: {session_id})")
    if session_id:
        quiz_service = QuizService(db_session)
        session = await quiz_service.repo.get_session_by_id(session_id)
        if session and not session.is_completed:
            await quiz_service.repo.update_session(session.id, session.current_question_index, session.score, is_completed=True)

    await state.clear()
    await message.answer("Викторина прервана. Вы вернулись в главное меню. 🏠", reply_markup=get_main_keyboard())
