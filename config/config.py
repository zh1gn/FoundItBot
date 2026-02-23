"""
Конфигурация проекта QR-Finder
"""
import os
from pathlib import Path

BASE_DIR     = Path(__file__).resolve().parent.parent
DATABASE_DIR = BASE_DIR / 'database'

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '8238565811:AAFwz18jnwCd88AKjcWiTZ19swChIdkrCQ0')
BOT_USERNAME       = os.getenv('BOT_USERNAME', 'QR_FinderBot')

# БД
DATABASE_PATH = DATABASE_DIR / 'qr_finder.db'

# Логирование
LOG_LEVEL  = os.getenv('LOG_LEVEL', 'INFO')
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

# Пакеты QR-кодов — каждый даёт 1 QR на весь срок
QR_PACKAGES = {
    'month_1': {
        'label': '1 месяц — 300 тг',
        'price': 300,
        'days':  30,
        'emoji': '🥉',
    },
    'month_3': {
        'label': '3 месяца — 700 тг',
        'price': 700,
        'days':  90,
        'emoji': '🥈',
    },
    'month_6': {
        'label': '6 месяцев — 1200 тг',
        'price': 1200,
        'days':  180,
        'emoji': '🥇',
    },
}

# Обратная совместимость
SUBSCRIPTION_PLANS = QR_PACKAGES

# Реквизиты оплаты
PAYMENT_DETAILS = os.getenv('PAYMENT_DETAILS', 'Kaspi: +7XXXXXXXXXX')

# ID администратора
ADMIN_ID = int(os.getenv('ADMIN_ID', '1403802771'))
