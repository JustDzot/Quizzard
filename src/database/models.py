from datetime import datetime
from sqlalchemy import Column, Integer, Boolean, String, DateTime, JSON, Text, ForeignKey
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)  # Telegram User ID
    username = Column(String(100), nullable=True)
    first_name = Column(String(150), nullable=False)
    joined_at = Column(DateTime, default=datetime.utcnow)

    quizzes = relationship("QuizSession", back_populates="user", cascade="all, delete-orphan")

class QuizSession(Base):
    __tablename__ = "quiz_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    topic = Column(String(255), nullable=False)
    current_question_index = Column(Integer, default=0)
    score = Column(Integer, default=0)
    total_questions = Column(Integer, default=0)
    is_completed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="quizzes")
    questions = relationship("Question", back_populates="quiz_session", cascade="all, delete-orphan", order_by="Question.id")

class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    quiz_session_id = Column(Integer, ForeignKey("quiz_sessions.id", ondelete="CASCADE"), nullable=False)
    question_text = Column(Text, nullable=False)
    options = Column(JSON, nullable=False)  # List of strings: ["Option A", "Option B", ...]
    correct_option_index = Column(Integer, nullable=False)
    explanation = Column(Text, nullable=True)
    user_answer_index = Column(Integer, nullable=True)

    quiz_session = relationship("QuizSession", back_populates="questions")