from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from src.database.models import User, QuizSession, Question

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
