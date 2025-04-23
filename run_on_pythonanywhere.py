#!/usr/bin/env python
"""
Скрипт для запуска бота на PythonAnywhere
Этот скрипт заменяет импорт db.py на db_pythonanywhere.py для решения проблемы с асинхронным SQLite
"""
import os
import sys
import subprocess
import shutil

def modify_bot_file():
    """Модифицирует bot.py для работы на PythonAnywhere"""
    print("Модификация bot.py для PythonAnywhere...")
    
    # Создаем резервную копию оригинального файла
    shutil.copy("bot.py", "bot.py.backup")
    
    with open("bot.py", "r", encoding="utf-8") as f:
        content = f.read()
    
    # Заменяем импорт db на db_pythonanywhere
    modified_content = content.replace(
        "from db import async_session, User, Table, Reservation, ClubSettings, init_db",
        "from db_pythonanywhere import async_session, User, Table, Reservation, ClubSettings, init_db"
    )
    
    with open("bot.py", "w", encoding="utf-8") as f:
        f.write(modified_content)
    
    print("Файл bot.py успешно модифицирован.")

def setup_environment():
    """Настраивает окружение для запуска бота на PythonAnywhere"""
    print("Настройка окружения...")
    
    # Устанавливаем переменную окружения для определения PythonAnywhere
    os.environ["PYTHONANYWHERE_DOMAIN"] = "pythonanywhere.com"
    
    # Проверяем наличие .env файла
    if not os.path.exists(".env"):
        print("Создание .env файла...")
        with open(".env", "w", encoding="utf-8") as f:
            f.write("BOT_TOKEN=7826466048:AAG4j3v-18BbuIHd14C5KGLFg2YqrFTuzUg\n")
            f.write("ADMIN_IDS=639199607\n")
            f.write("DATABASE_URL=sqlite:///database.db\n")
    
    print("Окружение настроено.")

def run_bot():
    """Запускает бота"""
    print("Запуск бота...")
    
    # Запускаем бота в фоновом режиме
    cmd = [sys.executable, "bot.py"]
    process = subprocess.Popen(cmd)
    
    print(f"Бот запущен с PID: {process.pid}")
    print("Для остановки бота используйте: pkill -f 'python bot.py'")
    
    return process

if __name__ == "__main__":
    print("=== Настройка и запуск бота на PythonAnywhere ===")
    setup_environment()
    modify_bot_file()
    
    # Запускаем бота
    process = run_bot()
    
    # Ждем завершения процесса (если нужно)
    try:
        process.wait()
    except KeyboardInterrupt:
        print("Остановка бота...")
        process.terminate()
        print("Бот остановлен.")
