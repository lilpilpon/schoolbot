import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from datetime import datetime, time, timedelta

# ------------------ НАСТРОЙКИ ------------------

TOKEN = "8638151081:AAGl5PMRR_6jCm738J7Dx4B6YE1sQuWC8Qk"

bot = Bot(token=TOKEN)
dp = Dispatcher()

# Хранилища в памяти
registered_users = set()
homeworks = {}
reminders = {}

# ------------------ КНОПКИ ------------------

main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📚 Расписание"), KeyboardButton(text="🔔 Звонки")],
        [KeyboardButton(text="⏭ Следующий урок"), KeyboardButton(text="📝 Домашка")],
        [KeyboardButton(text="🎯 Напоминания"), KeyboardButton(text="🧮 Калькулятор оценок")]
    ],
    resize_keyboard=True
)

schedule_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📅 Сегодня"), KeyboardButton(text="📆 Завтра")],
        [KeyboardButton(text="📘 Понедельник"), KeyboardButton(text="📘 Вторник")],
        [KeyboardButton(text="📘 Среда"), KeyboardButton(text="📘 Четверг")],
        [KeyboardButton(text="📘 Пятница"), KeyboardButton(text="⬅ Назад в меню")]
    ],
    resize_keyboard=True
)

homework_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="➕ Добавить ДЗ")],
        [KeyboardButton(text="📅 ДЗ на сегодня"), KeyboardButton(text="📆 ДЗ на завтра")],
        [KeyboardButton(text="📘 ДЗ по предмету")],
        [KeyboardButton(text="⬅ Назад в меню")]
    ],
    resize_keyboard=True
)

reminder_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="➕ Создать напоминание")],
        [KeyboardButton(text="📋 Мои напоминания")],
        [KeyboardButton(text="⬅ Назад в меню")]
    ],
    resize_keyboard=True
)

# ------------------ РАСПИСАНИЕ ЗВОНКОВ ------------------

LESSON_TIMES = {
    1: time(8, 30),
    2: time(9, 20),
    3: time(10, 10),
    4: time(11, 0),
    5: time(11, 50),
    6: time(12, 35),
    7: time(13, 30),
    8: time(14, 20),
}

# ------------------ ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ------------------

def get_weekday_name(offset=0):
    days = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]
    today = datetime.now().weekday()
    return days[(today + offset) % 7]

def get_current_and_next_lesson():
    now = datetime.now().time()
    times = list(LESSON_TIMES.items())
    current = None
    nxt = None
    for i, (num, t) in enumerate(times):
        if now < t:
            nxt = (num, t)
            if i > 0:
                current = times[i - 1]
            break
    return current, nxt

def get_break_end():
    now = datetime.now().time()
    times = list(LESSON_TIMES.values())
    for i in range(len(times) - 1):
        if times[i] < now < times[i + 1]:
            return times[i + 1]
    return None

# ------------------ ФОНОВЫЕ ЗАДАЧИ ------------------

async def bell_checker():
    await asyncio.sleep(3)
    last_notified = set()

    while True:
        now = datetime.now().time()

        # За 2 минуты до урока
        for lesson_number, lesson_time in LESSON_TIMES.items():
            notify_time = (datetime.combine(datetime.today(), lesson_time) - timedelta(minutes=2)).time()

            if now.hour == notify_time.hour and now.minute == notify_time.minute:
                key = f"before_{lesson_number}"
                if key not in last_notified:
                    last_notified.add(key)
                    for user in registered_users:
                        await bot.send_message(user, f"⏰ Через 2 минуты начинается {lesson_number}-й урок!")

        # Начало урока
        for lesson_number, lesson_time in LESSON_TIMES.items():
            if now.hour == lesson_time.hour and now.minute == lesson_time.minute:
                key = f"start_{lesson_number}"
                if key not in last_notified:
                    last_notified.add(key)
                    for user in registered_users:
                        await bot.send_message(user, f"📚 Начался {lesson_number}-й урок!")

        # Начало перемены
        times = list(LESSON_TIMES.values())
        for i in range(len(times) - 1):
            if now.hour == times[i].hour and now.minute == times[i].minute:
                key = f"break_start_{i}"
                if key not in last_notified:
                    last_notified.add(key)
                    for user in registered_users:
                        await bot.send_message(user, "🟡 Началась перемена!")

        # Конец перемены
        for i in range(len(times) - 1):
            next_lesson = times[i + 1]
            if now.hour == next_lesson.hour and now.minute == next_lesson.minute:
                key = f"break_end_{i}"
                if key not in last_notified:
                    last_notified.add(key)
                    for user in registered_users:
                        await bot.send_message(user, "🟢 Перемена закончилась! Сейчас начнётся урок.")

        await asyncio.sleep(20)

