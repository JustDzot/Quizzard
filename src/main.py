import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from src.config import settings
from src.database.session import async_session
from src.middlewares.db_midleware import DbSessionMiddleware
from src.handlers import router as main_router

async def main() -> None:
    # Инициализация логирования
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        stream=sys.stdout
    )
    logger = logging.getLogger(__name__)
    logger.info("Starting Quizzard bot...")

    # Инициализация бота и диспетчера
    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher()

    # Подключение Middleware для инъекции сессии БД
    dp.update.outer_middleware(DbSessionMiddleware(async_session))

    # Подключение обработчиков (handlers)
    dp.include_router(main_router)

    # Запуск polling
    logger.info("Bot is ready and polling!")
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())