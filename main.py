"""
Основной модуль Telegram бота QR-Находка
"""
import logging
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

from config.config import TELEGRAM_BOT_TOKEN, DATABASE_PATH
from database.models import Database
from bot.handlers import (
    start_handler,
    additem_handler,
    myitems_handler,
    stats_handler,
    help_handler,
    message_handler,
    button_handler,
    found_handler,
    delete_handler,
    history_handler,
    achievements_handler,
    review_handler,
    leaderboard_handler
)

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


class QRFinderBot:
    """Главный класс бота"""
    
    def __init__(self, token: str):
        self.token = token
        self.db = Database(DATABASE_PATH)
        self.application = None
    
    def setup_handlers(self):
        """Настройка обработчиков команд"""
        self.application.add_handler(CommandHandler("start", start_handler))
        self.application.add_handler(CommandHandler("additem", additem_handler))
        self.application.add_handler(CommandHandler("myitems", myitems_handler))
        self.application.add_handler(CommandHandler("stats", stats_handler))
        self.application.add_handler(CommandHandler("help", help_handler))
        self.application.add_handler(CommandHandler("delete", delete_handler))
        self.application.add_handler(CommandHandler("history", history_handler))
        self.application.add_handler(CommandHandler("achievements", achievements_handler))
        self.application.add_handler(CommandHandler("review", review_handler))
        self.application.add_handler(CommandHandler("leaderboard", leaderboard_handler))
        
        # Обработчик кнопок
        self.application.add_handler(CallbackQueryHandler(button_handler))
        
        # Обработчик текстовых сообщений
        self.application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler)
        )
        
        logger.info("Обработчики настроены")
    
    def run(self):
        """Запуск бота"""
        if not self.token:
            logger.error("TELEGRAM_BOT_TOKEN не установлен!")
            logger.error("Установите токен: export TELEGRAM_BOT_TOKEN='ваш_токен'")
            return
        
        # Создание приложения
        self.application = Application.builder().token(self.token).build()
        
        # Настройка обработчиков
        self.setup_handlers()
        
        # Запуск polling
        logger.info("🚀 QR-Находка бот запущен!")
        logger.info("Нажмите Ctrl+C для остановки")
        
        self.application.run_polling(allowed_updates=Update.ALL_TYPES)


def main():
    """Точка входа"""
    bot = QRFinderBot(TELEGRAM_BOT_TOKEN)
    bot.run()


if __name__ == '__main__':
    main()