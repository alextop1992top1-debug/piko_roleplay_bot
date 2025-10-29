import asyncio
import logging
import sqlite3
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandObject
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN, ADMIN_ID, CHARACTERS, ROLEPLAY_SETTINGS, ROLEPLAY_MODES, USER_CHARACTER_MAPPING, MODERATORS, ACHIEVEMENTS
from roleplay_manager import roleplay_manager
from database_manager import db_manager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

def is_moderator(user_id):
    return user_id == ADMIN_ID or db_manager.is_moderator(user_id)

def is_admin(user_id):
    return user_id == ADMIN_ID

def get_character_for_user(user_id, username, first_name):
    if username:
        username_with_at = f"@{username}"
        if username_with_at in USER_CHARACTER_MAPPING:
            return USER_CHARACTER_MAPPING[username_with_at]
        if username in USER_CHARACTER_MAPPING:
            return USER_CHARACTER_MAPPING[username]
    
    if first_name and first_name in USER_CHARACTER_MAPPING:
        return USER_CHARACTER_MAPPING[first_name]
    
    return None

def can_user_join_with_character(session, user_id, character_name):
    if user_id in session["players"]:
        return False, "Вы уже в ролевой!"
    
    for player_id, player_data in session["players"].items():
        if player_data["character"] == character_name and player_id != user_id:
            return False, "Эта роль уже занята!"
    
    return True, "Можно присоединиться"

