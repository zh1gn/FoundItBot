"""
Модели базы данных для QR-Находка
"""
import sqlite3
import threading
from datetime import datetime
from typing import Optional, List, Dict
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class Database:
    """Класс для работы с базой данных"""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self.init_database()

    def get_connection(self) -> sqlite3.Connection:
        """Получить соединение для текущего потока (создаётся один раз на поток)"""
        if not hasattr(self._local, 'conn') or self._local.conn is None:
            conn = sqlite3.connect(self.db_path, check_same_thread=False, timeout=30)
            conn.row_factory = sqlite3.Row
            # WAL-режим: несколько читателей + один писатель без блокировок
            conn.execute('PRAGMA journal_mode=WAL')
            conn.execute('PRAGMA synchronous=NORMAL')
            conn.execute('PRAGMA busy_timeout=10000')
            self._local.conn = conn
        return self._local.conn

    def init_database(self):
        """Инициализация базы данных"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT NOT NULL,
                phone TEXT,
                registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active INTEGER DEFAULT 1,
                total_items INTEGER DEFAULT 0,
                found_items INTEGER DEFAULT 0
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                qr_id TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                item_type TEXT NOT NULL,
                description TEXT,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active INTEGER DEFAULT 1,
                times_found INTEGER DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users (user_id),
                UNIQUE(qr_id, user_id)
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS findings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                qr_id TEXT NOT NULL,
                owner_id INTEGER NOT NULL,
                finder_id INTEGER NOT NULL,
                finder_name TEXT NOT NULL,
                location TEXT,
                found_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'pending',
                notes TEXT,
                FOREIGN KEY (qr_id) REFERENCES items (qr_id),
                FOREIGN KEY (owner_id) REFERENCES users (user_id),
                FOREIGN KEY (finder_id) REFERENCES users (user_id)
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS statistics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date DATE DEFAULT CURRENT_DATE,
                new_users INTEGER DEFAULT 0,
                new_items INTEGER DEFAULT 0,
                new_findings INTEGER DEFAULT 0,
                active_users INTEGER DEFAULT 0
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS achievements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                achievement_type TEXT NOT NULL,
                unlocked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id),
                UNIQUE(user_id, achievement_type)
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                finding_id INTEGER,
                rating INTEGER CHECK(rating >= 1 AND rating <= 5),
                comment TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id),
                FOREIGN KEY (finding_id) REFERENCES findings (id)
            )
        ''')

        cursor.execute('CREATE INDEX IF NOT EXISTS idx_items_user ON items(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_items_qr ON items(qr_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_findings_owner ON findings(owner_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_findings_qr ON findings(qr_id)')

        # Migration: if items table has global UNIQUE on qr_id, recreate with per-user unique
        cursor.execute("PRAGMA index_list(items)")
        indexes = [dict(row) for row in cursor.fetchall()]
        has_global_qr_unique = any(
            idx['unique'] == 1 and 'qr_id' in idx['name'] and 'user' not in idx['name']
            for idx in indexes
        )
        if has_global_qr_unique:
            try:
                cursor.execute('ALTER TABLE items RENAME TO items_old')
                cursor.execute('''
                    CREATE TABLE items (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        qr_id TEXT NOT NULL,
                        user_id INTEGER NOT NULL,
                        name TEXT NOT NULL,
                        item_type TEXT NOT NULL,
                        description TEXT,
                        added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        is_active INTEGER DEFAULT 1,
                        times_found INTEGER DEFAULT 0,
                        FOREIGN KEY (user_id) REFERENCES users (user_id),
                        UNIQUE(qr_id, user_id)
                    )
                ''')
                cursor.execute('INSERT INTO items SELECT * FROM items_old')
                cursor.execute('DROP TABLE items_old')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_items_user ON items(user_id)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_items_qr ON items(qr_id)')
                conn.commit()
                logger.info("Миграция items: UNIQUE(qr_id) -> UNIQUE(qr_id, user_id)")
            except Exception as e:
                logger.error(f"Ошибка миграции items: {e}")
                conn.rollback()

        conn.commit()
        logger.info("База данных инициализирована")

    # === ОПЕРАЦИИ С ПОЛЬЗОВАТЕЛЯМИ ===

    def create_user(self, user_id: int, username: str, full_name: str, phone: str = None) -> bool:
        """Создать нового пользователя"""
        try:
            conn = self.get_connection()
            conn.execute('''
                INSERT INTO users (user_id, username, full_name, phone)
                VALUES (?, ?, ?, ?)
            ''', (user_id, username, full_name, phone))
            conn.commit()
            logger.info(f"Создан пользователь: {user_id} - {full_name}")
            return True
        except sqlite3.IntegrityError:
            logger.warning(f"Пользователь {user_id} уже существует")
            return False
        except Exception as e:
            logger.error(f"Ошибка создания пользователя: {e}")
            return False

    def get_user(self, user_id: int) -> Optional[Dict]:
        """Получить пользователя по ID"""
        conn = self.get_connection()
        cursor = conn.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def user_exists(self, user_id: int) -> bool:
        """Проверить существование пользователя"""
        return self.get_user(user_id) is not None

    def update_user_stats(self, user_id: int, total_items: int = None, found_items: int = None):
        """Обновить статистику пользователя"""
        conn = self.get_connection()
        if total_items is not None:
            conn.execute('UPDATE users SET total_items = ? WHERE user_id = ?',
                         (total_items, user_id))
        if found_items is not None:
            conn.execute('UPDATE users SET found_items = found_items + ? WHERE user_id = ?',
                         (found_items, user_id))
        conn.commit()

    # === ОПЕРАЦИИ С ВЕЩАМИ ===

    def create_item(self, qr_id: str, user_id: int, name: str,
                    item_type: str, description: str = None) -> bool:
        """Создать новую вещь"""
        try:
            conn = self.get_connection()
            conn.execute('''
                INSERT INTO items (qr_id, user_id, name, item_type, description)
                VALUES (?, ?, ?, ?, ?)
            ''', (qr_id, user_id, name, item_type, description))
            # Обновляем счётчик в той же транзакции
            conn.execute('''
                UPDATE users SET total_items = (
                    SELECT COUNT(*) FROM items WHERE user_id = ? AND is_active = 1
                ) WHERE user_id = ?
            ''', (user_id, user_id))
            conn.commit()
            logger.info(f"Создана вещь: {qr_id} - {name}")
            return True
        except sqlite3.IntegrityError:
            logger.warning(f"QR-код {qr_id} уже существует у пользователя {user_id}")
            return False
        except Exception as e:
            logger.error(f"Ошибка создания вещи: {e}")
            return False

    def get_item_by_qr(self, qr_id: str) -> Optional[Dict]:
        """Получить вещь по QR-коду"""
        conn = self.get_connection()
        cursor = conn.execute('SELECT * FROM items WHERE qr_id = ? AND is_active = 1', (qr_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_user_items(self, user_id: int) -> List[Dict]:
        """Получить все вещи пользователя"""
        conn = self.get_connection()
        cursor = conn.execute('''
            SELECT * FROM items
            WHERE user_id = ? AND is_active = 1
            ORDER BY added_at DESC
        ''', (user_id,))
        return [dict(row) for row in cursor.fetchall()]

    def count_user_items(self, user_id: int) -> int:
        """Подсчитать количество вещей пользователя"""
        conn = self.get_connection()
        cursor = conn.execute(
            'SELECT COUNT(*) FROM items WHERE user_id = ? AND is_active = 1', (user_id,))
        return cursor.fetchone()[0]

    def delete_item(self, qr_id: str, user_id: int) -> bool:
        """Удалить вещь (мягкое удаление)"""
        try:
            conn = self.get_connection()
            conn.execute('''
                UPDATE items SET is_active = 0
                WHERE qr_id = ? AND user_id = ?
            ''', (qr_id, user_id))
            conn.execute('''
                UPDATE users SET total_items = (
                    SELECT COUNT(*) FROM items WHERE user_id = ? AND is_active = 1
                ) WHERE user_id = ?
            ''', (user_id, user_id))
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Ошибка удаления вещи: {e}")
            return False

    def increment_item_found_count(self, qr_id: str):
        """Увеличить счетчик находок вещи"""
        conn = self.get_connection()
        conn.execute('UPDATE items SET times_found = times_found + 1 WHERE qr_id = ?', (qr_id,))
        conn.commit()

    # === ОПЕРАЦИИ С НАХОДКАМИ ===

    def create_finding(self, qr_id: str, owner_id: int, finder_id: int,
                       finder_name: str, location: str = None, notes: str = None) -> bool:
        """Создать запись о находке"""
        try:
            conn = self.get_connection()
            conn.execute('''
                INSERT INTO findings (qr_id, owner_id, finder_id, finder_name, location, notes)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (qr_id, owner_id, finder_id, finder_name, location, notes))
            conn.execute(
                'UPDATE items SET times_found = times_found + 1 WHERE qr_id = ?', (qr_id,))
            conn.execute(
                'UPDATE users SET found_items = found_items + 1 WHERE user_id = ?', (owner_id,))
            conn.commit()
            logger.info(f"Создана находка: {qr_id} найдена {finder_name}")
            return True
        except Exception as e:
            logger.error(f"Ошибка создания находки: {e}")
            return False

    def get_user_findings(self, user_id: int, as_owner: bool = True) -> List[Dict]:
        """Получить находки пользователя (как владельца или нашедшего)"""
        conn = self.get_connection()
        if as_owner:
            query = '''
                SELECT f.*, i.name as item_name, i.item_type
                FROM findings f
                JOIN items i ON f.qr_id = i.qr_id
                WHERE f.owner_id = ?
                ORDER BY f.found_at DESC
            '''
        else:
            query = '''
                SELECT f.*, i.name as item_name, i.item_type
                FROM findings f
                JOIN items i ON f.qr_id = i.qr_id
                WHERE f.finder_id = ?
                ORDER BY f.found_at DESC
            '''
        cursor = conn.execute(query, (user_id,))
        return [dict(row) for row in cursor.fetchall()]

    def update_finding_status(self, finding_id: int, status: str) -> bool:
        """Обновить статус находки (pending, returned, lost)"""
        try:
            conn = self.get_connection()
            conn.execute('UPDATE findings SET status = ? WHERE id = ?', (status, finding_id))
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Ошибка обновления статуса находки: {e}")
            return False

    # === СТАТИСТИКА ===

    def get_statistics(self) -> Dict:
        """Получить общую статистику"""
        conn = self.get_connection()

        total_users = conn.execute(
            'SELECT COUNT(*) FROM users WHERE is_active = 1').fetchone()[0]
        total_items = conn.execute(
            'SELECT COUNT(*) FROM items WHERE is_active = 1').fetchone()[0]
        total_findings = conn.execute(
            'SELECT COUNT(*) FROM findings').fetchone()[0]
        active_users = conn.execute('''
            SELECT COUNT(DISTINCT user_id) FROM items
            WHERE added_at >= datetime('now', '-7 days')
        ''').fetchone()[0]

        popular_items = [dict(r) for r in conn.execute('''
            SELECT item_type, COUNT(*) as count
            FROM items WHERE is_active = 1
            GROUP BY item_type ORDER BY count DESC LIMIT 5
        ''').fetchall()]

        most_found = [dict(r) for r in conn.execute('''
            SELECT name, times_found
            FROM items WHERE is_active = 1 AND times_found > 0
            ORDER BY times_found DESC LIMIT 5
        ''').fetchall()]

        return {
            'total_users': total_users,
            'total_items': total_items,
            'total_findings': total_findings,
            'active_users': active_users,
            'avg_items_per_user': round(total_items / max(total_users, 1), 2),
            'popular_items': popular_items,
            'most_found': most_found
        }

    def get_daily_stats(self, days: int = 7) -> List[Dict]:
        """Получить статистику по дням"""
        conn = self.get_connection()
        cursor = conn.execute('''
            SELECT
                date(registered_at) as date,
                COUNT(*) as new_users
            FROM users
            WHERE registered_at >= datetime('now', '-' || ? || ' days')
            GROUP BY date(registered_at)
            ORDER BY date DESC
        ''', (days,))
        return [dict(row) for row in cursor.fetchall()]

    # === ПОИСК ===

    def search_items(self, query: str, user_id: int = None) -> List[Dict]:
        """Поиск вещей по названию"""
        conn = self.get_connection()
        if user_id:
            cursor = conn.execute('''
                SELECT * FROM items
                WHERE user_id = ? AND is_active = 1
                AND (name LIKE ? OR description LIKE ?)
                ORDER BY added_at DESC
            ''', (user_id, f'%{query}%', f'%{query}%'))
        else:
            cursor = conn.execute('''
                SELECT * FROM items
                WHERE is_active = 1
                AND (name LIKE ? OR description LIKE ?)
                ORDER BY added_at DESC LIMIT 50
            ''', (f'%{query}%', f'%{query}%'))
        return [dict(row) for row in cursor.fetchall()]

    # === ДОСТИЖЕНИЯ ===

    def unlock_achievement(self, user_id: int, achievement_type: str) -> bool:
        """Разблокировать достижение для пользователя"""
        try:
            conn = self.get_connection()
            cursor = conn.execute('''
                INSERT OR IGNORE INTO achievements (user_id, achievement_type)
                VALUES (?, ?)
            ''', (user_id, achievement_type))
            success = cursor.rowcount > 0
            conn.commit()
            if success:
                logger.info(f"Достижение {achievement_type} разблокировано для {user_id}")
            return success
        except Exception as e:
            logger.error(f"Ошибка разблокировки достижения: {e}")
            return False

    def get_user_achievements(self, user_id: int) -> List[Dict]:
        """Получить все достижения пользователя"""
        conn = self.get_connection()
        cursor = conn.execute('''
            SELECT * FROM achievements
            WHERE user_id = ?
            ORDER BY unlocked_at DESC
        ''', (user_id,))
        return [dict(row) for row in cursor.fetchall()]

    def check_achievements(self, user_id: int) -> List[str]:
        """Проверить и разблокировать новые достижения. Возвращает список новых."""
        new_achievements = []

        user = self.get_user(user_id)
        if not user:
            return new_achievements

        total_items = user['total_items']
        found_items = user['found_items']

        for threshold, key in [(1, 'first_item'), (5, 'five_items'),
                                (10, 'ten_items'), (25, 'twentyfive_items')]:
            if total_items >= threshold:
                if self.unlock_achievement(user_id, key):
                    new_achievements.append(key)

        for threshold, key in [(1, 'first_found'), (5, 'five_found')]:
            if found_items >= threshold:
                if self.unlock_achievement(user_id, key):
                    new_achievements.append(key)

        conn = self.get_connection()
        helped_count = conn.execute(
            'SELECT COUNT(*) FROM findings WHERE finder_id = ?', (user_id,)
        ).fetchone()[0]

        for threshold, key in [(3, 'helper_bronze'), (10, 'helper_silver'), (25, 'helper_gold')]:
            if helped_count >= threshold:
                if self.unlock_achievement(user_id, key):
                    new_achievements.append(key)

        return new_achievements

    # === ОТЗЫВЫ ===

    def add_review(self, user_id: int, rating: int, comment: str = None,
                   finding_id: int = None) -> bool:
        """Добавить отзыв"""
        try:
            conn = self.get_connection()
            conn.execute('''
                INSERT INTO reviews (user_id, finding_id, rating, comment)
                VALUES (?, ?, ?, ?)
            ''', (user_id, finding_id, rating, comment))
            conn.commit()
            logger.info(f"Отзыв добавлен от пользователя {user_id}")
            return True
        except Exception as e:
            logger.error(f"Ошибка добавления отзыва: {e}")
            return False

    def get_reviews(self, limit: int = 10) -> List[Dict]:
        """Получить последние отзывы"""
        conn = self.get_connection()
        cursor = conn.execute('''
            SELECT r.*, u.full_name
            FROM reviews r
            JOIN users u ON r.user_id = u.user_id
            WHERE r.rating >= 4
            ORDER BY r.created_at DESC
            LIMIT ?
        ''', (limit,))
        return [dict(row) for row in cursor.fetchall()]

    def get_average_rating(self) -> float:
        """Получить средний рейтинг"""
        conn = self.get_connection()
        avg = conn.execute('SELECT AVG(rating) FROM reviews').fetchone()[0]
        return round(avg, 1) if avg else 0.0