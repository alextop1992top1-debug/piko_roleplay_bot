import random
import logging
import asyncio
from datetime import datetime
from config import CHARACTERS, ROLEPLAY_SETTINGS, ROLEPLAY_MODES
from database_manager import db_manager

logger = logging.getLogger(__name__)

class StoryGenerator:
    def __init__(self):
        self.scene_templates = [
            "🎸 **FNF БАНДА В СБОРЕ**\n{characters} собрались на заброшенной сцене. В воздухе витает напряжение - сегодня предстоит важное выступление!",
            "🍕 **НОЧНОЙ ПРИКЛЮЧЕНИЯ**\n{characters} оказались в ночном городе. Фонари мигают, где-то играет музыка... Что их ждет этой ночью?", 
            "🎤 **РЕПЕТИЦИЯ С СЮРПРИЗОМ**\nНа репетиции {characters} что-то пошло не так. Звук пропал, свет погас... Но это только начало!",
            "🏆 **ГРАНД-ФИНАЛ**\n{characters} вышли в финал самого престижного музыкального конкурса. Публика замерла в ожидании...",
            "🚨 **ЧРЕЗВЫЧАЙНАЯ СИТУАЦИЯ**\nВо время выступления {characters} произошло нечто неожиданное. Придется импровизировать!",
            "🎭 **КОСТЮМИРОВАННЫЙ БАЛ**\n{characters} попали на роскошный бал в масках. Но под масками скрываются тайны...",
            "🔮 **ПРОРОЧЕСТВО**\nСтарая цыганка предсказала {characters} необычное будущее. Сбудется ли пророчество?",
            "🏝️ **ЗАТЕРЯННЫЕ НА ОСТРОВЕ**\n{characters} оказались на необитаемом острове после кораблекрушения. Как они выживут?",
            "👻 **ПРИЗРАКИ ПРОШЛОГО**\nВ старом театре, где репетируют {characters}, обитают призраки прошлых исполнителей...",
            "🤖 **ТЕХНОЛОГИЧЕСКИЙ СБОЙ**\nВо время высокотехнологичного шоу {characters} система искусственного интеллекта вышла из-под контроля!",
            "🎪 **ПУТЕШЕСТВУЮЩИЙ ЦИРК**\n{characters} присоединились к загадочному цирку, который скрывает темные секреты...",
            "🕰️ **ПОПАДАНИЕ В ПРОШЛОЕ**\n{characters} неожиданно перенеслись в 80-е годы! Смогут ли они вернуться назад?",
            "🎮 **ВИРТУАЛЬНАЯ РЕАЛЬНОСТЬ**\n{characters} оказались заперты в виртуальной игре. Чтобы выжить, нужно пройти все уровни!",
            "👑 **КОРОЛЕВСКИЙ ПРИЕМ**\n{characters} приглашены на королевский бал, но среди гостей затерялся убийца...",
            "🚀 **КОСМИЧЕСКАЯ ОДИССЕЯ**\n{characters} отправились в космическое турне, но их корабль вышел на орбиту неизвестной планеты..."
        ]

    def generate_scene(self, characters=None, mode="free"):
        template = random.choice(self.scene_templates)
        
        if characters and len(characters) > 0:
            char_names = [char["character"] for char in characters]
            if len(char_names) > 3:
                char_text = f"{', '.join(char_names[:2])} и другие"
            else:
                char_text = " и ".join(char_names)
        else:
            char_text = "вся банда"
        
        scene = template.format(characters=char_text)
        return scene