def create_join_keyboard(session):
    keyboard_buttons = []
    
    for character_name, character_data in CHARACTERS.items():
        role_taken = False
        for player_data in session["players"].values():
            if player_data["character"] == character_name:
                role_taken = True
                break
        
        if not role_taken:
            button_text = f"🎭 {character_name} - {character_data['role']}"
            keyboard_buttons.append([
                InlineKeyboardButton(text=button_text, callback_data=f"join_{character_name}")
            ])
        else:
            button_text = f"❌ {character_name} - Занята"
            keyboard_buttons.append([
                InlineKeyboardButton(text=button_text, callback_data="role_taken")
            ])
    
    if not keyboard_buttons:
        keyboard_buttons.append([
            InlineKeyboardButton(text="❌ Все роли заняты", callback_data="all_roles_taken")
        ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

async def set_bot_commands():
    """Установка команд меню бота"""
    commands = [
        types.BotCommand(command="help", description="📖 Помощь"),
        types.BotCommand(command="role", description="🎭 Моя роль"),
        types.BotCommand(command="stats", description="📊 Статистика"),
        types.BotCommand(command="achievements", description="🏆 Достижения"),
        types.BotCommand(command="top", description="🏅 Топ игроков"),
        types.BotCommand(command="roles", description="👥 Все роли"),
        types.BotCommand(command="start_rp", description="🎬 Начать ролевую"),
        types.BotCommand(command="force_start", description="⚡ Принудительный старт"),
        types.BotCommand(command="stop_rp", description="🛑 Завершить ролевую"),
        types.BotCommand(command="moderators", description="📋 Модераторы"),
        types.BotCommand(command="chats", description="💬 Чаты"),
    ]
    await bot.set_my_commands(commands)
    logger.info("✅ Команды бота установлены в меню")

@dp.message(Command("help"))
async def help_cmd(message: types.Message):
    if message.chat.type == "private":
        await message.answer("❌ Бот работает только в группах и чатах! Добавьте меня в группу для использования.")
        return
    
    user_status = ""
    if message.from_user.id == ADMIN_ID:
        user_status = "👑 Главный администратор"
    elif is_moderator(message.from_user.id):
        user_status = "🔧 Модератор"
    else:
        user_status = "👤 Игрок"
    
    help_text = (
        f"🎭 **Ролевой бот Пико Пиковича - Справка**\n\n"
        f"🔑 **Ваш статус:** {user_status}\n\n"
    )
    
    if message.from_user.id == ADMIN_ID:
        help_text += (
            "**👑 Команды администратора:**\n"
            "• /moderators - 📋 Список модераторов\n"
            "• /add_moderator @юзернейм - ➕ Добавить модератора\n"
            "• /add_moderator_id ID - ➕ Добавить модератора по ID\n"
            "• /remove_moderator @юзернейм - ➖ Удалить модератора\n"
            "• /chats - 💬 Список всех чатов\n"
            "• /выйти ID - 🚪 Выйти из чата\n\n"
        )
    
    if is_moderator(message.from_user.id):
        help_text += (
            "**⚡ Команды модератора:**\n"
            "• /start_rp - 🎬 Начать ролевую\n"
            "• /force_start - ⚡ Принудительно начать ролевую\n"
            "• /stop_rp - 🛑 Завершить ролевую\n\n"
        )
    
    help_text += (
        "**🎮 Общие команды:**\n"
        "• /role - 🎭 Узнать свою роль\n"
        "• /stats - 📊 Моя статистика\n"
        "• /achievements - 🏆 Мои достижения\n"
        "• /top - 🏅 Топ игроков\n"
        "• /roles - 👥 Все роли\n\n"
        "💡 **Как играть:**\n"
        "1. Модератор запускает /start_rp\n"
        "2. Игроки присоединяются к своим ролям\n"
        "3. Бот начинает историю\n"
        "4. Игроки пишут от имени персонажей\n"
        "5. Модератор завершает /stop_rp\n\n"
        "📞 **Поддержка:** @PicoFromTheVoid"
    )
    
    await message.answer(help_text)

# АДМИНИСТРАТИВНЫЕ КОМАНДЫ
@dp.message(Command("moderators"))
async def moderators_cmd(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Только главный администратор может просматривать модераторов!")
        return
    
    moderators = db_manager.get_moderators()
    
    if not moderators:
        moderators_text = "📋 **Список модераторов:**\n\n• Вы (Главный администратор)"
    else:
        moderators_list = ["• Вы (Главный администратор)"]
        for mod in moderators:
            added_by = f" (добавил @{mod['added_by_username']})" if mod['added_by_username'] else ""
            mod_info = f"• {mod['first_name']}"
            if mod['username']:
                mod_info += f" (@{mod['username']})"
            mod_info += f" - ID: {mod['user_id']}{added_by}"
            moderators_list.append(mod_info)
        
        moderators_text = "📋 **Список модераторов:**\n\n" + "\n".join(moderators_list)
    
    await message.answer(moderators_text)

@dp.message(Command("add_moderator"))
async def add_moderator_cmd(message: types.Message, command: CommandObject):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Только главный администратор может добавлять модераторов!")
        return
    
    if not command.args:
        await message.answer("❌ Укажите юзернейм: `/add_moderator @username`")
        return
    
    username = command.args.strip()
    if not username.startswith('@'):
        username = f"@{username}"
    
    try:
        user = await bot.get_chat(username)
        
        if user.id == ADMIN_ID:
            await message.answer("❌ Этот пользователь уже главный администратор!")
            return
        
        success = db_manager.add_moderator(
            user.id, 
            user.username or "", 
            user.first_name or "Пользователь", 
            message.from_user.id
        )
        
        if success:
            await message.answer(
                f"✅ **Пользователь добавлен в модераторы!**\n\n"
                f"👤 Имя: {user.first_name or 'Не указано'}\n"
                f"📧 Юзернейм: {username}\n"
                f"🆔 ID: `{user.id}`"
            )
            
            try:
                await bot.send_message(
                    user.id,
                    "🎉 **Вас назначили модератором ролевого бота!**\n\n"
                    "Теперь вы можете:\n"
                    "• Запускать ролевые (/start_rp)\n"
                    "• Останавливать ролевые (/stop_rp)\n"
                    "• Использовать /force_start\n\n"
                    "Спасибо за помощь в модерации! 👑"
                )
            except Exception as e:
                logger.warning(f"Не удалось отправить сообщение модератору: {e}")
                await message.answer("⚠️ Не удалось отправить сообщение новому модератору")
        else:
            await message.answer("❌ Ошибка при добавлении модератора")
            
    except Exception as e:
        logger.error(f"Error adding moderator {username}: {e}")
        await message.answer(
            f"❌ Не удалось найти пользователя {username}.\n\n"
            "**Возможные причины:**\n"
            "• Пользователь с таким юзернеймом не существует\n" 
            "• Пользователь никогда не писал боту\n"
            "• Бот заблокирован пользователем\n\n"
            "💡 **Решение:** Попросите пользователя написать боту в ЛС команду /start"
        )

@dp.message(Command("add_moderator_id"))
async def add_moderator_id_cmd(message: types.Message, command: CommandObject):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Только главный администратор может добавлять модераторов!")
        return
    
    if not command.args:
        await message.answer("❌ Укажите ID: `/add_moderator_id 123456789`")
        return
    
    try:
        user_id = int(command.args)
        
        if user_id == ADMIN_ID:
            await message.answer("❌ Этот пользователь уже главный администратор!")
            return
        
        try:
            user = await bot.get_chat(user_id)
            
            success = db_manager.add_moderator(
                user.id, 
                user.username or "", 
                user.first_name or "Пользователь", 
                message.from_user.id
            )
            
            if success:
                await message.answer(
                    f"✅ **Пользователь добавлен в модераторы!**\n\n"
                    f"👤 Имя: {user.first_name or 'Не указано'}\n"
                    f"📧 Юзернейм: @{user.username or 'отсутствует'}\n"
                    f"🆔 ID: `{user.id}`"
                )
                
                try:
                    await bot.send_message(
                        user.id,
                        "🎉 **Вас назначили модератором ролевого бота!**\n\n"
                        "Теперь вы можете:\n"
                        "• Запускать ролевые (/start_rp)\n"
                        "• Останавливать ролевые (/stop_rp)\n"
                        "• Использовать /force_start\n\n"
                        "Спасибо за помощь в модерации! 👑"
                    )
                except:
                    await message.answer("⚠️ Не удалось отправить сообщение новому модератору")
            else:
                await message.answer("❌ Ошибка при добавлении модератора")
                
        except Exception as e:
            await message.answer(f"❌ Не удалось найти пользователя с ID {user_id}. Убедитесь что ID правильный и пользователь писал боту.")
            
    except ValueError:
        await message.answer("❌ Неверный ID! ID должен быть числом.")

@dp.message(Command("remove_moderator"))
async def remove_moderator_cmd(message: types.Message, command: CommandObject):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Только главный администратор может удалять модераторов!")
        return
    
    if not command.args:
        await message.answer("❌ Укажите юзернейм: `/remove_moderator @username`")
        return
    
    username = command.args.strip()
    if not username.startswith('@'):
        username = f"@{username}"
    
    try:
        moderators = db_manager.get_moderators()
        moderator_to_remove = None
        
        for mod in moderators:
            if mod['username'] and mod['username'].lower() == username[1:].lower():
                moderator_to_remove = mod
                break
        
        if not moderator_to_remove:
            await message.answer(f"❌ Модератор с юзернеймом {username} не найден!")
            return
        
        success = db_manager.remove_moderator(moderator_to_remove['user_id'])
        
        if success:
            await message.answer(f"✅ Модератор {username} удален!")
        else:
            await message.answer("❌ Ошибка при удалении модератора!")
        
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")

@dp.message(Command("chats"))
async def my_chats_cmd(message: types.Message):
    """Список чатов с ботом (только для админа)"""
    logger.info(f"💬 Команда /chats от {message.from_user.id}")
    
    if not is_admin(message.from_user.id):
        await message.answer("❌ Только главный администратор может просматривать чаты!")
        return
    
    chats = db_manager.get_all_chats()
    
    if not chats:
        await message.answer("📋 Бот пока не добавлен ни в один чат")
        return
    
    chats_list = []
    for i, chat in enumerate(chats, 1):
        chat_info = f"{i}. {chat['chat_title']} ({chat['chat_type']})"
        chat_info += f"\n   ID: `{chat['chat_id']}`"
        chats_list.append(chat_info)
    
    chats_text = "📋 **ЧАТЫ С БОТОМ:**\n\n" + "\n\n".join(chats_list)
    chats_text += "\n\n💡 Используйте /выйти ID для выхода"
    
    await message.answer(chats_text)

@dp.message(Command("выйти"))
async def leave_chat_cmd(message: types.Message, command: CommandObject):
    """Выйти из чата (только для админа)"""
    logger.info(f"🚪 Команда /выйти от {message.from_user.id}")
    
    if not is_admin(message.from_user.id):
        await message.answer("❌ Только главный администратор может выходить из чатов!")
        return
    
    if not command.args:
        await message.answer("❌ Укажите ID чата: `/выйти 123456789`")
        return
    
    try:
        chat_id = int(command.args)
        
        try:
            await bot.leave_chat(chat_id)
            db_manager.remove_chat(chat_id)
            await message.answer(f"✅ Бот вышел из чата {chat_id}")
        except Exception as e:
            await message.answer(f"❌ Не удалось выйти из чата {chat_id}: {e}")
            
    except ValueError:
        await message.answer("❌ Неверный ID чата! ID должен быть числом.")

# ОСНОВНЫЕ КОМАНДЫ ПОЛЬЗОВАТЕЛЯ
@dp.message(Command("role"))
async def my_role_cmd(message: types.Message):
    """Показать роль пользователя"""
    logger.info(f"🎭 Команда /role от {message.from_user.id}")
    
    user_role = get_character_for_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name
    )
    
    if user_role:
        role_data = CHARACTERS[user_role]
        await message.answer(
            f"🎭 **ВАША РОЛЬ:** {user_role}\n"
            f"📝 **Амплуа:** {role_data['role']}\n"
            f"ℹ️ **Описание:** {role_data['desc']}\n\n"
            f"💡 Эта роль закреплена за вашим юзернеймом/именем автоматически!"
        )
    else:
        await message.answer(
            "❌ **У вас нет назначенной роли!**\n\n"
            "Возможные причины:\n"
            "• Ваш юзернейм не указан в списке распределения ролей\n"
            "• Ваше имя не совпадает с назначенными именами\n"
            "• Роль временно недоступна\n\n"
            "📞 Обратитесь к @PicoFromTheVoid для получения роли"
        )

@dp.message(Command("stats"))
async def user_stats(message: types.Message):
    """Статистика пользователя"""
    logger.info(f"📊 Команда /stats от {message.from_user.id}")
    
    try:
        db_manager.add_user(
            message.from_user.id,
            message.from_user.username,
            message.from_user.first_name,
            message.from_user.last_name
        )
        
        user_id = message.from_user.id
        stats = db_manager.get_user_stats(user_id)
        
        user_role = get_character_for_user(
            user_id, 
            message.from_user.username,
            message.from_user.first_name
        )
        
        if stats:
            achievements = db_manager.get_user_achievements(user_id)
            achievements_count = db_manager.get_achievements_count(user_id)
            
            stats_text = (
                f"📊 **ВАША СТАТИСТИКА** 📊\n\n"
                f"👤 **Имя:** {stats['first_name'] or message.from_user.first_name}\n"
                f"📧 **Юзернейм:** @{stats['username'] or 'отсутствует'}\n"
                f"🎭 **Ваша роль:** {user_role or 'Не назначена'}\n\n"
                f"📈 **Активность:**\n"
                f"💭 **Ответов отправлено:** {stats['total_responses']}\n"
                f"🕹️ **Сессий сыграно:** {stats['sessions_played']}\n"
                f"📨 **Всего сообщений:** {stats['total_messages']}\n"
                f"🏆 **Достижений:** {achievements_count}\n\n"
                f"💡 Используйте /achievements чтобы посмотреть свои достижения"
            )
        else:
            stats_text = (
                "📊 **Статистика не найдена**\n\n"
                "🎮 **Возможно, вы еще не участвовали в ролевых.**\n"
                "💫 **Присоединяйтесь к ролевой сессии чтобы начать собирать статистику!**"
            )
        
        await message.answer(stats_text)
    except Exception as e:
        logger.error(f"Error in user_stats: {e}")
        await message.answer("❌ Ошибка при получении статистики")

@dp.message(Command("achievements"))
async def achievements_cmd(message: types.Message):
    """Мои достижения"""
    logger.info(f"🏆 Команда /achievements от {message.from_user.id}")
    
    try:
        user_id = message.from_user.id
        achievements = db_manager.get_user_achievements(user_id)
        
        if achievements:
            achievements_list = []
            for ach in achievements:
                achievement_data = ACHIEVEMENTS.get(ach['achievement_id'])
                if achievement_data:
                    date = datetime.fromisoformat(ach['unlocked_at']).strftime("%d.%m.%Y")
                    achievements_list.append(f"• **{achievement_data['name']}**\n  📅 {date} - {achievement_data['desc']}")
            
            achievements_text = f"🏆 **ВАШИ ДОСТИЖЕНИЯ ({len(achievements_list)}):** 🏆\n\n" + "\n\n".join(achievements_list)
        else:
            achievements_text = (
                "🏆 **У вас пока нет достижений.**\n\n"
                "🎮 **Как получить достижения:**\n"
                "• 🎭 Участвуйте в ролевых сессиях\n"
                "• 💬 Активно пишите от имени своего персонажа\n"
                "• ⭐ Принимайте участие в разных ролевых\n\n"
                "💫 **Первое достижение ждет вас уже в первой ролевой!**"
            )
        
        await message.answer(achievements_text)
    except Exception as e:
        logger.error(f"Error in achievements: {e}")
        await message.answer("❌ Ошибка при получении достижений")

@dp.message(Command("top"))
async def top_cmd(message: types.Message):
    """Топ игроков"""
    logger.info(f"🏅 Команда /top от {message.from_user.id}")
    
    try:
        top_players = db_manager.get_top_players(10)
        
        if top_players:
            top_list = []
            for i, player in enumerate(top_players, 1):
                medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
                name = player['first_name'] or player['username'] or f"Игрок {player['user_id']}"
                top_list.append(f"{medal} **{name}** - {player['total_responses']} ответов, {player['sessions_played']} сессий")
            
            top_text = "🏆 **ТОП ИГРОКОВ** 🏆\n\n" + "\n".join(top_list)
        else:
            top_text = (
                "🏆 **Пока нет статистики игроков.**\n\n"
                "🎮 **Будьте первым в топе!**\n"
                "💫 **Участвуйте в ролевых и набирайте очки активности!**"
            )
        
        await message.answer(top_text)
    except Exception as e:
        logger.error(f"Error in top: {e}")
        await message.answer("❌ Ошибка при получении топа")

@dp.message(Command("roles"))
async def all_roles_cmd(message: types.Message):
    """Показывает все роли и их владельцев"""
    logger.info(f"👥 Команда /roles от {message.from_user.id}")
    
    try:
        roles_text = "🎭 **ВСЕ РОЛИ И ИХ ВЛАДЕЛЬЦЫ** 🎭\n\n"
        
        for character, data in CHARACTERS.items():
            owner = None
            for username, char in USER_CHARACTER_MAPPING.items():
                if char == character:
                    owner = username
                    break
            
            if owner:
                roles_text += f"• **{character}** - {data['role']}\n  👤 **Владелец:** {owner}\n\n"
            else:
                roles_text += f"• **{character}** - {data['role']}\n  🤖 **Свободная роль**\n\n"
        
        await message.answer(roles_text)
    except Exception as e:
        logger.error(f"Error in all_roles: {e}")
        await message.answer("❌ Ошибка при получении списка ролей")

@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    logger.info(f"✅ Команда /start от {message.from_user.id}")
    
    if message.chat.type == "private":
        await message.answer(
            "🎭 **Ролевой бот Пико Пиковича**\n\n"
            "❌ **Бот работает только в группах и чатах!**\n\n"
            "💡 **Добавьте меня в группу для использования ролевых функций:**\n"
            "1. Создайте группу\n"
            "2. Добавьте меня туда\n"
            "3. Используйте команды для запуска ролевых!\n\n"
            "🎮 **Начните ваше первое приключение!**"
        )
        return
    
    db_manager.add_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name,
        message.from_user.last_name
    )
    
    if message.chat.type != "private":
        db_manager.add_chat(
            message.chat.id,
            message.chat.title,
            message.chat.type,
            message.from_user.id
        )
    
    user_role = get_character_for_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name
    )
    
    user_status = ""
    if message.from_user.id == ADMIN_ID:
        user_status = "👑 Главный администратор"
    elif is_moderator(message.from_user.id):
        user_status = "🔧 Модератор"
    else:
        user_status = "👤 Игрок"
    
    chat_type = "групповом чате"
    role_info = f"🎭 Ваша роль: {user_role}" if user_role else "❌ У вас нет назначенной роли"
    
    start_text = (
        f"🎭 **Ролевой бот Пико Пиковича**\n\n"
        f"✅ **Бот активирован в {chat_type}!**\n"
        f"🔑 **Ваш статус:** {user_status}\n"
        f"{role_info}\n\n"
        f"💡 Используйте /help для списка команд\n"
        f"🎮 Используйте /role чтобы узнать свою роль\n"
        f"📊 Используйте /stats для просмотра статистики"
    )
    
    await message.answer(start_text)

