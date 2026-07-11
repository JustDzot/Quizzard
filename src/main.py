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

class TelegramLoggingHandler(logging.Handler):
    def __init__(self, bot: Bot, chat_id: int):
        super().__init__()
        self.bot = bot
        self.chat_id = chat_id

    def emit(self, record):
        try:
            log_entry = self.format(record)
            # Limit message length to avoid Telegram character limit issues
            if len(log_entry) > 3500:
                log_entry = log_entry[:3500] + "\n...[TRUNCATED]..."
            
            loop = asyncio.get_running_loop()
            if loop.is_running():
                # Schedule message sending in the active asyncio event loop
                loop.create_task(self.bot.send_message(
                    chat_id=self.chat_id,
                    text=f"⚠️ <b>Системный лог:</b>\n<pre>{log_entry}</pre>"
                ))
        except Exception:
            pass

async def main() -> None:
    # Инициализация логирования с выводом в консоль и в файл
    log_handlers = [
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(settings.log_file, encoding="utf-8")
    ]
    
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=log_handlers
    )
    
    logger = logging.getLogger(__name__)
    logger.info("Starting Quizzard bot...")

    # Инициализация бота и диспетчера
    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher()

    # Подключение логгера для Telegram, если указан ID администратора
    if settings.admin_chat_id:
        tg_handler = TelegramLoggingHandler(bot, settings.admin_chat_id)
        tg_handler.setLevel(logging.WARNING)  # Отправляем только WARNING и ERROR
        tg_handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
        logging.getLogger().addHandler(tg_handler)
        logger.info(f"Telegram logger initialized for admin chat: {settings.admin_chat_id}")

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