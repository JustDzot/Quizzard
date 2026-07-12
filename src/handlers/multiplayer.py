import asyncio
import logging
from datetime import datetime
from aiogram import Router, html, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession

from src.states.quiz_states import MultiplayerStates
from src.services.multiplayer_service import MultiplayerService

logger = logging.getLogger(__name__)
router = Router()

def get_main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🎯 Начать викторину"), KeyboardButton(text="👥 Найти соперника (Дуэль)")],
        [KeyboardButton(text="👤 Мой профиль"), KeyboardButton(text="ℹ️ О боте")]
    ], resize_keyboard=True)

def get_search_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="❌ Отменить поиск")]
    ], resize_keyboard=True)

def get_duel_options_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[
        [
            KeyboardButton(text="A"),
            KeyboardButton(text="B"),
            KeyboardButton(text="C"),
            KeyboardButton(text="D")
        ],
        [KeyboardButton(text="❌ Сдаться")]
    ], resize_keyboard=True)

def get_next_duel_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="➡️ Следующий вопрос")],
        [KeyboardButton(text="❌ Сдаться")]
    ], resize_keyboard=True)

def get_voting_keyboard(categories: list[str]) -> InlineKeyboardMarkup:
    buttons = []
    for idx, cat in enumerate(categories):
        buttons.append([InlineKeyboardButton(text=f"{idx+1}️⃣ {cat}", callback_data=f"duel_vote:{idx}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

@router.message(F.text == "👥 Найти соперника (Дуэль)")
async def start_matchmaking_handler(message: Message, state: FSMContext, db_session: AsyncSession, bot: Bot) -> None:
    user_id = message.from_user.id
    logger.info(f"User {user_id} (@{message.from_user.username or 'no_username'}) entered matchmaking queue")
    
    # Check if user already has an active multiplayer game
    service = MultiplayerService(db_session)
    active_game = await service.repo.get_active_multiplayer_game(user_id)
    if active_game:
        # Resume or abort active game
        await state.set_state(MultiplayerStates.game_in_progress)
        await state.update_data(game_id=active_game.id)
        await message.answer("⚠️ У вас есть незаконченная дуэль! Продолжаем игру.", reply_markup=get_duel_options_keyboard())
        await send_current_duel_question(bot, user_id, active_game.id, db_session)
        return
        
    await state.set_state(MultiplayerStates.searching)
    await message.answer(
        "🔍 Ищу соперника для дуэли...\n"
        "Когда оппонент найдётся, начнётся «Рулетка категорий»! 🎰",
        reply_markup=get_search_keyboard()
    )
    
    game, opponent_id = await service.join_queue(user_id)
    if game and opponent_id:
        # Opponent was waiting, current user joined. Match made!
        opponent_key = StorageKey(bot_id=bot.id, chat_id=opponent_id, user_id=opponent_id)
        opponent_state = FSMContext(storage=state.storage, key=opponent_key)
        
        # Transition both to voting state
        await state.set_state(MultiplayerStates.voting)
        await state.update_data(game_id=game.id)
        
        await opponent_state.set_state(MultiplayerStates.voting)
        await opponent_state.update_data(game_id=game.id)
        
        # Get opponents info if possible
        p1_username = f"@{message.from_user.username}" if message.from_user.username else message.from_user.first_name
        
        # Find opponent first name
        from src.database.repositories import UserRepository
        user_repo = UserRepository(db_session)
        opp = await user_repo.get_or_create_user(opponent_id, None, "")
        p2_username = f"@{opp.username}" if opp.username else opp.first_name
        
        # Send match notification to both
        voting_markup = get_voting_keyboard(game.category_options)
        
        await message.answer(
            f"🎮 {html.bold('Соперник найден!')} Вы играете против {html.bold(p2_username)}.\n\n"
            f"🎰 {html.bold('Рулетка категорий')} 🎰\n"
            f"Выберите тему для этой дуэли. Если ваши голоса разделятся, бот сделает случайный выбор!",
            reply_markup=voting_markup
        )
        
        try:
            await bot.send_message(
                chat_id=opponent_id,
                text=f"🎮 {html.bold('Соперник найден!')} Вы играете против {html.bold(p1_username)}.\n\n"
                     f"🎰 {html.bold('Рулетка категорий')} 🎰\n"
                     f"Выберите тему для этой дуэли. Если ваши голоса разделятся, бот сделает случайный выбор!",
                reply_markup=voting_markup
            )
        except Exception as e:
            logger.error(f"Failed to send match notification to opponent {opponent_id}: {e}")

@router.message(MultiplayerStates.searching, F.text == "❌ Отменить поиск")
async def cancel_matchmaking_handler(message: Message, state: FSMContext, db_session: AsyncSession) -> None:
    user_id = message.from_user.id
    logger.info(f"User {user_id} canceled matchmaking search")
    service = MultiplayerService(db_session)
    await service.leave_queue(user_id)
    await state.clear()
    await message.answer("Поиск дуэли отменён. 🏠", reply_markup=get_main_keyboard())

@router.callback_query(F.data.startswith("duel_vote:"), MultiplayerStates.voting)
async def handle_duel_vote(callback_query: CallbackQuery, state: FSMContext, db_session: AsyncSession, bot: Bot) -> None:
    user_id = callback_query.from_user.id
    state_data = await state.get_data()
    game_id = state_data.get("game_id")
    
    if not game_id:
        await callback_query.answer("Сессия дуэли не найдена.", show_alert=True)
        return
        
    vote_idx = int(callback_query.data.split(":")[1])
    service = MultiplayerService(db_session)
    game = await service.repo.get_game_by_id(game_id)
    
    if not game or not game.category_options or vote_idx >= len(game.category_options):
        await callback_query.answer("Некорректный выбор категории.", show_alert=True)
        return
        
    chosen_cat = game.category_options[vote_idx]
    
    # Save user vote
    updated_game = await service.vote_category(game_id, user_id, chosen_cat)
    
    await callback_query.answer(f"Вы выбрали: {chosen_cat}")
    
    # Remove buttons from the message to prevent double click
    try:
        await callback_query.message.edit_text(
            text=f"🎰 {html.bold('Рулетка категорий')}\n\n"
                 f"Ваш голос: {html.bold(chosen_cat)}.\n"
                 f"Ожидаем выбор соперника... ⏳"
        )
    except Exception:
        pass
        
    if updated_game and updated_game.status == "generating":
        # Both players voted! Set state for both to waiting_for_generation
        await state.set_state(MultiplayerStates.waiting_for_generation)
        
        opponent_id = updated_game.player2_id if user_id == updated_game.player1_id else updated_game.player1_id
        opponent_key = StorageKey(bot_id=bot.id, chat_id=opponent_id, user_id=opponent_id)
        opponent_state = FSMContext(storage=state.storage, key=opponent_key)
        await opponent_state.set_state(MultiplayerStates.waiting_for_generation)
        
        # Start questions generation in the background
        asyncio.create_task(generate_and_start_duel(game_id, bot, state.storage))

async def generate_and_start_duel(game_id: int, bot: Bot, storage) -> None:
    from src.database.session import async_session
    async with async_session() as session:
        service = MultiplayerService(session)
        game = await service.repo.get_game_by_id(game_id)
        if not game:
            return
            
        # Notify both players about choice
        for pid in [game.player1_id, game.player2_id]:
            try:
                await bot.send_message(
                    chat_id=pid,
                    text=f"🎲 Рулетка выбрала тему: {html.bold(game.chosen_category)}!\n\n"
                         f"⏳ Генерирую вопросы с помощью ИИ..."
                )
            except Exception:
                pass
                
        # Generate 5 questions on the chosen category
        success = await service.generate_questions_for_game(game_id, game.chosen_category)
        
        if success:
            # Set state to in_progress for both and send first question
            for pid in [game.player1_id, game.player2_id]:
                key = StorageKey(bot_id=bot.id, chat_id=pid, user_id=pid)
                p_state = FSMContext(storage=storage, key=key)
                await p_state.set_state(MultiplayerStates.game_in_progress)
                await p_state.update_data(game_id=game_id)
                await send_current_duel_question(bot, pid, game_id, session)
        else:
            # Send failure message
            for pid in [game.player1_id, game.player2_id]:
                key = StorageKey(bot_id=bot.id, chat_id=pid, user_id=pid)
                p_state = FSMContext(storage=storage, key=key)
                await p_state.clear()
                try:
                    await bot.send_message(
                        chat_id=pid,
                        text="❌ Не удалось сгенерировать вопросы для этой категории. Дуэль отменена. Попробуйте ещё раз.",
                        reply_markup=get_main_keyboard()
                    )
                except Exception:
                    pass

async def send_current_duel_question(bot: Bot, user_id: int, game_id: int, db_session: AsyncSession) -> None:
    from src.database.repositories import MultiplayerRepository
    repo = MultiplayerRepository(db_session)
    game = await repo.get_game_by_id(game_id)
    questions = await repo.get_game_questions(game_id)
    
    if not game or not questions:
        return
        
    if user_id == game.player1_id:
        current_idx = len(game.player1_answers or [])
    else:
        current_idx = len(game.player2_answers or [])
        
    if current_idx >= len(questions):
        return
        
    question = questions[current_idx]
    
    prefixes = ["A", "B", "C", "D"]
    options_lines = []
    for idx, option in enumerate(question.options):
        prefix = prefixes[idx] if idx < len(prefixes) else f"{idx+1}"
        options_lines.append(f"{html.bold(prefix + '.')} {option}")
    options_text = "\n".join(options_lines)
    
    progress = f"Вопрос {current_idx + 1} из {len(questions)}"
    text = (
        f"⚔️ {html.bold('ДУЭЛЬ')}\n"
        f"📋 Категория: {html.code(game.chosen_category)}\n"
        f"📊 Прогресс: {html.bold(progress)}\n\n"
        f"❓ {html.bold(question.question_text)}\n\n"
        f"{options_text}"
    )
    
    await bot.send_message(chat_id=user_id, text=text, reply_markup=get_duel_options_keyboard())

@router.message(MultiplayerStates.game_in_progress, F.text.in_({"A", "B", "C", "D"}))
async def handle_duel_answer(message: Message, state: FSMContext, db_session: AsyncSession, bot: Bot) -> None:
    user_id = message.from_user.id
    state_data = await state.get_data()
    game_id = state_data.get("game_id")
    
    if not game_id:
        await message.answer("Сессия дуэли не найдена.", reply_markup=get_main_keyboard())
        await state.clear()
        return
        
    mapping = {"A": 0, "B": 1, "C": 2, "D": 3}
    option_idx = mapping.get(message.text)
    
    service = MultiplayerService(db_session)
    game = await service.repo.get_game_by_id(game_id)
    questions = await service.repo.get_game_questions(game_id)
    
    if not game or not questions:
        await message.answer("Игра не найдена.", reply_markup=get_main_keyboard())
        await state.clear()
        return
        
    if user_id == game.player1_id:
        current_idx = len(game.player1_answers or [])
    else:
        current_idx = len(game.player2_answers or [])
        
    if current_idx >= len(questions):
        await message.answer("Вы уже ответили на все вопросы.", reply_markup=get_main_keyboard())
        return
        
    question = questions[current_idx]
    
    # Submit answer
    res = await service.submit_answer(game_id, user_id, option_idx)
    if not res:
        await message.answer("Ошибка при отправке ответа.")
        return
        
    is_correct, explanation, correct_option_text, game_completed = res
    
    # Format answer options indicating correctness
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
    
    feedback = "✅ Верно!\n" if is_correct else f"❌ Неверно! Правильный ответ: {html.bold(correct_option_text)}\n"
    if explanation:
        feedback += f"\n💡 Объяснение:\n{explanation}"
        
    # Check progress
    next_idx = current_idx + 1
    has_more = (next_idx < len(questions))
    
    question_context = (
        f"⚔️ ДУЭЛЬ: {html.code(game.chosen_category)}\n"
        f"❓ {html.bold(question.question_text)}\n\n"
        f"{options_text}\n\n"
        f"{feedback}"
    )
    
    if has_more:
        await message.answer(question_context, reply_markup=get_next_duel_keyboard())
    else:
        # User finished all questions
        finish_text = (
            f"{question_context}\n\n"
            f"🎉 Вы ответили на все вопросы!\n"
            f"Ожидаем, пока ваш соперник закончит игру... ⏳"
        )
        # Check if opponent also finished
        if game_completed:
            await message.answer(question_context)
            await end_duel_game(game_id, bot, db_session, state.storage)
        else:
            await message.answer(finish_text, reply_markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="⏳ Ожидание...")]], resize_keyboard=True))

