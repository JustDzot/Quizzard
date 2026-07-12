from sqlalchemy.ext.asyncio import AsyncSession
from src.database.repositories import UserRepository
from src.database.models import User

class UserService:
    def __init__(self, db_session: AsyncSession):
        self.repo = UserRepository(db_session)

    async def get_or_create_user(self, user_id: int, username: str | None, first_name: str) -> User:
        return await self.repo.get_or_create_user(user_id, username, first_name)

    def get_level_info(self, xp: int) -> dict:
        level = int((0.25 + xp / 50) ** 0.5 + 0.5)
        if level < 1:
            level = 1
            
        xp_current_level = 50 * level * (level - 1)
        xp_next_level = 50 * (level + 1) * level
        
        xp_in_level = xp - xp_current_level
        xp_needed_in_level = xp_next_level - xp_current_level
        
        progress_pct = int((xp_in_level / xp_needed_in_level) * 100) if xp_needed_in_level > 0 else 0
        progress_pct = max(0, min(100, progress_pct))
        
        filled = progress_pct // 10
        bar = "█" * filled + "░" * (10 - filled)
        
        if level <= 2:
            title = "Новичок 🟢"
        elif level <= 4:
            title = "Ученик 🟡"
        elif level <= 6:
            title = "Знаток 🔵"
        elif level <= 9:
            title = "Мастер 🟣"
        elif level <= 14:
            title = "Гроссмейстер 🔴"
        else:
            title = "Абсолютный Разум 👑"
            
        return {
            "level": level,
            "xp_in_level": xp_in_level,
            "xp_needed_in_level": xp_needed_in_level,
            "progress_pct": progress_pct,
            "bar": bar,
            "title": title,
            "xp_next_level": xp_next_level,
            "xp_current_level": xp_current_level
        }

    async def get_user_profile(self, user_id: int, first_name: str) -> dict:
        user = await self.repo.get_or_create_user(user_id, None, first_name)
        level_info = self.get_level_info(user.xp)
        
        # single player stats
        from src.database.repositories import QuizRepository
        quiz_repo = QuizRepository(self.repo.session)
        sp_stats = await quiz_repo.get_user_stats(user_id)
        
        total_duels = user.wins + user.losses + user.draws
        winrate = round((user.wins / total_duels * 100), 1) if total_duels > 0 else 0.0
        
        return {
            "user": user,
            "level_info": level_info,
            "sp_stats": sp_stats,
            "total_duels": total_duels,
            "winrate": winrate
        }
