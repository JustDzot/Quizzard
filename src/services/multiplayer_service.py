import logging
import random
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from src.database.repositories import MultiplayerRepository, UserRepository
from src.services.llm_client import LLMClient
from src.database.models import MultiplayerGame

logger = logging.getLogger(__name__)

class MultiplayerService:
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session
        self.repo = MultiplayerRepository(db_session)
        self.user_repo = UserRepository(db_session)
        self.llm_client = LLMClient()

    async def join_queue(self, user_id: int) -> tuple[MultiplayerGame | None, int | None]:
        """
        Adds user to matchmaking queue. If another player is available, matches them,
        creates a new multiplayer game, and returns (game, opponent_id).
        Otherwise returns (None, None).
        """
        # Add current user to queue
        await self.repo.add_to_queue(user_id)
        
        # Look for another player
        opponent_id = await self.repo.get_first_waiting_user(user_id)
        if opponent_id:
            # Match found! Remove both from the queue
            await self.repo.remove_from_queue(user_id)
            await self.repo.remove_from_queue(opponent_id)
            
            # Generate 3 categories for the duel
            categories = await self.llm_client.generate_duel_categories()
            
            # Create multiplayer game session (player 1 is the one who was waiting, player 2 is the joiner)
            game = await self.repo.create_multiplayer_game(
                player1_id=opponent_id,
                player2_id=user_id,
                category_options=categories
            )
            logger.info(f"Match found! Duel Game {game.id} created between Player 1 ({opponent_id}) and Player 2 ({user_id})")
            return game, opponent_id
            
        return None, None

    async def leave_queue(self, user_id: int) -> None:
        """Removes user from matchmaking queue."""
        await self.repo.remove_from_queue(user_id)

    async def vote_category(self, game_id: int, user_id: int, vote: str) -> MultiplayerGame | None:
        """Records a category vote for the user."""
        return await self.repo.submit_vote(game_id, user_id, vote)

    async def generate_questions_for_game(self, game_id: int, category: str) -> bool:
        """Generates 5 questions on the chosen category and saves them to the game."""
        questions_data = await self.llm_client.generate_questions(
            topic=category,
            difficulty="medium",
            count=5
        )
        if not questions_data:
            logger.error(f"Failed to generate multiplayer questions for Game {game_id} on category '{category}'")
            return False
            
        await self.repo.add_multiplayer_questions(game_id, questions_data)
        logger.info(f"Questions successfully generated and saved for Duel Game {game_id}")
        return True

    async def submit_answer(self, game_id: int, user_id: int, answer_index: int) -> tuple[bool, str, str, bool] | None:
        """
        Submits answer for a user.
        Returns: tuple of (is_correct, explanation, correct_option_text, game_completed)
        """
        res = await self.repo.submit_answer(game_id, user_id, answer_index)
        if not res:
            return None
            
        is_correct, question = res
        
        # Get correct answer text
        correct_text = ""
        if 0 <= question.correct_option_index < len(question.options):
            correct_text = question.options[question.correct_option_index]
            
        game = await self.repo.get_game_by_id(game_id)
        game_completed = (game.status == "completed") if game else False
        
        return is_correct, question.explanation or "", correct_text, game_completed

    async def distribute_game_rewards(self, game_id: int) -> dict | None:
        """
        Distributes XP and updates win/loss stats upon game completion.
        Returns result summary.
        """
        game = await self.repo.get_game_by_id(game_id)
        if not game or game.status != "completed":
            return None
            
        p1_score = game.player1_score
        p2_score = game.player2_score
        
        # Calculate completion speed (seconds)
        p1_dur = 999.0
        p2_dur = 999.0
        if game.player1_start_time and game.player1_end_time:
            p1_dur = (game.player1_end_time - game.player1_start_time).total_seconds()
        if game.player2_start_time and game.player2_end_time:
            p2_dur = (game.player2_end_time - game.player2_start_time).total_seconds()
            
        is_draw = False
        winner_id = None
        loser_id = None
        
        if p1_score > p2_score:
            winner_id = game.player1_id
            loser_id = game.player2_id
        elif p2_score > p1_score:
            winner_id = game.player2_id
            loser_id = game.player1_id
        else:
            # Scores are equal, use duration as tiebreaker
            if abs(p1_dur - p2_dur) < 0.1:
                is_draw = True
            elif p1_dur < p2_dur:
                winner_id = game.player1_id
                loser_id = game.player2_id
            else:
                winner_id = game.player2_id
                loser_id = game.player1_id

        # Calculate XP
        # Correct answer XP: 15 XP each
        # Winner bonus: 50 XP
        # Loser bonus: 10 XP
        # Draw bonus: 25 XP
        p1_correct_xp = p1_score * 15
        p2_correct_xp = p2_score * 15
        
        if is_draw:
            p1_bonus = 25
            p2_bonus = 25
            await self.user_repo.update_stats(game.player1_id, draws=1)
            await self.user_repo.update_stats(game.player2_id, draws=1)
        else:
            if winner_id == game.player1_id:
                p1_bonus = 50
                p2_bonus = 10
                await self.user_repo.update_stats(game.player1_id, wins=1)
                await self.user_repo.update_stats(game.player2_id, losses=1)
            else:
                p1_bonus = 10
                p2_bonus = 50
                await self.user_repo.update_stats(game.player2_id, wins=1)
                await self.user_repo.update_stats(game.player1_id, losses=1)

        p1_xp = p1_correct_xp + p1_bonus
        p2_xp = p2_correct_xp + p2_bonus
        
        # Add XP to users
        await self.user_repo.add_xp(game.player1_id, p1_xp)
        await self.user_repo.add_xp(game.player2_id, p2_xp)
        
        logger.info(f"Rewards distributed for Duel {game_id}: Winner={winner_id} (Draw={is_draw}), P1_XP={p1_xp}, P2_XP={p2_xp}")
        
        return {
            "winner_id": winner_id,
            "loser_id": loser_id,
            "is_draw": is_draw,
            "p1_xp": p1_xp,
            "p2_xp": p2_xp,
            "p1_score": p1_score,
            "p2_score": p2_score,
            "p1_duration": round(p1_dur, 1) if p1_dur < 990 else "N/A",
            "p2_duration": round(p2_dur, 1) if p2_dur < 990 else "N/A"
        }
