# Инструкция по развертыванию на PythonAnywhere

Эта инструкция поможет вам загрузить проект на GitHub и настроить автоматическое обновление на PythonAnywhere.

## 1. Загрузка проекта на GitHub

### Подготовка локального репозитория

```bash
# Инициализация Git репозитория
git init
git add .
git commit -m "Первоначальная загрузка проекта"
```

### Создание репозитория на GitHub

1. Перейдите на [GitHub](https://github.com) и войдите в свой аккаунт
2. Нажмите "+" в правом верхнем углу и выберите "New repository"
3. Введите имя репозитория "Reservation_bot"
4. Оставьте репозиторий публичным или сделайте его приватным
5. Нажмите "Create repository"

### Связывание локального репозитория с GitHub

```bash
git remote add origin https://github.com/ваш_пользователь/Reservation_bot.git
git branch -M main
git push -u origin main
```

## 2. Настройка PythonAnywhere

### Создание аккаунта и веб-приложения

1. Зарегистрируйтесь на [PythonAnywhere](https://www.pythonanywhere.com/)
2. Перейдите в раздел "Web" и нажмите "Add a new web app"
3. Выберите "Manual configuration" и Python 3.10

### Клонирование репозитория

1. Откройте консоль PythonAnywhere (раздел "Consoles")
2. Выполните команды:

```bash
cd ~
git clone https://github.com/Zhanibek55/Reservation_bot.git
```

### Настройка виртуального окружения

```bash
cd ~/Reservation_bot
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Настройка переменных окружения

Создайте файл `.env` в директории проекта:

```bash
cd ~/Reservation_bot
nano .env
```

Добавьте следующие строки:
```
BOT_TOKEN=ваш_токен_бота
ADMIN_IDS=ваш_id_администратора
DATABASE_URL=sqlite:///database.db
```

### Настройка запуска бота

1. Перейдите в раздел "Tasks" на PythonAnywhere
2. Добавьте новую задачу, которая будет запускать бота при старте:

```bash
cd ~/Reservation_bot && source venv/bin/activate && python bot.py
```

3. Установите расписание "Daily" и время запуска (например, 2:00 UTC)

## 3. Настройка автоматического обновления

### Настройка веб-хука для автоматического обновления

1. В разделе "Web" на PythonAnywhere создайте новый URL-путь:
   - URL: `/update`
   - Файл: `~/Reservation_bot/update_from_github.py`

2. Настройте GitHub Webhook:
   - Перейдите в настройки вашего репозитория на GitHub
   - Выберите "Webhooks" -> "Add webhook"
   - Payload URL: `https://ваш_пользователь.pythonanywhere.com/update`
   - Content type: `application/json`
   - Выберите "Just the push event"
   - Нажмите "Add webhook"

### Ручное обновление

Вы также можете обновить бота вручную, выполнив следующие команды в консоли PythonAnywhere:

```bash
cd ~/Reservation_bot
git pull
source venv/bin/activate
pip install -r requirements.txt
```

И затем перезапустите задачу в разделе "Tasks".

## 4. Проверка работоспособности

1. Внесите небольшое изменение в код локально
2. Отправьте изменения на GitHub:
```bash
git add .
git commit -m "Тестовое изменение"
git push
```
3. Проверьте, что изменения автоматически применились на PythonAnywhere

## Полезные команды для отладки

```bash
# Просмотр логов бота
cd ~/Reservation_bot
tail -f bot.log

# Проверка статуса Git
git status

# Принудительное обновление из репозитория
git fetch --all
git reset --hard origin/main

# Перезапуск бота вручную
pkill -f "python bot.py"
cd ~/Reservation_bot && source venv/bin/activate && python bot.py
```
