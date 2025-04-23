import os
import sys
import subprocess

def install_dependencies():
    """Устанавливает необходимые зависимости для работы на PythonAnywhere"""
    print("Установка зависимостей...")
    
    # Основные зависимости
    subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
    
    # Дополнительные зависимости для PythonAnywhere
    subprocess.run([sys.executable, "-m", "pip", "install", "aiosqlite"])
    
    print("Зависимости установлены успешно.")

def check_environment():
    """Проверяет окружение и выводит информацию о нем"""
    print(f"Python версия: {sys.version}")
    print(f"Текущая директория: {os.getcwd()}")
    
    # Проверка наличия .env файла
    if os.path.exists(".env"):
        print("Файл .env найден.")
    else:
        print("ВНИМАНИЕ: Файл .env не найден!")
    
    # Проверка наличия базы данных
    if os.path.exists("database.db"):
        print("База данных найдена.")
    else:
        print("База данных не найдена. Она будет создана при первом запуске бота.")
    
    print("\nПроверка импорта модулей:")
    try:
        import telegram
        print(f"python-telegram-bot: OK (версия {telegram.__version__})")
    except ImportError:
        print("python-telegram-bot: НЕ УСТАНОВЛЕН")
    
    try:
        import sqlalchemy
        print(f"SQLAlchemy: OK (версия {sqlalchemy.__version__})")
    except ImportError:
        print("SQLAlchemy: НЕ УСТАНОВЛЕН")
    
    try:
        import aiosqlite
        print(f"aiosqlite: OK (версия {aiosqlite.__version__})")
    except ImportError:
        print("aiosqlite: НЕ УСТАНОВЛЕН")
    
    try:
        from PIL import Image
        print(f"Pillow: OK (версия {Image.__version__})")
    except ImportError:
        print("Pillow: НЕ УСТАНОВЛЕН")

def create_run_script():
    """Создает скрипт для запуска бота на PythonAnywhere"""
    script_content = """#!/bin/bash
cd ~/Reservation_bot
source venv/bin/activate
python bot.py
"""
    with open("run_bot.sh", "w") as f:
        f.write(script_content)
    
    # Делаем скрипт исполняемым
    os.chmod("run_bot.sh", 0o755)
    print("Скрипт запуска run_bot.sh создан.")

if __name__ == "__main__":
    print("=== Настройка окружения для PythonAnywhere ===")
    check_environment()
    install_dependencies()
    create_run_script()
    print("\nНастройка завершена. Теперь вы можете запустить бота командой: ./run_bot.sh")
