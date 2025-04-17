#!/usr/bin/env python
import os
import sys
import subprocess
import logging
from datetime import datetime

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("update_log.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def run_command(command):
    """Выполняет команду и возвращает результат"""
    logger.info(f"Выполнение команды: {command}")
    try:
        result = subprocess.run(command, shell=True, check=True, 
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               universal_newlines=True)
        logger.info(f"Результат: {result.stdout}")
        return True, result.stdout
    except subprocess.CalledProcessError as e:
        logger.error(f"Ошибка: {e.stderr}")
        return False, e.stderr

def update_from_github():
    """Обновляет код из GitHub и перезапускает бота"""
    logger.info("Начало обновления из GitHub")
    
    # Путь к проекту (в PythonAnywhere)
    project_path = os.path.dirname(os.path.abspath(__file__))
    os.chdir(project_path)
    logger.info(f"Текущая директория: {project_path}")
    
    # Получаем текущую ветку
    success, branch = run_command("git rev-parse --abbrev-ref HEAD")
    if not success:
        logger.error("Не удалось определить текущую ветку")
        return False
    
    # Сохраняем текущие изменения, если они есть
    run_command("git stash")
    
    # Получаем последние изменения из GitHub
    success, _ = run_command("git pull origin " + branch.strip())
    if not success:
        logger.error("Не удалось получить обновления из GitHub")
        run_command("git stash pop")  # Восстанавливаем изменения
        return False
    
    # Устанавливаем новые зависимости, если они появились
    run_command("pip install -r requirements.txt")
    
    # Перезапускаем бота
    # В PythonAnywhere используем touch-reload для перезапуска
    if "PYTHONANYWHERE_DOMAIN" in os.environ:
        run_command("touch /var/www/ваш_пользователь_pythonanywhere_com_wsgi.py")
        logger.info("Бот перезапущен через touch-reload")
    else:
        # Локальный перезапуск (для тестирования)
        run_command("pkill -f 'python bot.py'")
        run_command("nohup python bot.py > bot.log 2>&1 &")
        logger.info("Бот перезапущен локально")
    
    logger.info("Обновление из GitHub завершено успешно")
    return True

if __name__ == "__main__":
    logger.info(f"Запуск обновления {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    update_from_github()