# РОЛЕВЫЕ КОМАНДЫ
@dp.message(Command("start_rp"))
async def start_roleplay_with_mode(message: types.Message, command: CommandObject):
    logger.info(f"🎭 Команда /start_rp от {message.from_user.id}")
    
    if message.chat.type == "private":
        await message.answer("❌ Ролевые нельзя запускать в ЛС! Добавьте бота в группу.")
        return
    
    if not is_moderator(message.from_user.id):
        await message.answer("❌ Только модераторы могут запускать ролевые!")
        return
    
    chat_id = message.chat.id
    
    existing_session_id, existing_session = roleplay_manager.get_session_by_chat(chat_id)
    if existing_session:
        await message.answer("❌ В этом чате уже есть активная ролевая! Сначала завершите её с помощью /stop_rp")
        return
    
    mode = command.args or "free"
    
    if mode not in ROLEPLAY_MODES:
        modes_list = "\n".join([f"`{mode_id}` - {data['name']}" for mode_id, data in ROLEPLAY_MODES.items()])
        await message.answer(
            f"❌ Неизвестный режим! Доступные режимы:\n{modes_list}\n\n"
            f"Пример: `/start_rp battle`"
        )
        return
    
    theme = ROLEPLAY_MODES[mode]["name"]
    session_id = roleplay_manager.create_session(message.from_user.id, chat_id, theme, mode)
    
    if not session_id:
        await message.answer("❌ Ошибка при создании сессии!")
        return
    
    creator_character = get_character_for_user(
        message.from_user.id,
        message.from_user.username, 
        message.from_user.first_name
    ) or "Пико Пикович"
    
    success, message_text = roleplay_manager.add_player(
        session_id,
        message.from_user.id,
        creator_character,
        message.from_user.username,
        message.from_user.first_name,
        message.from_user.last_name
    )
    
    if not success:
        await message.answer(f"❌ Ошибка: {message_text}")
        return
    
    session = roleplay_manager.get_session(session_id)
    
    start_message = await message.answer(
        f"🎭 **РОЛЕВАЯ НАЧИНАЕТСЯ!**\n\n"
        f"📝 **Режим:** {theme}\n"
        f"⏰ **На присоединение:** 1 минута\n"
        f"👥 **Система:** СВОБОДНЫЙ ВЫБОР РОЛЕЙ\n\n"
        f"**🎯 Выберите роль из списка ниже:**",
        reply_markup=create_join_keyboard(session)
    )
    
    session["pinned_message_id"] = start_message.message_id
    
    try:
        if message.chat.type != "private":
            await bot.pin_chat_message(chat_id, start_message.message_id)
    except Exception as e:
        logger.warning(f"Не удалось закрепить сообщение: {e}")
    
    asyncio.create_task(wait_for_players(session_id, chat_id))
    await message.answer(f"✅ **Ролевая создана!** Вы добавлены как **{creator_character}**")