@router.message(MultiplayerStates.game_in_progress, F.text == "➡️ Следующий вопрос")
async def handle_next_duel_question(message: Message, state: FSMContext, db_session: AsyncSession, bot: Bot) -> None:
    state_data = await state.get_data()
    game_id = state_data.get("game_id")
    if not game_id:
        await message.answer("Сессия не найдена.", reply_markup=get_main_keyboard())
        await state.clear()
        return
        
    await send_current_duel_question(bot, message.from_user.id, game_id, db_session)

@router.message(MultiplayerStates.game_in_progress, F.text == "❌ Сдаться")
async def handle_duel_surrender(message: Message, state: FSMContext, db_session: AsyncSession, bot: Bot) -> None:
    state_data = await state.get_data()
    game_id = state_data.get("game_id")
    if not game_id:
        await message.answer("Сессия не найдена.", reply_markup=get_main_keyboard())
        await state.clear()
        return
        
    await handle_surrender(game_id, message.from_user.id, bot, db_session, state.storage)

async def handle_surrender(game_id: int, user_id: int, bot: Bot, session: AsyncSession, storage) -> None:
    from src.database.repositories import MultiplayerRepository
    
    repo = MultiplayerRepository(session)
    game = await repo.get_game_by_id(game_id)
    if not game or game.status != "in_progress":
        return
        
    questions = await repo.get_game_questions(game_id)
    
    # Fill remaining answers with -1 (incorrect)
    if user_id == game.player1_id:
        if game.player1_finished:
            return
        answers = list(game.player1_answers or [])
        while len(answers) < len(questions):
            answers.append(-1)
        game.player1_answers = answers
        game.player1_finished = True
        game.player1_end_time = datetime.utcnow()
        surrenderer_name = game.player1.first_name
        opponent_id = game.player2_id
    elif user_id == game.player2_id:
        if game.player2_finished:
            return
        answers = list(game.player2_answers or [])
        while len(answers) < len(questions):
            answers.append(-1)
        game.player2_answers = answers
        game.player2_finished = True
        game.player2_end_time = datetime.utcnow()
        surrenderer_name = game.player2.first_name
        opponent_id = game.player1_id
    else:
        return
        
    if game.player1_finished and game.player2_finished:
        game.status = "completed"
        
    await session.commit()
    
    # Clear FSM state for the surrenderer
    key = StorageKey(bot_id=bot.id, chat_id=user_id, user_id=user_id)
    user_state = FSMContext(storage=storage, key=key)
    await user_state.clear()
    
    await bot.send_message(
        chat_id=user_id,
        text="❌ Вы сдались и покинули дуэль. Игра засчитана как поражение. 🏠",
        reply_markup=get_main_keyboard()
    )
    
    # Notify opponent
    try:
        await bot.send_message(
            chat_id=opponent_id,
            text=f"⚠️ Соперник ({surrenderer_name}) сдался! Вы выиграли дуэль! 🎉"
        )
    except Exception:
        pass
        
    if game.status == "completed":
        await end_duel_game(game_id, bot, session, storage)

