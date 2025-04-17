from dotenv import load_dotenv
import os

print("Начинаю загрузку переменных окружения...")

try:
    load_dotenv()
    print("Файл .env успешно загружен")
except Exception as e:
    print(f"Ошибка при загрузке .env файла: {e}")
    pass  # Если .env файл отсутствует, продолжаем работу

# Telegram Bot Token
BOT_TOKEN = os.getenv('BOT_TOKEN')
print(f"Загруженный BOT_TOKEN: {BOT_TOKEN}")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не установлен в переменных окружения")

# База данных
DATABASE_URL = "sqlite:///billiards.db"

# Настройки клуба по умолчанию
DEFAULT_CLUB_SETTINGS = {
    "opening_time": "15:00",
    "closing_time": "21:00",
    "slot_duration": 120,  # в минутах
    "total_tables": 9
}

# Админские настройки
ADMIN_IDS = os.getenv('ADMIN_IDS', '').split(',')  # Список ID администраторов
print(f"Загруженные ADMIN_IDS: {ADMIN_IDS}")

if not ADMIN_IDS or not ADMIN_IDS[0]:
    raise ValueError("ADMIN_IDS не установлен в переменных окружения")

# Преобразуем строковые ID в целые числа
ADMIN_IDS = [int(admin_id.strip()) for admin_id in ADMIN_IDS if admin_id.strip()]

# Настройки расположения столов
TABLE_LAYOUT = [
    {"number": 1, "x": 230, "y": 50, "width": 160, "height": 80},
    {"number": 2, "x": 430, "y": 50, "width": 160, "height": 80},
    {"number": 3, "x": 630, "y": 50, "width": 160, "height": 80},
    {"number": 4, "x": 330, "y": 200, "width": 160, "height": 80},
    {"number": 5, "x": 530, "y": 200, "width": 160, "height": 80},
    {"number": 6, "x": 330, "y": 350, "width": 160, "height": 80},
    {"number": 7, "x": 530, "y": 350, "width": 160, "height": 80},
    {"number": 8, "x": 80, "y": 400, "width": 80, "height": 160},
    {"number": 9, "x": 80, "y": 100, "width": 80, "height": 160}
] 