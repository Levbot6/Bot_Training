import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton
import json
import os
from datetime import datetime, time, timedelta
import threading
import time as time_module

TOKEN = "8621665379:AAEK8HrDLlMv0nku0meOVp2l_GyH__yuluc"
bot = telebot.TeleBot(TOKEN)

DATA_FILE = "weekly_trainings.json"

# Дни недели (пн=0, вс=6)
DAYS = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
DAYS_EN = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# Главное меню
def main_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(KeyboardButton("➕ Добавить тренировку"))
    markup.add(KeyboardButton("📋 Моё расписание"))
    markup.add(KeyboardButton("❌ Удалить тренировку"))
    markup.add(KeyboardButton("📊 Статистика"))
    return markup


# Отмена добавления
def cancel_button():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(KeyboardButton("❌ Отмена"))
    return markup


@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id,
                     "🏋️ Еженедельное расписание тренировок\n\n"
                     "Я буду напоминать о тренировках каждую неделю в выбранный день и время.\n\n"
                     "Что нужно указать при добавлении:\n"
                     "1️⃣ День недели\n"
                     "2️⃣ Время тренировки (Новосибирск)\n"
                     "3️⃣ Когда напомнить (за сколько часов)\n"
                     "4️⃣ Название тренировки\n\n"
                     "Нажми ➕ Добавить тренировку",
                     parse_mode="Markdown", reply_markup=main_menu())


@bot.message_handler(func=lambda message: message.text == "➕ Добавить тренировку")
def add_training_start(message):
    msg = bot.send_message(message.chat.id,
                           "📅 Выбери день недели для тренировки:",
                           reply_markup=day_selection_menu(), parse_mode="Markdown")
    bot.register_next_step_handler(msg, ask_time)


def day_selection_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    buttons = [KeyboardButton(day) for day in DAYS]
    markup.add(*buttons)
    markup.add(KeyboardButton("❌ Отмена"))
    return markup


def ask_time(message):
    if message.text == "❌ Отмена":
        bot.send_message(message.chat.id, "Добавление отменено", reply_markup=main_menu())
        return

    if message.text not in DAYS:
        bot.send_message(message.chat.id, "Выбери день из кнопок", reply_markup=day_selection_menu())
        return

    user_id = str(message.chat.id)
    data = load_data()
    if user_id not in data:
        data[user_id] = []

    # Временное хранилище
    temp = {"day": message.text}
    data[user_id].append(temp)
    save_data(data)

    msg = bot.send_message(message.chat.id,
                           "⏰ Во сколько тренировка?\n\nОтправь время в формате: 19:30 или 07:00\n(Новосибирское время)",
                           parse_mode="Markdown", reply_markup=cancel_button())
    bot.register_next_step_handler(msg, ask_training_time, user_id, len(data[user_id]) - 1)


def ask_training_time(message, user_id, idx):
    if message.text == "❌ Отмена":
        cancel_add(user_id, idx)
        return

    try:
        time.strptime(message.text.strip(), "%H:%M")
        training_time = message.text.strip()
    except:
        bot.send_message(message.chat.id, "❌ Неверный формат. Используй ЧЧ:ММ (например 19:30)",
                         reply_markup=cancel_button())
        return

    data = load_data()
    data[user_id][idx]["training_time"] = training_time
    save_data(data)

    msg = bot.send_message(message.chat.id,
                           "⏰ За сколько напомнить?\n\n"
                 "Отправь число в часах (от 0 до 48):\n"
                 "• 0 — ровно в время тренировки\n"
                 "• 1 — за час\n"
                 "• 24 — за сутки и т.д.",
    parse_mode = "Markdown", reply_markup = cancel_button())
    bot.register_next_step_handler(msg, ask_reminder_hours, user_id, idx)


def ask_reminder_hours(message, user_id, idx):
    if message.text == "❌ Отмена":
        cancel_add(user_id, idx)
        return

    try:
        hours = int(message.text.strip())
        if hours < 0 or hours > 48:
            raise ValueError
    except:
        bot.send_message(message.chat.id, "❌ Введи число от 0 до 48", reply_markup=cancel_button())
        return

    data = load_data()
    data[user_id][idx]["reminder_hours"] = hours
    save_data(data)

    msg = bot.send_message(message.chat.id,
                           "🏋️ Название тренировки\n\nНапиши название (например: «Бег 5 км», «Пресс», «Тренажёрный зал»)",
                           reply_markup=cancel_button())
    bot.register_next_step_handler(msg, save_training, user_id, idx)


def save_training(message, user_id, idx):
    if message.text == "❌ Отмена":
        cancel_add(user_id, idx)
        return

    name = message.text.strip()
    if not name:
        bot.send_message(message.chat.id, "Название не может быть пустым", reply_markup=cancel_button())
        return

    data = load_data()
    data[user_id][idx]["name"] = name
    save_data(data)

    # Отправляем подтверждение
    day = data[user_id][idx]["day"]
    training_time = data[user_id][idx]["training_time"]
    reminder_hours = data[user_id][idx]["reminder_hours"]

    reminder_text = f"за {reminder_hours} ч." if reminder_hours > 0 else "ровно в время тренировки"

    bot.send_message(message.chat.id,
                     f"✅ Тренировка добавлена!\n\n"
                     f"📅 {day}\n"
                     f"⏰ Тренировка в {training_time}\n"
                     f"🔔 Напоминание {reminder_text}\n"
                     f"🏋️ {name}\n\n"
                     f"Напоминания будут приходить каждую неделю!",
                     parse_mode="Markdown", reply_markup=main_menu())

    # Запускаем планировщик для этого пользователя
    start_scheduler_for_user(user_id)


