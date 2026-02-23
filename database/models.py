"""
Модели базы данных QR-Находка
"""
import sqlite3
import logging
import uuid
import qrcode
import io
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


def _qr_image_bytes(url: str) -> bytes:
    """Генерирует PNG QR-кода и возвращает bytes."""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class Database:
    def __init__(self, db_path):
        self.db_path = str(db_path)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self.init_db()

    # ──────────────────────────────────────────────
    # Инициализация
    # ──────────────────────────────────────────────

    def init_db(self):
        conn = self.get_connection()
        cur  = conn.cursor()

        # Пользователи
        cur.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id     INTEGER PRIMARY KEY,
                username    TEXT    DEFAULT '',
                full_name   TEXT    DEFAULT '',
                total_items INTEGER DEFAULT 0,
                is_active   INTEGER DEFAULT 1,
                created_at  TEXT    DEFAULT (datetime('now'))
            )
        ''')

        # Подписки
        cur.execute('''
            CREATE TABLE IF NOT EXISTS subscriptions (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                plan        TEXT    NOT NULL,
                started_at  TEXT    NOT NULL DEFAULT (datetime('now')),
                expires_at  TEXT    NOT NULL,
                qr_used     INTEGER DEFAULT 0,
                is_active   INTEGER DEFAULT 1,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        ''')

        # Вещи — без названия, только QR ID и срок
        cur.execute('''
            CREATE TABLE IF NOT EXISTS items (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                qr_id       TEXT    UNIQUE NOT NULL,
                user_id     INTEGER NOT NULL,
                times_found INTEGER DEFAULT 0,
                is_active   INTEGER DEFAULT 1,
                added_at    TEXT    DEFAULT (datetime('now')),
                expires_at  TEXT,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        ''')

        # Находки
        cur.execute('''
            CREATE TABLE IF NOT EXISTS findings (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                qr_id        TEXT    NOT NULL,
                owner_id     INTEGER NOT NULL,
                finder_id    INTEGER,
                finder_name  TEXT    DEFAULT 'Аноним',
                finder_username TEXT DEFAULT '',
                found_at     TEXT    DEFAULT (datetime('now')),
                FOREIGN KEY (qr_id) REFERENCES items(qr_id)
            )
        ''')

        # Ожидающие подтверждения платежи
        cur.execute('''
            CREATE TABLE IF NOT EXISTS pending_payments (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id    INTEGER NOT NULL,
                plan       TEXT    NOT NULL,
                created_at TEXT    DEFAULT (datetime('now'))
            )
        ''')

        # Отзывы
        cur.execute('''
            CREATE TABLE IF NOT EXISTS reviews (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                full_name   TEXT    DEFAULT '',
                rating      INTEGER NOT NULL,
                review_text TEXT    DEFAULT '',
                created_at  TEXT    DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        ''')

        conn.commit()
        conn.close()
        logger.info("База данных инициализирована")

    # ──────────────────────────────────────────────

    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # ── Пользователи ──────────────────────────────

    def user_exists(self, user_id: int) -> bool:
        conn = self.get_connection()
        cur  = conn.cursor()
        cur.execute('SELECT 1 FROM users WHERE user_id = ?', (user_id,))
        result = cur.fetchone()
        conn.close()
        return result is not None

    def create_user(self, user_id: int, username: str, full_name: str):
        conn = self.get_connection()
        cur  = conn.cursor()
        cur.execute(
            'INSERT OR IGNORE INTO users (user_id, username, full_name) VALUES (?, ?, ?)',
            (user_id, username, full_name)
        )
        conn.commit()
        conn.close()

    def get_user(self, user_id: int) -> Optional[dict]:
        conn = self.get_connection()
        cur  = conn.cursor()
        cur.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        row = cur.fetchone()
        conn.close()
        return dict(row) if row else None

    # ── Подписки ──────────────────────────────────

    def get_active_subscription(self, user_id: int) -> Optional[dict]:
        conn = self.get_connection()
        cur  = conn.cursor()
        cur.execute('''
            SELECT * FROM subscriptions
            WHERE user_id = ? AND is_active = 1
              AND expires_at > datetime('now')
            ORDER BY expires_at DESC LIMIT 1
        ''', (user_id,))
        row = cur.fetchone()
        conn.close()
        return dict(row) if row else None

    def create_subscription(self, user_id: int, plan: str, days: int) -> dict:
        conn    = self.get_connection()
        cur     = conn.cursor()
        cur.execute(
            'UPDATE subscriptions SET is_active = 0 WHERE user_id = ? AND is_active = 1',
            (user_id,)
        )
        started   = datetime.now()
        expires   = started + timedelta(days=days)
        started_s = started.strftime('%Y-%m-%d %H:%M:%S')
        expires_s = expires.strftime('%Y-%m-%d %H:%M:%S')
        cur.execute(
            'INSERT INTO subscriptions (user_id, plan, started_at, expires_at) VALUES (?, ?, ?, ?)',
            (user_id, plan, started_s, expires_s)
        )
        conn.commit()
        conn.close()
        return {'plan': plan, 'started_at': started_s, 'expires_at': expires_s}

    def mark_qr_used(self, user_id: int):
        """Отметить что QR уже создан в рамках подписки."""
        conn = self.get_connection()
        cur  = conn.cursor()
        cur.execute('''
            UPDATE subscriptions SET qr_used = 1
            WHERE user_id = ? AND is_active = 1
              AND expires_at > datetime('now')
        ''', (user_id,))
        conn.commit()
        conn.close()

    def add_pending_payment(self, user_id: int, plan: str):
        conn = self.get_connection()
        cur  = conn.cursor()
        cur.execute(
            'INSERT INTO pending_payments (user_id, plan) VALUES (?, ?)',
            (user_id, plan)
        )
        conn.commit()
        conn.close()

    def get_pending_payments(self) -> list:
        conn = self.get_connection()
        cur  = conn.cursor()
        cur.execute('''
            SELECT pp.*, u.full_name, u.username
            FROM pending_payments pp
            JOIN users u ON pp.user_id = u.user_id
            ORDER BY pp.created_at ASC
        ''')
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows

    def delete_pending_payment(self, payment_id: int):
        conn = self.get_connection()
        cur  = conn.cursor()
        cur.execute('DELETE FROM pending_payments WHERE id = ?', (payment_id,))
        conn.commit()
        conn.close()

    # ── Вещи ──────────────────────────────────────

    def _generate_qr_id(self) -> str:
        conn = self.get_connection()
        cur  = conn.cursor()
        while True:
            qr_id = 'QR' + uuid.uuid4().hex[:6].upper()
            cur.execute('SELECT 1 FROM items WHERE qr_id = ?', (qr_id,))
            if not cur.fetchone():
                conn.close()
                return qr_id

    def create_item(self, user_id: int, expires_at: Optional[str] = None) -> Optional[dict]:
        """Создать QR без названия. Возвращает словарь или None."""
        qr_id = self._generate_qr_id()
        conn  = self.get_connection()
        cur   = conn.cursor()
        try:
            cur.execute(
                'INSERT INTO items (qr_id, user_id, expires_at) VALUES (?, ?, ?)',
                (qr_id, user_id, expires_at)
            )
            cur.execute(
                'UPDATE users SET total_items = total_items + 1 WHERE user_id = ?',
                (user_id,)
            )
            conn.commit()
            return {'qr_id': qr_id, 'expires_at': expires_at}
        except Exception as e:
            logger.error(f"Ошибка создания вещи: {e}")
            return None
        finally:
            conn.close()

    def get_user_items(self, user_id: int) -> list:
        conn = self.get_connection()
        cur  = conn.cursor()
        cur.execute(
            'SELECT * FROM items WHERE user_id = ? AND is_active = 1 ORDER BY added_at DESC',
            (user_id,)
        )
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows

    def get_item_by_qr(self, qr_id: str) -> Optional[dict]:
        conn = self.get_connection()
        cur  = conn.cursor()
        cur.execute('SELECT * FROM items WHERE qr_id = ? AND is_active = 1', (qr_id,))
        row = cur.fetchone()
        conn.close()
        return dict(row) if row else None

    def delete_item(self, qr_id: str, user_id: int) -> bool:
        conn = self.get_connection()
        cur  = conn.cursor()
        cur.execute(
            'UPDATE items SET is_active = 0 WHERE qr_id = ? AND user_id = ?',
            (qr_id, user_id)
        )
        affected = cur.rowcount
        if affected:
            cur.execute(
                'UPDATE users SET total_items = MAX(0, total_items - 1) WHERE user_id = ?',
                (user_id,)
            )
        conn.commit()
        conn.close()
        return affected > 0

    def generate_qr_image(self, qr_id: str, bot_username: str) -> bytes:
        url = f"https://t.me/{bot_username}?start=found_{qr_id}"
        return _qr_image_bytes(url)

    # ── Находки ───────────────────────────────────

    def create_finding(self, qr_id: str, owner_id: int,
                       finder_id: int, finder_name: str,
                       finder_username: str = '') -> bool:
        conn = self.get_connection()
        cur  = conn.cursor()
        try:
            cur.execute('''
                INSERT INTO findings (qr_id, owner_id, finder_id, finder_name, finder_username)
                VALUES (?, ?, ?, ?, ?)
            ''', (qr_id, owner_id, finder_id, finder_name, finder_username or ''))
            cur.execute(
                'UPDATE items SET times_found = times_found + 1 WHERE qr_id = ?',
                (qr_id,)
            )
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Ошибка записи находки: {e}")
            return False
        finally:
            conn.close()

    def get_user_findings(self, user_id: int, as_owner: bool = True) -> list:
        conn = self.get_connection()
        cur  = conn.cursor()
        if as_owner:
            cur.execute('''
                SELECT f.* FROM findings f
                WHERE f.owner_id = ?
                ORDER BY f.found_at DESC LIMIT 20
            ''', (user_id,))
        else:
            cur.execute('''
                SELECT f.* FROM findings f
                WHERE f.finder_id = ?
                ORDER BY f.found_at DESC LIMIT 20
            ''', (user_id,))
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows

    def get_active_package(self, user_id: int) -> Optional[dict]:
        """Алиас для get_active_subscription — используется в handlers."""
        return self.get_active_subscription(user_id)

    # ── Отзывы ────────────────────────────────────

    def add_review(self, user_id: int, full_name: str, rating: int, review_text: str) -> bool:
        conn = self.get_connection()
        cur  = conn.cursor()
        try:
            cur.execute(
                'INSERT INTO reviews (user_id, full_name, rating, review_text) VALUES (?, ?, ?, ?)',
                (user_id, full_name, rating, review_text or '')
            )
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Ошибка сохранения отзыва: {e}")
            return False
        finally:
            conn.close()

    # ── Статистика ────────────────────────────────

    def get_statistics(self) -> dict:
        conn = self.get_connection()
        cur  = conn.cursor()
        cur.execute('SELECT COUNT(*) AS cnt FROM users WHERE is_active = 1')
        total_users = cur.fetchone()['cnt']
        cur.execute('SELECT COUNT(*) AS cnt FROM items WHERE is_active = 1')
        total_items = cur.fetchone()['cnt']
        cur.execute('SELECT COUNT(*) AS cnt FROM findings')
        total_findings = cur.fetchone()['cnt']
        cur.execute('SELECT COUNT(*) AS cnt FROM reviews')
        total_reviews = cur.fetchone()['cnt']
        avg_rating = 0.0
        if total_reviews:
            cur.execute('SELECT AVG(rating) AS avg FROM reviews')
            row = cur.fetchone()
            avg_rating = round(row['avg'], 1) if row['avg'] else 0.0
        avg_per_user = round(total_items / total_users, 1) if total_users else 0
        conn.close()
        return {
            'total_users':    total_users,
            'total_items':    total_items,
            'total_findings': total_findings,
            'avg_per_user':   avg_per_user,
            'total_reviews':  total_reviews,
            'avg_rating':     avg_rating,
        }