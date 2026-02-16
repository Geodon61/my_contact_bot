#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Contact Bot - для подруги
Подруга получает сообщения, админ видит всё
"""

import logging
import sqlite3
import time
from datetime import datetime
from typing import Optional, Dict, List
from telebot import TeleBot, types
import telebot

# ========== НАСТРОЙКИ ==========
BOT_TOKEN = "8491886115:AAHZrWx-0T5hvZlfibyhG7ITQUOxExMzucs"  # Получи у @BotFather
ADMIN_ID = 5171909366  # ТЫ (видишь всё)
FRIEND_ID = 6665694522  # 👈 СЮДА ВСТАВЬ ID ПОДРУГИ (она будет основным пользователем)

# ========== ИНИЦИАЛИЗАЦИЯ ==========
bot = TeleBot(BOT_TOKEN)
bot.set_my_commands([
    telebot.types.BotCommand("/start", "Начать общение"),
    telebot.types.BotCommand("/help", "Помощь"),
])

# ========== БАЗА ДАННЫХ ==========
conn = sqlite3.connect('users.db', check_same_thread=False)
cursor = conn.cursor()

cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        last_name TEXT,
        language_code TEXT,
        first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        messages_count INTEGER DEFAULT 0
    )
''')

cursor.execute('''
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        from_user_id INTEGER,
        to_user_id INTEGER,
        message_text TEXT,
        message_date TIMESTAMP,
        direction TEXT  -- 'incoming' (от людей к подруге) или 'outgoing' (от подруги к людям)
    )
''')
conn.commit()


# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========

def update_user_info(message):
    """Обновляет информацию о пользователе в БД"""
    user = message.from_user
    cursor.execute('''
        INSERT INTO users (user_id, username, first_name, last_name, language_code, last_active)
        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(user_id) DO UPDATE SET
            username = excluded.username,
            first_name = excluded.first_name,
            last_name = excluded.last_name,
            language_code = excluded.language_code,
            last_active = CURRENT_TIMESTAMP,
            messages_count = messages_count + 1
    ''', (user.id, user.username, user.first_name, user.last_name, user.language_code))
    conn.commit()


def get_user_info(user_id: int) -> Optional[Dict]:
    """Получает информацию о пользователе из БД"""
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    row = cursor.fetchone()
    if row:
        columns = ['user_id', 'username', 'first_name', 'last_name',
                   'language_code', 'first_seen', 'last_active', 'messages_count']
        return dict(zip(columns, row))
    return None


def get_all_users() -> List[Dict]:
    """Получает список всех пользователей"""
    cursor.execute('SELECT * FROM users ORDER BY last_active DESC')
    rows = cursor.fetchall()
    columns = ['user_id', 'username', 'first_name', 'last_name',
               'language_code', 'first_seen', 'last_active', 'messages_count']
    return [dict(zip(columns, row)) for row in rows]


def format_user_info(user_info: Dict) -> str:
    """Форматирует информацию о пользователе для вывода"""
    return (
        f"👤 *Информация о пользователе*\n\n"
        f"🆔 ID: `{user_info['user_id']}`\n"
        f"📛 Имя: {user_info['first_name']} {user_info['last_name'] or ''}\n"
        f"🔰 Username: @{user_info['username'] if user_info['username'] else 'нет'}\n"
        f"🌐 Язык: {user_info['language_code'] or 'не указан'}\n"
        f"📊 Сообщений: {user_info['messages_count']}\n"
        f"🕐 Первое обращение: {user_info['first_seen']}\n"
        f"🕐 Последняя активность: {user_info['last_active']}"
    )


# ========== ОБРАБОТЧИКИ КОМАНД ==========

@bot.message_handler(commands=['start'])
def start_command(message):
    """Приветственное сообщение"""
    user = message.from_user
    update_user_info(message)

    # Если это подруга — показываем расширенное меню
    if user.id == FRIEND_ID:
        markup = types.InlineKeyboardMarkup()
        btn1 = types.InlineKeyboardButton("👤 Обо мне", callback_data=f"info_{user.id}")
        btn2 = types.InlineKeyboardButton("📊 Статистика", callback_data="friend_stats")
        markup.add(btn1, btn2)

        welcome_text = (
            f"👋 Привет, {user.first_name}!\n\n"
            f"Ты — главный пользователь этого бота. Люди будут писать тебе сюда.\n\n"
            f"📨 Все входящие сообщения будут приходить тебе.\n"
            f"💬 Чтобы ответить — просто напиши текст (бот поймёт, кому).\n"
            f"👆 Кнопки ниже — для информации."
        )

        bot.send_message(
            message.chat.id,
            welcome_text,
            parse_mode='Markdown',
            reply_markup=markup
        )

    # Если это админ
    elif user.id == ADMIN_ID:
        markup = types.InlineKeyboardMarkup()
        btn1 = types.InlineKeyboardButton("📋 Все пользователи", callback_data="admin_users")
        btn2 = types.InlineKeyboardButton("📊 Статистика", callback_data="admin_stats")
        markup.add(btn1, btn2)

        bot.send_message(
            message.chat.id,
            "👑 *Админ-панель*\n\nТы видишь все сообщения (входящие и исходящие).",
            parse_mode='Markdown',
            reply_markup=markup
        )

    # Обычный пользователь
    else:
        markup = types.InlineKeyboardMarkup()
        btn = types.InlineKeyboardButton("👤 Обо мне", callback_data=f"info_{user.id}")
        markup.add(btn)

        bot.send_message(
            message.chat.id,
            f"👋 Привет, {user.first_name}! Напиши сообщение — оно уйдёт получателю.",
            parse_mode='Markdown',
            reply_markup=markup
        )


# ========== ОБРАБОТКА СООБЩЕНИЙ ==========

@bot.message_handler(func=lambda m: True)
def handle_message(message):
    """Главный обработчик всех сообщений"""
    user_id = message.from_user.id
    update_user_info(message)

    # Сохраняем сообщение в БД
    cursor.execute('''
        INSERT INTO messages (from_user_id, to_user_id, message_text, message_date, direction)
        VALUES (?, ?, ?, ?, ?)
    ''', (user_id, FRIEND_ID, message.text, datetime.now(), 'unknown'))
    conn.commit()

    # --- 1. Сообщение от обычного человека (не подруга и не админ) ---
    if user_id != FRIEND_ID and user_id != ADMIN_ID:
        # Пересылаем подруге
        caption = (
            f"📨 *Новое сообщение*\n\n"
            f"👤 От: {message.from_user.first_name}\n"
            f"🔰 Username: @{message.from_user.username if message.from_user.username else 'нет'}\n"
            f"⏰ {datetime.now().strftime('%d.%m.%Y %H:%M')}"
        )

        # Кнопка для подруги — посмотреть инфо о писавшем
        markup = types.InlineKeyboardMarkup()
        info_btn = types.InlineKeyboardButton(
            "👤 Инфо",
            callback_data=f"friend_info_{user_id}"
        )
        markup.add(info_btn)

        bot.send_message(
            FRIEND_ID,
            f"{caption}\n\n_{message.text}_",
            parse_mode='Markdown',
            reply_markup=markup
        )

        # Дублируем админу
        admin_caption = (
            f"📨 [ВХОДЯЩЕЕ] От человека к @{bot.get_me().username}\n\n"
            f"👤 От: {message.from_user.first_name} (ID: {user_id})\n"
            f"💬 Текст: {message.text}"
        )
        bot.send_message(ADMIN_ID, admin_caption)

        # Подтверждение человеку
        bot.send_message(user_id, "✅ Сообщение доставлено.")

        # Обновляем направление в БД
        cursor.execute('''
            UPDATE messages SET direction = 'incoming' 
            WHERE from_user_id = ? AND to_user_id = ?
        ''', (user_id, FRIEND_ID))
        conn.commit()

    # --- 2. Сообщение от подруги (она отвечает кому-то) ---
    elif user_id == FRIEND_ID:
        # Пытаемся понять, кому она отвечает
        if message.reply_to_message:
            # Если ответила на конкретное сообщение
            replied = message.reply_to_message
            # Парсим ID из caption (если это входящее)
            import re
            match = re.search(r'ID: (\d+)', replied.caption if replied.caption else '')
            if match:
                target_id = int(match.group(1))

                # Отправляем ответ
                bot.send_message(
                    target_id,
                    f"✉️ *Ответ:*\n\n{message.text}",
                    parse_mode='Markdown'
                )

                # Дублируем админу
                bot.send_message(
                    ADMIN_ID,
                    f"📤 [ИСХОДЯЩЕЕ] Подруга ответила ID {target_id}:\n{message.text}"
                )

                # Сохраняем в БД
                cursor.execute('''
                    INSERT INTO messages (from_user_id, to_user_id, message_text, message_date, direction)
                    VALUES (?, ?, ?, ?, ?)
                ''', (FRIEND_ID, target_id, message.text, datetime.now(), 'outgoing'))
                conn.commit()

                bot.send_message(FRIEND_ID, "✅ Ответ отправлен.")
                return

        # Если не ответ, а просто текст — просим использовать reply
        bot.send_message(
            FRIEND_ID,
            "❓ Чтобы ответить человеку, используй 'ответить' (reply) на его сообщение."
        )

    # --- 3. Сообщение от админа (ты можешь писать подруге или отвечать) ---
    elif user_id == ADMIN_ID:
        bot.send_message(
            ADMIN_ID,
            "👑 Ты админ. Используй кнопки или команды."
        )


# ========== ОБРАБОТКА INLINE КНОПОК ==========

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    """Обработка нажатий на кнопки"""
    user_id = call.from_user.id
    data = call.data

    # ----- КНОПКИ ДЛЯ ПОДРУГИ -----

    if data.startswith('friend_info_'):
        if user_id != FRIEND_ID:
            bot.answer_callback_query(call.id, "❌ Это не для тебя")
            return

        target_user_id = int(data.split('_')[2])
        user_info = get_user_info(target_user_id)

        if user_info:
            text = format_user_info(user_info)
        else:
            text = "❌ Информация не найдена"

        bot.answer_callback_query(call.id, "Загружаю...")
        bot.send_message(FRIEND_ID, text, parse_mode='Markdown')

    elif data == 'friend_stats':
        if user_id != FRIEND_ID:
            bot.answer_callback_query(call.id, "❌ Не для тебя")
            return

        cursor.execute('SELECT COUNT(*) FROM messages WHERE direction = "incoming"')
        incoming = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM messages WHERE direction = "outgoing"')
        outgoing = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(DISTINCT from_user_id) FROM messages WHERE direction = "incoming"')
        unique_people = cursor.fetchone()[0]

        stats = (
            f"📊 *Твоя статистика*\n\n"
            f"📨 Получено сообщений: {incoming}\n"
            f"📤 Отправлено ответов: {outgoing}\n"
            f"👥 Людей писали: {unique_people}"
        )
        bot.send_message(FRIEND_ID, stats, parse_mode='Markdown')
        bot.answer_callback_query(call.id)

    # ----- КНОПКИ ДЛЯ АДМИНА -----

    elif data == 'admin_users':
        if user_id != ADMIN_ID:
            bot.answer_callback_query(call.id, "❌ Недостаточно прав")
            return

        users = get_all_users()
        if not users:
            bot.send_message(ADMIN_ID, "❌ Пока никто не писал.")
            return

        text = f"📋 *Все пользователи ({len(users)})*\n\n"
        for u in users[:15]:
            name = u['first_name']
            username = f"@{u['username']}" if u['username'] else 'нет username'
            text += f"▪️ {name} ({username}) — {u['messages_count']} сообщ.\n"

        if len(users) > 15:
            text += f"\n... и ещё {len(users) - 15}"

        bot.send_message(ADMIN_ID, text, parse_mode='Markdown')
        bot.answer_callback_query(call.id)

    elif data == 'admin_stats':
        if user_id != ADMIN_ID:
            bot.answer_callback_query(call.id, "❌ Недостаточно прав")
            return

        cursor.execute('SELECT COUNT(*) FROM users')
        total_users = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM messages WHERE direction = "incoming"')
        total_incoming = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM messages WHERE direction = "outgoing"')
        total_outgoing = cursor.fetchone()[0]

        stats = (
            f"📊 *ОБЩАЯ СТАТИСТИКА*\n\n"
            f"👥 Всего писали: {total_users} чел.\n"
            f"📨 Входящих подруге: {total_incoming}\n"
            f"📤 Ответов от подруги: {total_outgoing}"
        )
        bot.send_message(ADMIN_ID, stats, parse_mode='Markdown')
        bot.answer_callback_query(call.id)


# ========== ЗАПУСК ==========

if __name__ == "__main__":
    print("🤖 Contact Bot запущен...")
    print(f"👑 Админ ID: {ADMIN_ID}")
    print(f"👩 Подруга ID: {FRIEND_ID}")

    bot.remove_webhook()

    bot.infinity_polling(timeout=60, long_polling_timeout=30)