def cancel_add(user_id, idx):
    data = load_data()
    if user_id in data and idx < len(data[user_id]):
        data[user_id].pop(idx)
        save_data(data)
    bot.send_message(user_id, "❌ Добавление отменено", reply_markup=main_menu())


@bot.message_handler(func=lambda message: message.text == "📋 Моё расписание")
def show_schedule(message):
    user_id = str(message.chat.id)
    data = load_data()

    if user_id not in data or not data[user_id]:
        bot.send_message(message.chat.id, "📭 У тебя пока нет тренировок в расписании.\nНажми «➕ Добавить тренировку»")
        return

    # Группируем по дням
    schedule = {day: [] for day in DAYS}
    for t in data[user_id]:
        schedule[t["day"]].append(t)

    text = "📋 Твоё еженедельное расписание:\n\n"
    for day in DAYS:
        if schedule[day]:
            text += f"*{day}*:\n"
            for t in schedule[day]:
                reminder = f" (напом. за {t['reminder_hours']} ч)" if t['reminder_hours'] > 0 else ""
                text += f"  ⏰ {t['training_time']}{reminder} — {t['name']}\n"
            text += "\n"

    if len(text) > 4000:
        text = text[:4000] + "..."

    bot.send_message(message.chat.id, text, parse_mode="Markdown")


@bot.message_handler(func=lambda message: message.text == "❌ Удалить тренировку")
def delete_training_start(message):
    user_id = str(message.chat.id)
    data = load_data()

    if user_id not in data or not data[user_id]:
        bot.send_message(message.chat.id, "Нет тренировок для удаления")
        return

    text = "🗑 Какую тренировку удалить?\n\n"
    for i, t in enumerate(data[user_id], 1):
        text += f"{i}. {t['day']} {t['training_time']} — {t['name']}\n"

    msg = bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=cancel_button())
    bot.register_next_step_handler(msg, delete_training_by_number, user_id)



def delete_training_by_number(message, user_id):
    if message.text == "❌ Отмена":
        bot.send_message(message.chat.id, "Удаление отменено", reply_markup=main_menu())
        return

    try:
        num = int(message.text.strip()) - 1
        data = load_data()
        if 0 <= num < len(data[user_id]):
            deleted = data[user_id].pop(num)
            save_data(data)
            bot.send_message(message.chat.id,
                             f"✅ Удалено: {deleted['day']} {deleted['training_time']} — {deleted['name']}",
                             reply_markup=main_menu())
        else:
            bot.send_message(message.chat.id, "❌ Неверный номер", reply_markup=main_menu())
    except:
        bot.send_message(message.chat.id, "❌ Напиши число", reply_markup=main_menu())


@bot.message_handler(func=lambda message: message.text == "📊 Статистика")
def show_stats(message):
    user_id = str(message.chat.id)
    data = load_data()

    if user_id not in data:
        count = 0
    else:
        count = len(data[user_id])

    bot.send_message(message.chat.id,
                     f"📊 Твоя статистика\n\n"
                     f"🏋️ Всего тренировок в расписании: {count}\n"
                     f"📅 Напоминания приходят каждую неделю\n\n"
                     f"Совет: не забывай обновлять расписание при изменении графика!",
                     parse_mode="Markdown")


# ========== ПЛАНИРОВЩИК НАПОМИНАНИЙ ==========
schedulers = {}


def start_scheduler_for_user(user_id):
    """Запускает поток с напоминаниями для пользователя"""
    if user_id in schedulers and schedulers[user_id].is_alive():
        return

    def scheduler_loop():
        while True:
            try:
                now = datetime.now()
                data = load_data()

                if user_id in data and data[user_id]:
                    for training in data[user_id]:
                        # Определяем день недели тренировки (0-6, пн=0)
                        target_day_index = DAYS.index(training["day"])
                        training_time = datetime.strptime(training["training_time"], "%H:%M").time()
                        reminder_hours = training["reminder_hours"]

                        # Вычисляем время напоминания
                        reminder_time = (datetime.combine(now.date(), training_time) - timedelta(hours=reminder_hours))

                        # Проверяем, нужно ли отправить напоминание сейчас
                        # Сравниваем с точностью до минуты
                        now_rounded = now.replace(second=0, microsecond=0)
                        reminder_rounded = reminder_time.replace(second=0, microsecond=0)

                        if now_rounded == reminder_rounded and now.weekday() == target_day_index:
                            reminder_text = f"🔔 Напоминание!\n\n🏋️ Сегодня {training['day']} в {training['training_time']} тренировка:\n*{training['name']}*"
                            if reminder_hours > 0:
                                reminder_text = f"🔔 Напоминание за {reminder_hours} ч до тренировки!\n\n🏋️ Сегодня {training['day']} в {training['training_time']}:\n*{training['name']}*"
                            else:
                                reminder_text = f"🔔 Время тренировки!\n\n🏋️ {training['day']} {training['training_time']}:\n*{training['name']}*"

                            try:
                                bot.send_message(user_id, reminder_text, parse_mode="Markdown")
                            except:
                                pass

                time_module.sleep(60)  # Проверяем каждую минуту
            except Exception as e:
                print(f"Ошибка в планировщике для {user_id}: {e}")
                time_module.sleep(60)

    thread = threading.Thread(target=scheduler_loop, daemon=True)
    thread.start()
    schedulers[user_id] = thread



def start_all_schedulers():
    data = load_data()
    for user_id in data.keys():
        if data[user_id]:
            start_scheduler_for_user(user_id)


print("🤖 Бот с еженедельным расписанием запущен...")
start_all_schedulers()
bot.infinity_polling()
