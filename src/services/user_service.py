from sqlalchemy.ext.asyncio import AsyncSession
from src.database.repositories import UserRepository
from src.database.models import User

class UserService:
    def __init__(self, db_session: AsyncSession):
        self.repo = UserRepository(db_session)

    async def get_or_create_user(self, user_id: int, username: str | None, first_name: str) -> User:
        return await self.repo.get_or_create_user(user_id, username, first_name)