class RoleplayManager:
    def __init__(self):
        self.active_sessions = {}
        self.story_gen = StoryGenerator()
    
    def create_session(self, creator_id, chat_id, theme="", mode="free"):
        session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        self.active_sessions[session_id] = {
            "id": session_id,
            "chat_id": chat_id,
            "creator": creator_id,
            "theme": theme,
            "mode": mode,
            "players": {},
            "status": "waiting",
            "created_at": datetime.now().isoformat(),
            "current_scene": "",
            "story_arc": [],
            "current_scene_index": 0,
            "pinned_message_id": None
        }
        
        logger.info(f"🎭 Создана сессия: {session_id}")
        return session_id
    
    def add_player(self, session_id, user_id, character_name, username="", first_name="", last_name=""):
        if session_id not in self.active_sessions:
            return False, "Сессия не найдена!"
        
        session = self.active_sessions[session_id]
        
        for player_id, player_data in session["players"].items():
            if player_data["character"] == character_name and player_id != user_id:
                return False, "Персонаж уже занят!"
        
        db_manager.add_user(user_id, username, first_name, last_name)
        
        session["players"][user_id] = {
            "character": character_name,
            "username": username,
            "first_name": first_name,
            "joined_at": datetime.now().isoformat(),
            "messages_count": 0
        }
        
        logger.info(f"👤 Игрок добавлен: {character_name} (ID: {user_id})")
        return True, f"✅ Вы присоединились как {character_name}!"
    
    def get_session(self, session_id):
        return self.active_sessions.get(session_id)
    
    def get_session_by_chat(self, chat_id):
        for session_id, session in self.active_sessions.items():
            if session.get("chat_id") == chat_id and session["status"] in ["waiting", "active"]:
                return session_id, session
        return None, None
    
    async def start_session(self, session_id):
        if session_id not in self.active_sessions:
            return False, "Сессия не найдена!"
        
        session = self.active_sessions[session_id]
        
        total_players = len(session["players"])
        
        if total_players >= ROLEPLAY_SETTINGS["min_players"]:
            session["status"] = "active"
            
            initial_scene = self.story_gen.generate_scene(list(session["players"].values()), session["mode"])
            session["current_scene"] = initial_scene
            session["story_arc"] = [initial_scene]
            session["current_scene_index"] = 0
            
            for user_id in session["players"]:
                db_manager.update_user_stats(user_id, sessions_delta=1)
            
            logger.info(f"🎬 Сессия запущена: {session_id} с {total_players} игроками")
            return True, initial_scene
        else:
            return False, f"Недостаточно игроков! Всего: {total_players}, нужно: {ROLEPLAY_SETTINGS['min_players']}"

    def force_start_session(self, session_id):
        if session_id not in self.active_sessions:
            return False, "Сессия не найдена!"
        
        session = self.active_sessions[session_id]
        session["status"] = "active"
        
        initial_scene = self.story_gen.generate_scene(list(session["players"].values()), session["mode"])
        session["current_scene"] = initial_scene
        session["story_arc"] = [initial_scene]
        
        for user_id in session["players"]:
            db_manager.update_user_stats(user_id, sessions_delta=1)
        
        logger.info(f"🎬 Сессия принудительно запущена: {session_id}")
        return True, initial_scene

    def end_session(self, session_id):
        if session_id not in self.active_sessions:
            return False, "Сессия не найдена!"
        
        session = self.active_sessions[session_id]
        
        players_stats = []
        total_messages = 0
        
        for user_id, player_data in session["players"].items():
            messages_count = player_data.get("messages_count", 0)
            players_stats.append({
                "user_id": user_id,
                "character": player_data["character"],
                "messages_count": messages_count,
                "username": player_data["username"],
                "first_name": player_data["first_name"]
            })
            total_messages += messages_count
            
            db_manager.update_user_stats(user_id, messages_delta=messages_count)
        
        players_stats.sort(key=lambda x: x["messages_count"], reverse=True)
        
        stats = {
            "total_players": len(players_stats),
            "total_messages": total_messages,
            "top_players": players_stats[:3],
            "session_duration": datetime.now() - datetime.fromisoformat(session["created_at"])
        }
        
        del self.active_sessions[session_id]
        
        logger.info(f"🎬 Сессия завершена: {session_id}")
        return True, stats

roleplay_manager = RoleplayManager()