async def end_duel_game(game_id: int, bot: Bot, session: AsyncSession, storage) -> None:
    from src.services.multiplayer_service import MultiplayerService
    from src.database.repositories import UserRepository
    
    service = MultiplayerService(session)
    rewards = await service.distribute_game_rewards(game_id)
    if not rewards:
        return
        
    game = await service.repo.get_game_by_id(game_id)
    if not game:
        return
        
    user_repo = UserRepository(session)
    p1 = await user_repo.get_or_create_user(game.player1_id, None, "")
    p2 = await user_repo.get_or_create_user(game.player2_id, None, "")
    
    p1_name = p1.first_name
    p2_name = p2.first_name
    
    is_draw = rewards["is_draw"]
    winner_id = rewards["winner_id"]
    
    if is_draw:
        winner_text = "🤝 Дуэль завершилась вничью!"
    else:
        winner_name = p1_name if winner_id == game.player1_id else p2_name
        winner_text = f"🏆 Победитель: {html.bold(winner_name)}!"

    p1_speed = rewards["p1_duration"]
    p2_speed = rewards["p2_duration"]
    
    result_text = (
        f"🏁 {html.bold('Дуэль завершена!')} 🏁\n\n"
        f"📋 Категория: {html.code(game.chosen_category)}\n\n"
        f"📊 Результаты:\n"
        f"• {html.bold(p1_name)}: {game.player1_score} очков ({p1_speed} сек)\n"
        f"• {html.bold(p2_name)}: {game.player2_score} очков ({p2_speed} сек)\n\n"
        f"{winner_text}\n\n"
        f"✨ Получено опыта (XP):\n"
        f"• {html.bold(p1_name)}: +{rewards['p1_xp']} XP\n"
        f"• {html.bold(p2_name)}: +{rewards['p2_xp']} XP\n\n"
        f"Вы возвращаетесь в главное меню."
    )
    
    for user_id in [game.player1_id, game.player2_id]:
        # Clear state
        key = StorageKey(bot_id=bot.id, chat_id=user_id, user_id=user_id)
        user_state = FSMContext(storage=storage, key=key)
        await user_state.clear()
        try:
            await bot.send_message(chat_id=user_id, text=result_text, reply_markup=get_main_keyboard())
        except Exception:
            pass
