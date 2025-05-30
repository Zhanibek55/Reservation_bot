# Бот для бронирования бильярдных столов

Телеграм-бот для управления бронированием столов в бильярдном клубе.

## Функциональность

- Визуализация расположения бильярдных столов
- Отображение доступности столов
- Бронирование столов на временные слоты
- Уведомления администратора через WhatsApp
- Административная панель для управления режимом работы

## Установка

1. Клонируйте репозиторий:
```bash
git clone <repository-url>
cd billiards-booking-bot
```

2. Создайте виртуальное окружение и активируйте его:
```bash
python -m venv venv
source venv/bin/activate  # для Linux/Mac
venv\Scripts\activate     # для Windows
```

3. Установите зависимости:
```bash
pip install -r requirements.txt
```

4. Создайте файл `.env` и заполните его следующими данными:
```
BOT_TOKEN=your_telegram_bot_token_here
ADMIN_ID=your_telegram_admin_id_here
ADMIN_WHATSAPP=your_whatsapp_number_here
```

## Запуск

1. Активируйте виртуальное окружение (если еще не активировано):
```bash
source venv/bin/activate  # для Linux/Mac
venv\Scripts\activate     # для Windows
```

2. Запустите бота:
```bash
python bot.py
```

## Использование

1. Найдите бота в Telegram по его username
2. Отправьте команду `/start`
3. Следуйте инструкциям бота для регистрации и бронирования столов

## Административные функции

Для доступа к административной панели:
1. Убедитесь, что ваш Telegram ID указан в переменной `ADMIN_ID`
2. Отправьте команду `/start`
3. В главном меню появится кнопка "Админ панель"

В административной панели вы можете:
- Устанавливать режим работы клуба
- Настраивать длительность временных слотов
- Управлять доступностью столов
- Подтверждать или отклонять заявки на бронирование 