@dp.message(Command("force_start"))
async def force_start_cmd(message: types.Message):
    """Принудительно начать ролевую не дожидаясь минуты"""
    logger.info(f"⚡ Команда /force_start от {message.from_user.id}")
    
    if not is_moderator(message.from_user.id):
        await message.answer("❌ Только модераторы могут использовать принудительный старт!")
        return
    
    chat_id = message.chat.id
    
    session_id, session = roleplay_manager.get_session_by_chat(chat_id)
    
    if not session or session["status"] != "waiting":
        await message.answer("❌ Нет активных ролевых в режиме ожидания!")
        return
    
    success, initial_scene = roleplay_manager.force_start_session(session_id)
    
    if success:
        players_list = "\n".join([f"• {data['character']} 👤" for data in session["players"].values()])
        
        await message.answer(
            f"⚡ **РОЛЕВАЯ ЗАПУЩЕНА ПРИНУДИТЕЛЬНО!**\n\n"
            f"👥 **Участники:**\n{players_list}\n\n"
            f"🎭 **НАЧАЛО ИСТОРИИ:**\n{initial_scene}\n\n"
            f"💬 **Пишите сообщения от имени своих персонажей!**\n"
            f"🎬 **Когда история завершится, используйте /stop_rp**"
        )
        
        # Открепляем сообщение с выбором ролей
        try:
            if session.get("pinned_message_id"):
                await bot.unpin_chat_message(chat_id, session["pinned_message_id"])
        except Exception as e:
            logger.warning(f"Не удалось открепить сообщение: {e}")
            
    else:
        await message.answer(f"❌ Ошибка: {initial_scene}")