async def reminder_checker():
    await asyncio.sleep(3)
    while True:
        now = datetime.now()
        for user, items in list(reminders.items()):
            to_remove = []
            for r in items:
                if now >= r["dt"]:
                    await bot.send_message(user, f"🔔 Напоминание: {r['text']}")
                    to_remove.append(r)
            for r in to_remove:
                items.remove(r)
        await asyncio.sleep(20)

async def morning_schedule_sender():
    await asyncio.sleep(3)
    while True:
        now = datetime.now()
        if now.hour == 7 and now.minute == 0:
            day = get_weekday_name(0)
            if day in SCHEDULE:
                text = f"📅 Расписание на сегодня ({day.capitalize()}):\n\n"
                for num, subj in SCHEDULE[day].items():
                    text += f"{num} урок — {subj}\n"
                for user in registered_users:
                    await bot.send_message(user, text)
        await asyncio.sleep(30)

# ------------------ КОМАНДЫ ------------------

@dp.message(Command("start"))
async def start(message: types.Message):
    registered_users.add(message.from_user.id)
    await message.answer("Привет! Я учебный бот.", reply_markup=main_menu)

@dp.message(Command("help"))
async def help_cmd(message: types.Message):
    await message.answer("Используй кнопки ниже.", reply_markup=main_menu)

# ------------------ РАСПИСАНИЕ ------------------

SCHEDULE = {
    "понедельник": {1: "Разговор о важном", 2: "География", 3: "История", 4: "Родной язык", 5: "Английский", 6: "Биология/Информатика", 7: "Информатика/Алгебра"},
    "вторник": {1: "Алгебра/Информатика", 2: "Родная литература", 3: "Литература", 4: "Литература", 5: "Геометрия/Химия", 6: "Химия/Геометрия", 7: "Обществознание"},
    "среда": {1: "Физкультура", 2: "Биология/Алгебра", 3: "Алгебра/Биология", 4: "История", 5: "Обществознание", 6: "Химия/Статистика", 7: "Статистика/Информатика"},
    "четверг": {1: "Русский язык", 2: "Геометрия/Информатика", 3: "Русский язык", 4: "Физика", 5: "Химия/Геометрия", 6: "Биология/Алгебра", 7: "Английский"},
    "пятница": {1: "Литература", 2: "Биология/Геометрия", 3: "Химия/Алгебра", 4: "Английский", 5: "Физика", 6: "Обществознание"}
}

@dp.message(lambda m: m.text == "📚 Расписание")
async def schedule_menu_btn(message: types.Message):
    await message.answer("Выбери день:", reply_markup=schedule_menu)

@dp.message(lambda m: m.text in ["📅 Сегодня", "📆 Завтра", "📘 Понедельник", "📘 Вторник", "📘 Среда", "📘 Четверг", "📘 Пятница"])
async def schedule_show(message: types.Message):
    mapping = {
        "📘 Понедельник": "понедельник",
        "📘 Вторник": "вторник",
        "📘 Среда": "среда",
        "📘 Четверг": "четверг",
        "📘 Пятница": "пятница"
    }

    if message.text == "📅 Сегодня":
        day = get_weekday_name(0)
    elif message.text == "📆 Завтра":
        day = get_weekday_name(1)
    else:
        day = mapping[message.text]

    lessons = SCHEDULE.get(day, {})
    text = f"📚 Расписание на {day.capitalize()}:\n\n"
    for num, subj in lessons.items():
        text += f"{num} урок — {subj}\n"

    await message.answer(text)

# ------------------ ЗВОНКИ ------------------

@dp.message(lambda m: m.text == "🔔 Звонки")
async def bells(message: types.Message):
    text = "🔔 Расписание звонков:\n\n"
    for num, t in LESSON_TIMES.items():
        text += f"{num} урок — {t.strftime('%H:%M')}\n"
    await message.answer(text)

# ------------------ СЛЕДУЮЩИЙ УРОК ------------------

@dp.message(lambda m: m.text == "⏭ Следующий урок")
async def next_lesson(message: types.Message):
    current, nxt = get_current_and_next_lesson()
    if not nxt:
        await message.answer("Уроки закончились!")
        return

    text = ""
    if current:
        text += f"Сейчас идёт {current[0]}‑й урок.\n"
    text += f"Следующий урок: {nxt[0]}‑й в {nxt[1].strftime('%H:%M')}"

    await message.answer(text)

