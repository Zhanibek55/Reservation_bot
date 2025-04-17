import os
from dotenv import load_dotenv
from functools import lru_cache

load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')
# Безопасный способ обработки ADMIN_IDS
admin_ids_str = os.getenv('ADMIN_IDS', '')
try:
    # Пробуем обработать как список через запятую
    ADMIN_IDS = [int(x) for x in admin_ids_str.split(',') if x.strip()]
except ValueError:
    # Если возникает ошибка, используем как одно значение
    try:
        ADMIN_IDS = [int(admin_ids_str)] if admin_ids_str.strip() else []
    except ValueError:
        print("Предупреждение: Невозможно преобразовать ADMIN_IDS в числа. Используем пустой список.")
        ADMIN_IDS = []

DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite+aiosqlite:///billiards.db')

DEFAULT_CLUB_SETTINGS = {
    "opening_time": "15:00",
    "closing_time": "21:00",
    "slot_duration": 120,
    "total_tables": 9
}

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

@lru_cache(maxsize=1)
def get_club_settings():
    return DEFAULT_CLUB_SETTINGS.copy()

@lru_cache(maxsize=1)
def get_table_layout():
    return TABLE_LAYOUT.copy()
