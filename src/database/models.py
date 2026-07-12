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
    xp = Column(Integer, default=0, nullable=False)
    wins = Column(Integer, default=0, nullable=False)
    losses = Column(Integer, default=0, nullable=False)
    draws = Column(Integer, default=0, nullable=False)

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

class MatchmakingQueue(Base):
    __tablename__ = "matchmaking_queue"

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User")

class MultiplayerGame(Base):
    __tablename__ = "multiplayer_games"

    id = Column(Integer, primary_key=True, autoincrement=True)
    player1_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    player2_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    category_options = Column(JSON, nullable=True)  # list of 3 strings
    player1_vote = Column(String(255), nullable=True)
    player2_vote = Column(String(255), nullable=True)
    chosen_category = Column(String(255), nullable=True)
    
    status = Column(String(50), default="voting", nullable=False)  # 'voting', 'generating', 'in_progress', 'completed'
    
    player1_score = Column(Integer, default=0, nullable=False)
    player2_score = Column(Integer, default=0, nullable=False)
    
    player1_finished = Column(Boolean, default=False, nullable=False)
    player2_finished = Column(Boolean, default=False, nullable=False)
    
    player1_answers = Column(JSON, nullable=True)  # list of dicts/ints
    player2_answers = Column(JSON, nullable=True)  # list of dicts/ints
    
    player1_start_time = Column(DateTime, nullable=True)
    player1_end_time = Column(DateTime, nullable=True)
    player2_start_time = Column(DateTime, nullable=True)
    player2_end_time = Column(DateTime, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    player1 = relationship("User", foreign_keys=[player1_id])
    player2 = relationship("User", foreign_keys=[player2_id])
    questions = relationship("MultiplayerQuestion", back_populates="game", cascade="all, delete-orphan", order_by="MultiplayerQuestion.id")

class MultiplayerQuestion(Base):
    __tablename__ = "multiplayer_questions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    game_id = Column(Integer, ForeignKey("multiplayer_games.id", ondelete="CASCADE"), nullable=False)
    question_text = Column(Text, nullable=False)
    options = Column(JSON, nullable=False)  # List of 4 strings
    correct_option_index = Column(Integer, nullable=False)
    explanation = Column(Text, nullable=True)

    game = relationship("MultiplayerGame", back_populates="questions")