@dp.message(Command("stop_rp"))
async def stop_roleplay(message: types.Message):
    """Завершить ролевую и показать статистику"""
    logger.info(f"🛑 Команда /stop_rp от {message.from_user.id}")
    
    if not is_moderator(message.from_user.id):
        await message.answer("❌ Только модераторы могут останавливать ролевые!")
        return
    
    chat_id = message.chat.id
    
    session_id, session = roleplay_manager.get_session_by_chat(chat_id)
    
    if session:
        success, stats = roleplay_manager.end_session(session_id)
        
        if success:
            players_list = "\n".join([f"• {data['character']}" for data in session["players"].values()])
            
            top_players_text = ""
            if stats["top_players"]:
                top_players_text = "\n🏆 **Топ активных игроков:**\n"
                for i, player in enumerate(stats["top_players"], 1):
                    medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉"
                    top_players_text += f"{medal} {player['character']} ({player['first_name']}) - {player['messages_count']} сообщ.\n"
            
            await message.answer(
                f"🎬 **РОЛЕВАЯ ЗАВЕРШЕНА!** 🎬\n\n"
                f"👥 **Участники:**\n{players_list}\n\n"
                f"📊 **Статистика сессии:**\n"
                f"• 👤 Игроков: {stats['total_players']}\n"
                f"• 💬 Сообщений: {stats['total_messages']}\n"
                f"• ⏱️ Длительность: {stats['session_duration'].seconds // 60} мин.\n"
                f"{top_players_text}\n"
                f"🙏 **ОГРОМНОЕ СПАСИБО ВСЕМ ЗА УЧАСТИЕ!**\n"
                f"💫 **Вы были прекрасны в своих ролях!**\n\n"
                f"До следующих приключений! 👋"
            )
            
            try:
                if message.chat.type != "private" and session.get("pinned_message_id"):
                    await bot.unpin_chat_message(chat_id, session["pinned_message_id"])
            except Exception as e:
                logger.warning(f"Не удалось открепить сообщение: {e}")
                
        else:
            await message.answer("❌ Ошибка при завершении ролевой!")
    else:
        await message.answer("❌ Нет активных ролевых для остановки!")

