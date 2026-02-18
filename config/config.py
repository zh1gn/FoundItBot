"""
Конфигурация проекта QR-Находка
"""
import os
from pathlib import Path

# Базовые пути
BASE_DIR = Path(__file__).resolve().parent.parent
DATABASE_DIR = BASE_DIR / 'database'
STATIC_DIR = BASE_DIR / 'static'

# Telegram Bot
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '8238565811:AAFwz18jnwCd88AKjcWiTZ19swChIdkrCQ0')
BOT_USERNAME = os.getenv('BOT_USERNAME', 'QR_FinderBot')

# База данных
DATABASE_PATH = DATABASE_DIR / 'qr_finder.db'

# Веб-сервер
WEB_HOST = os.getenv('WEB_HOST', '0.0.0.0')
WEB_PORT = int(os.getenv('WEB_PORT', 5000))
SECRET_KEY = os.getenv('SECRET_KEY', 'your-secret-key-change-in-production')

# URL для QR-кодов
BASE_URL = os.getenv('BASE_URL', f'http://localhost:{WEB_PORT}')

# Настройки QR
QR_CODE_SIZE = 10
QR_CODE_BORDER = 2

# Типы вещей с эмодзи
ITEM_TYPES = {
    'рюкзак': '🎒',
    'ключи': '🔑',
    'обувь': '👟',
    'куртка': '🧥',
    'телефон': '📱',
    'наушники': '🎧',
    'кошелек': '💰',
    'очки': '👓',
    'часы': '⌚',
    'зонт': '☂️',
    'книга': '📚',
    'другое': '📦'
}

# Логирование
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

# Бизнес-метрики
STICKER_COST = 18  # тенге
STICKER_PRICE = 60  # тенге
PACKAGE_PRICES = {
    'mini': {'count': 3, 'price': 300},
    'standard': {'count': 5, 'price': 400},
    'maxi': {'count': 10, 'price': 700}
}