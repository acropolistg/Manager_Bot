from flask import Flask
import threading
import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime, timedelta
import json
import os
from dotenv import load_dotenv  # Импортируем библиотеку для работы с .env

# Загружаем переменные окружения
load_dotenv()

# Получаем данные из .env
API_TOKEN = os.getenv("API_TOKEN")
GROUP_ID = int(os.getenv("GROUP_ID"))
PAYMENT_ADDRESS = os.getenv("PAYMENT_ADDRESS")
OWNER_ID = int(os.getenv("OWNER_ID"))
INVITE_LINK = os.getenv("INVITE_LINK")
SUPPORT_USERNAME = os.getenv("SUPPORT_USERNAME")

bot = telebot.TeleBot(API_TOKEN)

# Хранилище данных
pending_payments = {}  # Ожидающие оплаты: user_id -> {"days": срок, "amount": сумма}
users = {}  # Активные пользователи: user_id -> expiration_date

# Путь к файлу для хранения данных пользователей
USERS_FILE = 'users_data.json'

# Загрузка данных пользователей из файла
def load_users():
    try:
        with open(USERS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            for user_id, user_data in data.items():
                if 'expiration_date' in user_data and user_data['expiration_date']:
                    user_data['expiration_date'] = datetime.fromisoformat(user_data['expiration_date'])
            return data
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError as e:
        print(f"Ошибка в формате JSON в файле: {e}")
        return {}

# Сохранение данных пользователей в файл
def save_users():
    try:
        with open(USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump({user_id: {**data, 'expiration_date': data['expiration_date'].isoformat() if data['expiration_date'] else None}
                       for user_id, data in users.items()},
                      f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"Ошибка при сохранении данных в файл: {e}")

# Главный экран (меню)
def main_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(KeyboardButton("Купить подписку"))
    markup.add(KeyboardButton("Поддержка"))
    return markup

# Обработка команды /start
@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "Добро пожаловать! Выберите действие:", reply_markup=main_menu())

# Покупка подписки
@bot.message_handler(func=lambda message: message.text == "Купить подписку")
def choose_subscription(message):
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("7 дней — 25$", callback_data="buy_7"),
        InlineKeyboardButton("30 дней — 100$", callback_data="buy_30"),
        InlineKeyboardButton("2 месяца — 165$", callback_data="buy_2_months"),
        InlineKeyboardButton("Навсегда — 400$", callback_data="buy_forever")
    )
    bot.send_message(message.chat.id, "Выберите срок подписки (оплата TRC-20 USDT):", reply_markup=markup)

# Обработка выбора подписки
@bot.callback_query_handler(func=lambda call: call.data.startswith("buy_"))
def handle_subscription_choice(call):
    days = None
    amount = None

    if call.data == "buy_7":
        days = 7
        amount = 25
    elif call.data == "buy_30":
        days = 30
        amount = 100
    elif call.data == "buy_2_months":
        days = 60
        amount = 165
    elif call.data == "buy_forever":
        days = None
        amount = 400

    pending_payments[call.from_user.id] = {"days": days, "amount": amount, "forever": days is None}
    
    bot.send_message(
        call.message.chat.id,
        f"Вы выбрали подписку на {days if days else 'навсегда'} за {amount} $.\n`{PAYMENT_ADDRESS}`\n\n"
        "После оплаты отправьте скриншот подтверждения оплаты.",
        parse_mode="Markdown"
    )

# Подтверждение оплаты скриншотом
@bot.message_handler(content_types=['photo'])
def confirm_payment(message):
    user_id = message.from_user.id
    if user_id not in pending_payments:
        bot.reply_to(message, "Вы ещё не выбрали подписку.")
        return

    payment_info = pending_payments[user_id]
    days = payment_info["days"]
    forever = payment_info.get("forever", False)

    bot.reply_to(
        message,
        "Спасибо за подтверждение! Мы проверим ваш платёж. После проверки вы получите доступ в группу."
    )

    # Пересылаем скриншот владельцу бота
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("Подтвердить оплату", callback_data=f"approve_{user_id}"))

    bot.forward_message(OWNER_ID, message.chat.id, message.message_id)
    bot.send_message(
        OWNER_ID,
        f"Пользователь {message.from_user.username} ({user_id}) отправил скриншот оплаты {payment_info['amount']} $ за "
        f"{days if not forever else 'навсегда'} подписки.",
        reply_markup=markup
    )

# Поддержка
@bot.message_handler(func=lambda message: message.text == "Поддержка")
def support(message):
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("Написать владельцу", url=f"https://t.me/{SUPPORT_USERNAME[1:]}"))
    bot.reply_to(message, "Нажмите кнопку ниже, чтобы связаться с поддержкой:", reply_markup=markup)

# Подтверждение оплаты владельцем
@bot.callback_query_handler(func=lambda call: call.data.startswith("approve_"))
def approve_payment(call):
    try:
        if call.from_user.id != OWNER_ID:
            bot.answer_callback_query(call.id, "Только владелец может подтвердить оплату.")
            return

        user_id = int(call.data.split("_")[1])
        if user_id not in pending_payments:
            bot.send_message(OWNER_ID, "Пользователь не найден среди ожидающих оплат.")
            return

        payment_info = pending_payments.pop(user_id)
        days = payment_info["days"]
        forever = payment_info.get("forever", False)
        
        expiration_date = None if forever else datetime.now() + timedelta(days=days)
        users[user_id] = {"expiration_date": expiration_date, "notifications_sent": {"expired": False, "soon": False, "hour": False}, "forever": forever}

        bot.send_message(
            user_id,
            f"Оплата подтверждена! Ваша подписка активна {'навсегда' if forever else 'до ' + expiration_date.strftime('%Y-%m-%d %H:%M:%S') }.\n\nДобро пожаловать в группу!")
        bot.send_message(user_id, f"Спасибо за покупку! Присоединяйтесь к нашей группе: {INVITE_LINK}")

        save_users()

    except Exception as e:
        bot.send_message(OWNER_ID, f"Ошибка: {e}")

# Установим порт для прослушивания
port = int(os.getenv("PORT", 8080))

# Запуск бота в потоке
if __name__ == '__main__':
    users = load_users()  # Загружаем данные пользователей при старте
    bot.polling(none_stop=True)

    # Если нужно, запускайте сервер (для Fly.io)
    # app.run(host="0.0.0.0", port=port)