# CALLBACK HANDLERS
@dp.callback_query(F.data.startswith("join_"))
async def join_roleplay(callback: types.CallbackQuery):
    character = callback.data.replace("join_", "")
    
    active_session_id, active_session = roleplay_manager.get_session_by_chat(callback.message.chat.id)
    
    if not active_session:
        await callback.answer("❌ Нет активных ролевых для присоединения!")
        return
    
    session_id, session = active_session_id, active_session
    
    can_join, reason = can_user_join_with_character(session, callback.from_user.id, character)
    if not can_join:
        await callback.answer(f"❌ {reason}")
        return
    
    success, message_text = roleplay_manager.add_player(
        session_id, 
        callback.from_user.id,
        character,
        callback.from_user.username,
        callback.from_user.first_name,
        callback.from_user.last_name
    )
    
    if success:
        await callback.answer(f"✅ {message_text}")
        
        players_list = "\n".join([
            f"• {data['character']} 👤" 
            for data in session["players"].values()
        ]) or "• Пока никто не присоединился"
        
        time_left = ROLEPLAY_SETTINGS["max_wait_time"] - (datetime.now() - datetime.fromisoformat(session["created_at"])).seconds
        time_left = max(0, time_left)
        
        await callback.message.edit_text(
            f"🎭 **РОЛЕВАЯ НАЧИНАЕТСЯ!**\n\n"
            f"📝 **Режим:** {session['theme']}\n"
            f"⏰ **Осталось времени:** {time_left} сек\n"
            f"👥 **Участники:**\n{players_list}\n\n"
            f"**🎯 Выберите роль из списка ниже:**",
            reply_markup=create_join_keyboard(session)
        )
    else:
        await callback.answer(f"❌ {message_text}")

