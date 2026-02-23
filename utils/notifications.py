"""
Утилиты QR-Находка
"""
from datetime import datetime
from typing import Optional


def format_time_ago(timestamp: str) -> str:
    """Форматировать время в 'X назад'."""
    try:
        dt      = datetime.fromisoformat(timestamp)
        seconds = (datetime.now() - dt).total_seconds()
        if seconds < 60:
            return "только что"
        elif seconds < 3600:
            m = int(seconds / 60)
            return f"{m} {'минуту' if m == 1 else 'минут'} назад"
        elif seconds < 86400:
            h = int(seconds / 3600)
            return f"{h} {'час' if h == 1 else 'часов'} назад"
        else:
            d = int(seconds / 86400)
            return f"{d} {'день' if d == 1 else 'дней'} назад"
    except Exception:
        return timestamp[:10]


def generate_qr_url(qr_id: str, bot_username: str) -> str:
    return f"https://t.me/{bot_username}?start=found_{qr_id}"
