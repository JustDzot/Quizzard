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
                    text=f"📋 <b>Лог бота:</b>\n<pre>{log_entry}</pre>"
                ))
        except Exception:
            pass

async def main() -> None:
    # Инициализация корневого логгера
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))
    
    # Форматтер для логов
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    
    # Вывод в консоль (sys.stdout) - пишет всё (уровень LOG_LEVEL)
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    root_logger.addHandler(stream_handler)
    
    # Запись в файл - пишет только WARNING и выше
    file_handler = logging.FileHandler(settings.log_file, encoding="utf-8")
    file_handler.setLevel(logging.WARNING)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)
    
    logger = logging.getLogger(__name__)
    logger.info("Starting Quizzard bot...")

    # Инициализация основного бота и диспетчера
    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher()

    # Подключение логгера для Telegram через отдельного бота (пишет всё от уровня INFO и выше)
    logs_bot = None
    if settings.logs_bot_token and settings.admin_chat_id:
        logs_bot = Bot(token=settings.logs_bot_token)
        tg_handler = TelegramLoggingHandler(logs_bot, settings.admin_chat_id)
        tg_handler.setLevel(logging.INFO)  # Пересылает все логи (INFO, WARNING, ERROR)
        tg_handler.setFormatter(formatter)
        root_logger.addHandler(tg_handler)
        logger.info(f"Telegram logs bot initialized for admin chat: {settings.admin_chat_id}")

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
        if logs_bot:
            await logs_bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())