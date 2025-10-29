import sqlite3
import logging
from datetime import datetime
from config import ACHIEVEMENTS

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self):
        self.conn = sqlite3.connect('roleplay_bot.db', check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.create_tables()
    
    def create_tables(self):
        cursor = self.conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS chats (
                chat_id INTEGER PRIMARY KEY,
                chat_title TEXT,
                chat_type TEXT,
                added_by INTEGER,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_allowed BOOLEAN DEFAULT 1
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                total_responses INTEGER DEFAULT 0,
                sessions_played INTEGER DEFAULT 0,
                total_messages INTEGER DEFAULT 0
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS moderators (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                added_by INTEGER,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_achievements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                achievement_id TEXT,
                unlocked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id),
                UNIQUE(user_id, achievement_id)
            )
        ''')
        
        self.conn.commit()
        logger.info("✅ База данных инициализирована")
    
    def add_chat(self, chat_id, chat_title, chat_type, added_by):
        cursor = self.conn.cursor()
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO chats (chat_id, chat_title, chat_type, added_by, is_allowed)
                VALUES (?, ?, ?, ?, 1)
            ''', (chat_id, chat_title, chat_type, added_by))
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error adding chat: {e}")
            return False
    
    def get_all_chats(self):
        cursor = self.conn.cursor()
        cursor.execute('SELECT chat_id, chat_title, chat_type, added_at FROM chats WHERE is_allowed = 1 ORDER BY added_at DESC')
        results = cursor.fetchall()
        return [dict(row) for row in results]
    
    def remove_chat(self, chat_id):
        cursor = self.conn.cursor()
        try:
            cursor.execute('DELETE FROM chats WHERE chat_id = ?', (chat_id,))
            self.conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error removing chat: {e}")
            return False
    
    def add_user(self, user_id, username, first_name, last_name):
        cursor = self.conn.cursor()
        try:
            cursor.execute('''
                INSERT OR IGNORE INTO users (user_id, username, first_name, last_name)
                VALUES (?, ?, ?, ?)
            ''', (user_id, username, first_name, last_name))
            
            cursor.execute('''
                UPDATE users SET username = ?, first_name = ?, last_name = ?
                WHERE user_id = ?
            ''', (username, first_name, last_name, user_id))
            
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error adding user: {e}")
            return False
    
    def update_user_stats(self, user_id, responses_delta=0, sessions_delta=0, messages_delta=0):
        cursor = self.conn.cursor()
        try:
            cursor.execute('''
                UPDATE users 
                SET total_responses = total_responses + ?,
                    sessions_played = sessions_played + ?,
                    total_messages = total_messages + ?
                WHERE user_id = ?
            ''', (responses_delta, sessions_delta, messages_delta, user_id))
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error updating user stats: {e}")
            return False
    
    def get_user_stats(self, user_id):
        cursor = self.conn.cursor()
        cursor.execute('SELECT username, first_name, total_responses, sessions_played, total_messages FROM users WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        if result:
            return dict(result)
        return None
    
    def add_moderator(self, user_id, username, first_name, added_by):
        cursor = self.conn.cursor()
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO moderators (user_id, username, first_name, added_by)
                VALUES (?, ?, ?, ?)
            ''', (user_id, username, first_name, added_by))
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error adding moderator: {e}")
            return False
    
    def remove_moderator(self, user_id):
        cursor = self.conn.cursor()
        try:
            cursor.execute('DELETE FROM moderators WHERE user_id = ?', (user_id,))
            self.conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error removing moderator: {e}")
            return False
    
    def get_moderators(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT m.user_id, m.username, m.first_name, m.added_at,
                   u.username as added_by_username
            FROM moderators m
            LEFT JOIN users u ON m.added_by = u.user_id
            ORDER BY m.added_at
        ''')
        results = cursor.fetchall()
        return [dict(row) for row in results]
    
    def is_moderator(self, user_id):
        cursor = self.conn.cursor()
        cursor.execute('SELECT 1 FROM moderators WHERE user_id = ?', (user_id,))
        return cursor.fetchone() is not None
    
    def unlock_achievement(self, user_id, achievement_id):
        cursor = self.conn.cursor()
        try:
            # Используем INSERT OR IGNORE для избежания дубликатов
            cursor.execute('''
                INSERT OR IGNORE INTO user_achievements (user_id, achievement_id) 
                VALUES (?, ?)
            ''', (user_id, achievement_id))
            
            if cursor.rowcount > 0:
                self.conn.commit()
                logger.info(f"✅ Достижение {achievement_id} разблокировано для пользователя {user_id}")
                return True
            else:
                logger.info(f"ℹ️ Достижение {achievement_id} уже было разблокировано для пользователя {user_id}")
                return False
                
        except Exception as e:
            logger.error(f"Error unlocking achievement: {e}")
            return False
    
    def get_user_achievements(self, user_id):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT achievement_id, unlocked_at 
            FROM user_achievements 
            WHERE user_id = ? 
            ORDER BY unlocked_at DESC
        ''', (user_id,))
        results = cursor.fetchall()
        return [dict(row) for row in results]
    
    def has_achievement(self, user_id, achievement_id):
        cursor = self.conn.cursor()
        cursor.execute('SELECT 1 FROM user_achievements WHERE user_id = ? AND achievement_id = ?', (user_id, achievement_id))
        return cursor.fetchone() is not None
    
    def check_achievements(self, user_id):
        stats = self.get_user_stats(user_id)
        if not stats:
            return []
        
        new_achievements = []
        
        # Проверяем и разблокируем достижения
        achievements_to_check = [
            ("first_roleplay", stats['sessions_played'] >= 1),
            ("active_participant", stats['total_responses'] >= 10),
            ("veteran", stats['sessions_played'] >= 5),
            ("word_master", stats['total_messages'] >= 50),
            ("social_butterfly", stats['sessions_played'] >= 10)
        ]
        
        for achievement_id, condition in achievements_to_check:
            if condition and not self.has_achievement(user_id, achievement_id):
                if self.unlock_achievement(user_id, achievement_id):
                    new_achievements.append(achievement_id)
                    logger.info(f"🎉 Новое достижение {achievement_id} для пользователя {user_id}")
        
        return new_achievements
    
    def get_achievements_count(self, user_id):
        """Получить точное количество достижений пользователя"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT COUNT(*) as count FROM user_achievements WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        return result['count'] if result else 0
    
    def get_top_players(self, limit=10):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT 
                u.user_id, 
                u.username, 
                u.first_name, 
                u.total_responses, 
                u.sessions_played, 
                u.total_messages,
                (SELECT COUNT(*) FROM user_achievements ua WHERE ua.user_id = u.user_id) as achievements_count
            FROM users u
            WHERE u.total_responses > 0 OR u.sessions_played > 0
            ORDER BY u.total_responses DESC, u.sessions_played DESC
            LIMIT ?
        ''', (limit,))
        results = cursor.fetchall()
        return [dict(row) for row in results]
    
    def cleanup_duplicate_achievements(self):
        """Очистка дубликатов достижений (для исправления проблемы)"""
        cursor = self.conn.cursor()
        try:
            # Удаляем дубликаты достижений, оставляя только первую запись
            cursor.execute('''
                DELETE FROM user_achievements 
                WHERE id NOT IN (
                    SELECT MIN(id) 
                    FROM user_achievements 
                    GROUP BY user_id, achievement_id
                )
            ''')
            deleted_count = cursor.rowcount
            self.conn.commit()
            if deleted_count > 0:
                logger.info(f"🧹 Удалено {deleted_count} дубликатов достижений")
            return deleted_count
        except Exception as e:
            logger.error(f"Error cleaning duplicate achievements: {e}")
            return 0

db_manager = DatabaseManager()

# При инициализации очистим возможные дубликаты
db_manager.cleanup_duplicate_achievements()