# ------------------ ДОМАШКА ------------------

@dp.message(lambda m: m.text == "📝 Домашка")
async def homework_menu_btn(message: types.Message):
    await message.answer("Выбери действие:", reply_markup=homework_menu)

@dp.message(lambda m: m.text == "➕ Добавить ДЗ")
async def hw_add(message: types.Message):
    await message.answer("Формат:\nпредмет; текст; дата\nНапример:\nматематика; №1‑5; 25.09")

@dp.message(lambda m: ";" in m.text and "ДЗ" not in m.text)
async def hw_add_parse(message: types.Message):
    parts = [p.strip() for p in message.text.split(";")]
    if len(parts) != 3:
        return
    subject, text_hw, date_str = parts
    user = message.from_user.id
    homeworks.setdefault(user, []).append({"subject": subject, "text": text_hw, "date": date_str})
    await message.answer("Добавлено!")

@dp.message(lambda m: m.text == "📅 ДЗ на сегодня")
async def hw_today(message: types.Message):
    user = message.from_user.id
    today = datetime.now().strftime("%d.%m")
    items = [h for h in homeworks.get(user, []) if h["date"] == today]
    if not items:
        await message.answer("На сегодня нет ДЗ.")
        return
    text = "📅 ДЗ на сегодня:\n\n"
    for h in items:
        text += f"{h['subject']}: {h['text']}\n"
    await message.answer(text)

@dp.message(lambda m: m.text == "📆 ДЗ на завтра")
async def hw_tomorrow(message: types.Message):
    user = message.from_user.id
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%d.%m")
    items = [h for h in homeworks.get(user, []) if h["date"] == tomorrow]
    if not items:
        await message.answer("На завтра нет ДЗ.")
        return
    text = "📆 ДЗ на завтра:\n\n"
    for h in items:
        text += f"{h['subject']}: {h['text']}\n"
    await message.answer(text)

# ------------------ НАПОМИНАНИЯ ------------------

@dp.message(lambda m: m.text == "🎯 Напоминания")
async def reminders_menu(message: types.Message):
    await message.answer("Выбери действие:", reply_markup=reminder_menu)

@dp.message(lambda m: m.text == "➕ Создать напоминание")
async def reminder_add(message: types.Message):
    await message.answer("Формат:\nтекст; ЧЧ:ММ")

@dp.message(lambda m: ";" in m.text and "ДЗ" not in m.text)
async def reminder_parse(message: types.Message):
    parts = [p.strip() for p in message.text.split(";")]
    if len(parts) != 2:
        return
    text_r, time_str = parts
    try:
        t = datetime.strptime(time_str, "%H:%M").time()
    except:
        return

    now = datetime.now()
    dt = datetime.combine(now.date(), t)
    if dt < now:
        dt += timedelta(days=1)

    user = message.from_user.id
    reminders.setdefault(user, []).append({"text": text_r, "time": time_str, "dt": dt})
    await message.answer("Напоминание создано!")

@dp.message(lambda m: m.text == "📋 Мои напоминания")
async def reminder_list(message: types.Message):
    user = message.from_user.id
    items = reminders.get(user, [])
    if not items:
        await message.answer("Нет напоминаний.")
        return
    text = "📋 Твои напоминания:\n\n"
    for r in items:
        text += f"{r['time']} — {r['text']}\n"
    await message.answer(text)
    
@dp.message(lambda m: m.text == "⬅ Назад в меню")
async def back_to_menu(message: types.Message):
    await message.answer("Главное меню:", reply_markup=main_menu)

# ------------------ КАЛЬКУЛЯТОР ------------------

@dp.message(lambda m: m.text == "🧮 Калькулятор оценок")
async def calc_start(message: types.Message):
    await message.answer("Введи оценки через пробел.")

@dp.message()
async def calc(message: types.Message):
    parts = message.text.split()
    if all(p in ["2", "3", "4", "5"] for p in parts):
        grades = list(map(int, parts))
        avg = sum(grades) / len(grades)
        await message.answer(f"Средний балл: {avg:.2f}")


# ------------------ ЗАПУСК ------------------

async def main():
    asyncio.create_task(bell_checker())
    asyncio.create_task(reminder_checker())
    asyncio.create_task(morning_schedule_sender())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