@dp.callback_query(F.data == "role_taken")
async def handle_role_taken(callback: types.CallbackQuery):
    await callback.answer("❌ Эта роль уже занята!")

@dp.callback_query(F.data == "all_roles_taken")
async def handle_all_roles_taken(callback: types.CallbackQuery):
    await callback.answer("❌ Все роли заняты!")

@dp.message()
async def handle_all_messages(message: types.Message):
    if message.text and message.text.startswith('/'):
        return
    
    chat_id = message.chat.id
    user_id = message.from_user.id
    
    active_session_id, active_session = roleplay_manager.get_session_by_chat(chat_id)
    
    if not active_session or active_session["status"] != "active":
        return
    
    session_id, session = active_session_id, active_session
    
    if user_id in session["players"]:
        character = session["players"][user_id]["character"]
        response_text = message.text or (message.caption if message.caption else "")
        
        if response_text:
            logger.info(f"💬 {character}: {response_text}")
            
            session["players"][user_id]["messages_count"] = session["players"][user_id].get("messages_count", 0) + 1
            
            db_manager.update_user_stats(user_id, responses_delta=1, messages_delta=1)
            
            new_achievements = db_manager.check_achievements(user_id)
            if new_achievements:
                for achievement_id in new_achievements:
                    achievement = ACHIEVEMENTS[achievement_id]
                    await message.answer(
                        f"🎉 **НОВОЕ ДОСТИЖЕНИЕ!** 🎉\n\n"
                        f"🏆 **{achievement['name']}**\n"
                        f"📖 {achievement['desc']}\n\n"
                        f"✨ Поздравляем, {message.from_user.first_name}!"
                    )

