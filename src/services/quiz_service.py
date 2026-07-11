from sqlalchemy.ext.asyncio import AsyncSession
from src.database.repositories import QuizRepository
from src.services.llm_client import LLMClient
from src.database.models import QuizSession, Question

class QuizService:
    def __init__(self, db_session: AsyncSession):
        self.repo = QuizRepository(db_session)
        self.llm_client = LLMClient()

    async def start_quiz_session(self, user_id: int, topic: str, difficulty: str = "medium", count: int = 5, on_chunk = None) -> QuizSession | None:
        # Mark any previous active session as completed before starting a new one
        active = await self.repo.get_active_session(user_id)
        if active:
            await self.repo.update_session(active.id, active.current_question_index, active.score, is_completed=True)

        # Generate questions using LLM
        questions_data = await self.llm_client.generate_questions(topic, difficulty, count, on_chunk=on_chunk)
        if not questions_data:
            return None

        diff_titles = {
            "easy": "Легкая 🟢",
            "medium": "Средняя 🟡",
            "hard": "Сложная 🔴"
        }
        display_topic = f"{topic} ({diff_titles.get(difficulty, 'Средняя 🟡')})"

        # Create session and save questions
        session = await self.repo.create_quiz_session(user_id, display_topic, len(questions_data))
        await self.repo.add_questions(session.id, questions_data)
        return session

    async def get_current_question(self, session_id: int) -> Question | None:
        session = await self.repo.get_session_by_id(session_id)
        if not session or session.is_completed:
            return None
        questions = await self.repo.get_session_questions(session_id)
        if 0 <= session.current_question_index < len(questions):
            return questions[session.current_question_index]
        return None

    async def submit_answer(self, session_id: int, answer_index: int) -> tuple[bool, Question] | None:
        session = await self.repo.get_session_by_id(session_id)
        if not session or session.is_completed:
            return None

        questions = await self.repo.get_session_questions(session_id)
        current_idx = session.current_question_index
        if not (0 <= current_idx < len(questions)):
            return None

        question = questions[current_idx]
        is_correct = (question.correct_option_index == answer_index)

        # Save answer
        await self.repo.save_answer(question.id, answer_index)

        # Update stats
        new_score = session.score + (1 if is_correct else 0)
        next_idx = current_idx + 1
        is_completed = (next_idx >= len(questions))

        await self.repo.update_session(session.id, next_idx, new_score, is_completed)
        return is_correct, question
