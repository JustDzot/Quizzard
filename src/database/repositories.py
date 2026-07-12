from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from src.database.models import User, QuizSession, Question, MultiplayerGame, MultiplayerQuestion

class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_or_create_user(self, user_id: int, username: str | None, first_name: str) -> User:
        result = await self.session.execute(select(User).filter_by(id=user_id))
        user = result.scalar_one_or_none()
        if not user:
            user = User(id=user_id, username=username, first_name=first_name)
            self.session.add(user)
            await self.session.commit()
            await self.session.refresh(user)
        else:
            if user.username != username or user.first_name != first_name:
                user.username = username
                user.first_name = first_name
                await self.session.commit()
                await self.session.refresh(user)
        return user

    async def add_xp(self, user_id: int, amount: int) -> None:
        result = await self.session.execute(select(User).filter_by(id=user_id))
        user = result.scalar_one_or_none()
        if user:
            user.xp += amount
            await self.session.commit()

    async def update_stats(self, user_id: int, wins: int = 0, losses: int = 0, draws: int = 0) -> None:
        result = await self.session.execute(select(User).filter_by(id=user_id))
        user = result.scalar_one_or_none()
        if user:
            user.wins += wins
            user.losses += losses
            user.draws += draws
            await self.session.commit()


class QuizRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_quiz_session(self, user_id: int, topic: str, total_questions: int) -> QuizSession:
        quiz_session = QuizSession(user_id=user_id, topic=topic, total_questions=total_questions)
        self.session.add(quiz_session)
        await self.session.commit()
        await self.session.refresh(quiz_session)
        return quiz_session

    async def get_active_session(self, user_id: int) -> QuizSession | None:
        result = await self.session.execute(
            select(QuizSession)
            .filter_by(user_id=user_id, is_completed=False)
            .order_by(QuizSession.created_at.desc())
        )
        return result.scalar_one_or_none()

    async def get_session_by_id(self, session_id: int) -> QuizSession | None:
        result = await self.session.execute(select(QuizSession).filter_by(id=session_id))
        return result.scalar_one_or_none()

    async def add_questions(self, quiz_session_id: int, questions_data: list[dict]) -> list[Question]:
        questions = []
        for q in questions_data:
            question = Question(
                quiz_session_id=quiz_session_id,
                question_text=q["question_text"],
                options=q["options"],
                correct_option_index=q["correct_option_index"],
                explanation=q.get("explanation", "")
            )
            self.session.add(question)
            questions.append(question)
        await self.session.commit()
        return questions

    async def get_session_questions(self, session_id: int) -> list[Question]:
        result = await self.session.execute(
            select(Question)
            .filter_by(quiz_session_id=session_id)
            .order_by(Question.id.asc())
        )
        return list(result.scalars().all())

    async def save_answer(self, question_id: int, answer_index: int) -> None:
        result = await self.session.execute(select(Question).filter_by(id=question_id))
        question = result.scalar_one_or_none()
        if question:
            question.user_answer_index = answer_index
            await self.session.commit()

    async def update_session(self, session_id: int, current_question_index: int, score: int, is_completed: bool) -> None:
        result = await self.session.execute(select(QuizSession).filter_by(id=session_id))
        session = result.scalar_one_or_none()
        if session:
            session.current_question_index = current_question_index
            session.score = score
            session.is_completed = is_completed
            await self.session.commit()

    async def get_user_stats(self, user_id: int) -> dict:
        result = await self.session.execute(
            select(
                func.count(QuizSession.id),
                func.sum(QuizSession.score),
                func.sum(QuizSession.total_questions)
            )
            .filter_by(user_id=user_id, is_completed=True)
        )
        row = result.fetchone()
        
        if not row or row[0] == 0:
            return {
                "total_quizzes": 0,
                "total_score": 0,
                "total_questions": 0,
                "correct_rate": 0.0
            }
            
        total_quizzes = row[0]
        total_score = row[1] or 0
        total_questions = row[2] or 0
        correct_rate = (total_score / total_questions * 100) if total_questions > 0 else 0.0
        
        return {
            "total_quizzes": total_quizzes,
            "total_score": total_score,
            "total_questions": total_questions,
            "correct_rate": round(correct_rate, 1)
        }


class MultiplayerRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add_to_queue(self, user_id: int) -> None:
        from src.database.models import MatchmakingQueue
        result = await self.session.execute(select(MatchmakingQueue).filter_by(user_id=user_id))
        queue_entry = result.scalar_one_or_none()
        if not queue_entry:
            queue_entry = MatchmakingQueue(user_id=user_id)
            self.session.add(queue_entry)
            await self.session.commit()

    async def remove_from_queue(self, user_id: int) -> None:
        from src.database.models import MatchmakingQueue
        result = await self.session.execute(select(MatchmakingQueue).filter_by(user_id=user_id))
        queue_entry = result.scalar_one_or_none()
        if queue_entry:
            await self.session.delete(queue_entry)
            await self.session.commit()

    async def get_first_waiting_user(self, exclude_user_id: int) -> int | None:
        from src.database.models import MatchmakingQueue
        result = await self.session.execute(
            select(MatchmakingQueue)
            .filter(MatchmakingQueue.user_id != exclude_user_id)
            .order_by(MatchmakingQueue.created_at.asc())
            .limit(1)
        )
        entry = result.scalar_one_or_none()
        return entry.user_id if entry else None

    async def create_multiplayer_game(self, player1_id: int, player2_id: int, category_options: list[str]) -> MultiplayerGame:
        from src.database.models import MultiplayerGame
        game = MultiplayerGame(
            player1_id=player1_id,
            player2_id=player2_id,
            category_options=category_options,
            player1_answers=[],
            player2_answers=[],
            status="voting"
        )
        self.session.add(game)
        await self.session.commit()
        await self.session.refresh(game)
        return game

    async def get_active_multiplayer_game(self, user_id: int) -> MultiplayerGame | None:
        from src.database.models import MultiplayerGame
        from sqlalchemy import or_
        result = await self.session.execute(
            select(MultiplayerGame)
            .filter(
                or_(MultiplayerGame.player1_id == user_id, MultiplayerGame.player2_id == user_id),
                MultiplayerGame.status != "completed"
            )
            .order_by(MultiplayerGame.created_at.desc())
        )
        return result.scalar_one_or_none()

    async def get_game_by_id(self, game_id: int) -> MultiplayerGame | None:
        from src.database.models import MultiplayerGame
        result = await self.session.execute(select(MultiplayerGame).filter_by(id=game_id))
        return result.scalar_one_or_none()

    async def submit_vote(self, game_id: int, user_id: int, vote: str) -> MultiplayerGame | None:
        game = await self.get_game_by_id(game_id)
        if not game or game.status != "voting":
            return None
        
        if game.player1_id == user_id:
            game.player1_vote = vote
        elif game.player2_id == user_id:
            game.player2_vote = vote

        # Check if both voted
        if game.player1_vote and game.player2_vote:
            import random
            if game.player1_vote == game.player2_vote:
                game.chosen_category = game.player1_vote
            else:
                game.chosen_category = random.choice([game.player1_vote, game.player2_vote])
            game.status = "generating"
            
        await self.session.commit()
        await self.session.refresh(game)
        return game

    async def add_multiplayer_questions(self, game_id: int, questions_data: list[dict]) -> None:
        from src.database.models import MultiplayerQuestion
        for q in questions_data:
            question = MultiplayerQuestion(
                game_id=game_id,
                question_text=q["question_text"],
                options=q["options"],
                correct_option_index=q["correct_option_index"],
                explanation=q.get("explanation", "")
            )
            self.session.add(question)
        
        game = await self.get_game_by_id(game_id)
        if game:
            game.status = "in_progress"
            
        await self.session.commit()

    async def get_game_questions(self, game_id: int) -> list[MultiplayerQuestion]:
        from src.database.models import MultiplayerQuestion
        result = await self.session.execute(
            select(MultiplayerQuestion)
            .filter_by(game_id=game_id)
            .order_by(MultiplayerQuestion.id.asc())
        )
        return list(result.scalars().all())

    async def submit_answer(self, game_id: int, user_id: int, answer_index: int) -> tuple[bool, MultiplayerQuestion] | None:
        game = await self.get_game_by_id(game_id)
        if not game or game.status != "in_progress":
            return None

        questions = await self.get_game_questions(game_id)
        
        if game.player1_id == user_id:
            if game.player1_finished:
                return None
            
            if not game.player1_start_time:
                game.player1_start_time = datetime.utcnow()
                
            current_idx = len(game.player1_answers or [])
            if current_idx >= len(questions):
                return None
            
            question = questions[current_idx]
            is_correct = (question.correct_option_index == answer_index)
            
            current_answers = list(game.player1_answers or [])
            current_answers.append(answer_index)
            game.player1_answers = current_answers
            
            if is_correct:
                game.player1_score += 1
                
            if len(game.player1_answers) >= len(questions):
                game.player1_finished = True
                game.player1_end_time = datetime.utcnow()

        elif game.player2_id == user_id:
            if game.player2_finished:
                return None
            
            if not game.player2_start_time:
                game.player2_start_time = datetime.utcnow()
                
            current_idx = len(game.player2_answers or [])
            if current_idx >= len(questions):
                return None
            
            question = questions[current_idx]
            is_correct = (question.correct_option_index == answer_index)
            
            current_answers = list(game.player2_answers or [])
            current_answers.append(answer_index)
            game.player2_answers = current_answers
            
            if is_correct:
                game.player2_score += 1
                
            if len(game.player2_answers) >= len(questions):
                game.player2_finished = True
                game.player2_end_time = datetime.utcnow()
        else:
            return None

        if game.player1_finished and game.player2_finished:
            game.status = "completed"

        await self.session.commit()
        await self.session.refresh(game)
        return is_correct, question