async def wait_for_players(session_id, chat_id):
    await asyncio.sleep(ROLEPLAY_SETTINGS["max_wait_time"])
    
    session = roleplay_manager.get_session(session_id)
    if session and session["status"] == "waiting":
        success, initial_scene = await roleplay_manager.start_session(session_id)
        
        if success:
            players_list = "\n".join([f"• {data['character']} 👤" for data in session["players"].values()])
            
            await bot.send_message(
                chat_id,
                f"🎬 **РОЛЕВАЯ НАЧАЛАСЬ!** 🎬\n\n"
                f"👥 **Участники:**\n{players_list}\n\n"
                f"🎭 **НАЧАЛО ИСТОРИИ:**\n{initial_scene}\n\n"
                f"💬 **Теперь просто пишите сообщения от имени своих персонажей!**\n"
                f"🎬 **Когда история завершится, модератор использует /stop_rp**"
            )
            
            # Открепляем сообщение с выбором ролей
            try:
                if session.get("pinned_message_id"):
                    await bot.unpin_chat_message(chat_id, session["pinned_message_id"])
            except Exception as e:
                logger.warning(f"Не удалось открепить сообщение: {e}")
                
        else:
            await bot.send_message(chat_id, f"❌ {initial_scene}")
            roleplay_manager.end_session(session_id)

def check_database():
    import os
    if os.path.exists('roleplay_bot.db'):
        print("✅ База данных roleplay_bot.db существует!")
        conn = sqlite3.connect('roleplay_bot.db')
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        print(f"✅ Создано таблиц: {len(tables)}")
        for table in tables:
            print(f"   - {table[0]}")
        conn.close()
    else:
        print("❌ База данных еще не создана. Запустите бота один раз!")

check_database()

async def main():
    logger.info("🎭 Бот запускается...")
    logger.info("💾 Инициализируем базу данных...")
    
    # Устанавливаем команды меню
    await set_bot_commands()
    
    db_manager.add_user(ADMIN_ID, "PicoFromTheVoid", "Главный", "Администратор")
    
    db_moderators = db_manager.get_moderators()
    for mod in db_moderators:
        MODERATORS[mod['user_id']] = f"{mod['first_name']} (@{mod['username']})"
    
    logger.info("✅ Бот готов к работе!")
    logger.info(f"👑 Главный администратор: {ADMIN_ID}")
    logger.info(f"🔧 Модераторов: {len(MODERATORS)}")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())