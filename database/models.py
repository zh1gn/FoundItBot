"""
Модели базы данных для QR-Находка
"""
import sqlite3
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
        self.init_database()
    
    def get_connection(self):
        """Получить подключение к БД"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def init_database(self):
        """Инициализация базы данных"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Таблица пользователей
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
        
        # Таблица вещей
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                qr_id TEXT UNIQUE NOT NULL,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                item_type TEXT NOT NULL,
                description TEXT,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active INTEGER DEFAULT 1,
                times_found INTEGER DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
        
        # Таблица находок
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
        
        # Таблица статистики
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
        
        # Индексы для быстрого поиска
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_items_user ON items(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_items_qr ON items(qr_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_findings_owner ON findings(owner_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_findings_qr ON findings(qr_id)')
        
        conn.commit()
        conn.close()
        logger.info("База данных инициализирована")
    
    # === ОПЕРАЦИИ С ПОЛЬЗОВАТЕЛЯМИ ===
    
    def create_user(self, user_id: int, username: str, full_name: str, phone: str = None) -> bool:
        """Создать нового пользователя"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO users (user_id, username, full_name, phone)
                VALUES (?, ?, ?, ?)
            ''', (user_id, username, full_name, phone))
            conn.commit()
            conn.close()
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
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None
    
    def user_exists(self, user_id: int) -> bool:
        """Проверить существование пользователя"""
        return self.get_user(user_id) is not None
    
    def update_user_stats(self, user_id: int, total_items: int = None, found_items: int = None):
        """Обновить статистику пользователя"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if total_items is not None:
            cursor.execute('UPDATE users SET total_items = ? WHERE user_id = ?', 
                         (total_items, user_id))
        
        if found_items is not None:
            cursor.execute('UPDATE users SET found_items = found_items + ? WHERE user_id = ?', 
                         (found_items, user_id))
        
        conn.commit()
        conn.close()
    
    # === ОПЕРАЦИИ С ВЕЩАМИ ===
    
    def create_item(self, qr_id: str, user_id: int, name: str, 
                   item_type: str, description: str = None) -> bool:
        """Создать новую вещь"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO items (qr_id, user_id, name, item_type, description)
                VALUES (?, ?, ?, ?, ?)
            ''', (qr_id, user_id, name, item_type, description))
            conn.commit()
            conn.close()
            
            # Обновляем счетчик вещей пользователя
            self.update_user_stats(user_id, self.count_user_items(user_id))
            
            logger.info(f"Создана вещь: {qr_id} - {name}")
            return True
        except sqlite3.IntegrityError:
            logger.warning(f"QR-код {qr_id} уже существует")
            return False
        except Exception as e:
            logger.error(f"Ошибка создания вещи: {e}")
            return False
    
    def get_item_by_qr(self, qr_id: str) -> Optional[Dict]:
        """Получить вещь по QR-коду"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM items WHERE qr_id = ? AND is_active = 1', (qr_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None
    
    def get_user_items(self, user_id: int) -> List[Dict]:
        """Получить все вещи пользователя"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM items 
            WHERE user_id = ? AND is_active = 1
            ORDER BY added_at DESC
        ''', (user_id,))
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    
    def count_user_items(self, user_id: int) -> int:
        """Подсчитать количество вещей пользователя"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM items WHERE user_id = ? AND is_active = 1', 
                      (user_id,))
        count = cursor.fetchone()[0]
        conn.close()
        return count
    
    def delete_item(self, qr_id: str, user_id: int) -> bool:
        """Удалить вещь (мягкое удаление)"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE items SET is_active = 0 
                WHERE qr_id = ? AND user_id = ?
            ''', (qr_id, user_id))
            conn.commit()
            conn.close()
            
            # Обновляем счетчик
            self.update_user_stats(user_id, self.count_user_items(user_id))
            return True
        except Exception as e:
            logger.error(f"Ошибка удаления вещи: {e}")
            return False
    
    def increment_item_found_count(self, qr_id: str):
        """Увеличить счетчик находок вещи"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE items SET times_found = times_found + 1 WHERE qr_id = ?', 
                      (qr_id,))
        conn.commit()
        conn.close()
    
    # === ОПЕРАЦИИ С НАХОДКАМИ ===
    
    def create_finding(self, qr_id: str, owner_id: int, finder_id: int, 
                      finder_name: str, location: str = None, notes: str = None) -> bool:
        """Создать запись о находке"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO findings (qr_id, owner_id, finder_id, finder_name, location, notes)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (qr_id, owner_id, finder_id, finder_name, location, notes))
            conn.commit()
            conn.close()
            
            # Обновляем счетчики
            self.increment_item_found_count(qr_id)
            self.update_user_stats(owner_id, found_items=1)
            
            logger.info(f"Создана находка: {qr_id} найдена {finder_name}")
            return True
        except Exception as e:
            logger.error(f"Ошибка создания находки: {e}")
            return False
    
    def get_user_findings(self, user_id: int, as_owner: bool = True) -> List[Dict]:
        """Получить находки пользователя (как владельца или нашедшего)"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
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
        
        cursor.execute(query, (user_id,))
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    
    def update_finding_status(self, finding_id: int, status: str) -> bool:
        """Обновить статус находки (pending, returned, lost)"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('UPDATE findings SET status = ? WHERE id = ?', (status, finding_id))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Ошибка обновления статуса находки: {e}")
            return False
    
    # === СТАТИСТИКА ===
    
    def get_statistics(self) -> Dict:
        """Получить общую статистику"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Общее количество пользователей
        cursor.execute('SELECT COUNT(*) FROM users WHERE is_active = 1')
        total_users = cursor.fetchone()[0]
        
        # Общее количество вещей
        cursor.execute('SELECT COUNT(*) FROM items WHERE is_active = 1')
        total_items = cursor.fetchone()[0]
        
        # Общее количество находок
        cursor.execute('SELECT COUNT(*) FROM findings')
        total_findings = cursor.fetchone()[0]
        
        # Активные пользователи за последние 7 дней
        cursor.execute('''
            SELECT COUNT(DISTINCT user_id) FROM items 
            WHERE added_at >= datetime('now', '-7 days')
        ''')
        active_users = cursor.fetchone()[0]
        
        # Популярные типы вещей
        cursor.execute('''
            SELECT item_type, COUNT(*) as count 
            FROM items 
            WHERE is_active = 1
            GROUP BY item_type 
            ORDER BY count DESC 
            LIMIT 5
        ''')
        popular_items = [dict(row) for row in cursor.fetchall()]
        
        # Вещи с наибольшим количеством находок
        cursor.execute('''
            SELECT name, times_found 
            FROM items 
            WHERE is_active = 1 AND times_found > 0
            ORDER BY times_found DESC 
            LIMIT 5
        ''')
        most_found = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        
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
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT 
                date(registered_at) as date,
                COUNT(*) as new_users
            FROM users
            WHERE registered_at >= datetime('now', '-' || ? || ' days')
            GROUP BY date(registered_at)
            ORDER BY date DESC
        ''', (days,))
        
        stats = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return stats
    
    # === ПОИСК ===
    
    def search_items(self, query: str, user_id: int = None) -> List[Dict]:
        """Поиск вещей по названию"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if user_id:
            cursor.execute('''
                SELECT * FROM items 
                WHERE user_id = ? AND is_active = 1 
                AND (name LIKE ? OR description LIKE ?)
                ORDER BY added_at DESC
            ''', (user_id, f'%{query}%', f'%{query}%'))
        else:
            cursor.execute('''
                SELECT * FROM items 
                WHERE is_active = 1 
                AND (name LIKE ? OR description LIKE ?)
                ORDER BY added_at DESC
                LIMIT 50
            ''', (f'%{query}%', f'%{query}%'))
        
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]