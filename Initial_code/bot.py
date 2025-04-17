import logging
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from sqlalchemy.orm import sessionmaker
from PIL import Image, ImageDraw, ImageFont
import traceback

from config import BOT_TOKEN, ADMIN_IDS, DEFAULT_CLUB_SETTINGS, TABLE_LAYOUT
from models import engine, User, Table, Reservation, ClubSettings, Base
from utils import create_table_layout, get_time_slots, format_time_slot, is_slot_available

# Отладочный вывод
print(f"Loaded BOT_TOKEN: {BOT_TOKEN}")
print(f"Loaded ADMIN_IDS: {ADMIN_IDS}")

# Настройка логирования
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Создаем сессию базы данных
Session = sessionmaker(bind=engine)

def is_admin(user_id: int) -> bool:
    """Проверяет, является ли пользователь администратором"""
    return user_id in ADMIN_IDS

async def notify_admins(context: ContextTypes.DEFAULT_TYPE, message: str):
    """Отправляет уведомление всем администраторам"""
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(chat_id=admin_id, text=message)
        except Exception as e:
            logger.error(f"Ошибка при отправке уведомления администратору {admin_id}: {e}")

# Инициализация базы данных
def init_database():
    """Инициализация базы данных"""
    try:
        # Создаем все таблицы
        Base.metadata.create_all(engine)
        logger.info("База данных успешно инициализирована")
    except Exception as e:
        logger.error(f"Ошибка при инициализации базы данных: {e}")
        traceback.print_exc()

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    try:
        logger.info(f"Получена команда /start от пользователя {update.effective_user.id}")
        logger.info(f"Текст сообщения: {update.message.text}")
        logger.info(f"Тип чата: {update.message.chat.type}")
        
        with Session() as session:
            user = session.query(User).filter_by(telegram_id=update.effective_user.id).first()
        
            if not user:
                keyboard = [[InlineKeyboardButton("Зарегистрироваться", callback_data="register")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                message = await update.message.reply_text(
                    "Добро пожаловать в бот бронирования бильярдных столов!\n"
                    "Для начала работы необходимо зарегистрироваться.",
                    reply_markup=reply_markup
                )
                logger.info(f"Отправлено приглашение к регистрации пользователю {update.effective_user.id}")
                logger.info(f"ID отправленного сообщения: {message.message_id}")
            else:
                await show_main_menu(update, context)
                logger.info(f"Показано главное меню пользователю {update.effective_user.id}")
        
    except Exception as e:
        logger.error(f"Ошибка при обработке команды /start: {e}")
        logger.error(f"Полный traceback: {traceback.format_exc()}")
        try:
            await update.message.reply_text(
                "Произошла ошибка при обработке команды. Пожалуйста, попробуйте позже или обратитесь к администратору."
            )
        except Exception as e2:
            logger.error(f"Ошибка при отправке сообщения об ошибке: {e2}")
            logger.error(f"Полный traceback: {traceback.format_exc()}")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений"""
    try:
        logger.info(f"Получено текстовое сообщение от пользователя {update.effective_user.id}: {update.message.text}")
        logger.info(f"Текущий шаг регистрации: {context.user_data.get('registration_step')}")
        
        text = update.message.text.lower()
        
        # Если это команда /старт, обрабатываем как /start
        if text == '/старт':
            await start_command(update, context)
            return
        
        # Если идет процесс регистрации, обрабатываем как регистрацию
        if 'registration_step' in context.user_data:
            await process_registration(update, context)
            return
            
    except Exception as e:
        logger.error(f"Ошибка в handle_text: {e}")
        logger.error(f"Полный traceback: {traceback.format_exc()}")

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать главное меню"""
    keyboard = [
        [InlineKeyboardButton("Забронировать стол", callback_data="book_table")],
        [InlineKeyboardButton("Мои бронирования", callback_data="my_bookings")]
    ]
    
    session = Session()
    user = session.query(User).filter_by(telegram_id=update.effective_user.id).first()
    
    logger.info(f"Проверка админских прав для пользователя {update.effective_user.id}")
    logger.info(f"Текущий пользователь: {user.name if user else 'Не найден'}")
    logger.info(f"Админские права: {user.is_admin if user else False}")
    
    if user and user.is_admin:
        logger.info("Добавляю кнопку админ панели")
        keyboard.append([InlineKeyboardButton("Админ панель", callback_data="admin_panel")])
    
    session.close()
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        if update.callback_query:
            # Отвечаем на callback query
            await update.callback_query.answer()
            
            if hasattr(update.callback_query.message, 'photo'):
                # Если сообщение содержит фото, отправляем новое сообщение
                await update.callback_query.message.reply_text(
                    text="Главное меню:",
                    reply_markup=reply_markup
                )
                # Удаляем предыдущее сообщение с фото
                await update.callback_query.message.delete()
            else:
                # Если сообщение без фото, редактируем его
                await update.callback_query.message.edit_text(
                    text="Главное меню:",
                    reply_markup=reply_markup
                )
        else:
            await update.message.reply_text(
                "Главное меню:",
                reply_markup=reply_markup
            )
    except Exception as e:
        logger.error(f"Ошибка при показе главного меню: {e}")
        if update.callback_query:
            await update.callback_query.message.reply_text(
                "Главное меню:",
                reply_markup=reply_markup
            )

async def register_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик регистрации"""
    query = update.callback_query
    await query.answer()  # Отвечаем на callback query
    
    logger.info(f"Начало регистрации для пользователя {update.effective_user.id}")
    
    await query.message.edit_text(
        "Пожалуйста, отправьте ваше имя в следующем сообщении."
    )
    context.user_data['registration_step'] = 'name'
    logger.info(f"Установлен шаг регистрации 'name' для пользователя {update.effective_user.id}")

async def process_registration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка этапов регистрации"""
    try:
        step = context.user_data.get('registration_step')
        logger.info(f"Обработка регистрации для пользователя {update.effective_user.id}, шаг: {step}")
        logger.info(f"Текущие данные пользователя: {context.user_data}")
        logger.info(f"Текст сообщения: {update.message.text}")
        
        if step == 'name':
            name = update.message.text
            context.user_data['name'] = name
            logger.info(f"Сохранено имя: {name}")
            
            response = await update.message.reply_text(
                "Теперь отправьте ваш номер телефона в формате +7XXXXXXXXXX"
            )
            logger.info(f"Отправлен запрос номера телефона, message_id: {response.message_id}")
            
            context.user_data['registration_step'] = 'phone'
            logger.info(f"Установлен следующий шаг: phone")
        
        elif step == 'phone':
            phone = update.message.text
            # Добавляем + если его нет в начале номера
            if not phone.startswith('+'):
                phone = '+' + phone
            
            # Проверяем формат номера
            if not (phone.startswith('+7') and len(phone) == 12 and phone[1:].isdigit()):
                await update.message.reply_text(
                    "Неверный формат номера. Пожалуйста, используйте формат +7XXXXXXXXXX"
                )
                return
            
            try:
                session = Session()
                
                # Проверяем, является ли пользователь администратором
                is_admin = str(update.effective_user.id) in str(ADMIN_IDS)
                logger.info(f"Проверка на админа: user_id={update.effective_user.id}, ADMIN_IDS={ADMIN_IDS}, is_admin={is_admin}")
                
                new_user = User(
                    telegram_id=update.effective_user.id,
                    name=context.user_data['name'],
                    phone=phone,
                    is_admin=is_admin
                )
                session.add(new_user)
                session.commit()
                logger.info(f"Пользователь {update.effective_user.id} успешно добавлен в базу данных")
                logger.info(f"Админские права установлены: {is_admin}")
                
                session.close()
                
                del context.user_data['registration_step']
                await show_main_menu(update, context)
                logger.info(f"Регистрация успешно завершена для пользователя {update.effective_user.id}")
            except Exception as e:
                logger.error(f"Ошибка при сохранении пользователя в БД: {e}")
                raise
    except Exception as e:
        logger.error(f"Ошибка при регистрации: {e}")
        logger.error(f"Полный traceback: {traceback.format_exc()}")
        await update.message.reply_text(
            "Произошла ошибка при регистрации. Пожалуйста, попробуйте позже или обратитесь к администратору."
        )

async def book_table(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать доступные столы"""
    session = Session()
    
    # Получаем все столы
    tables = []
    for table_info in TABLE_LAYOUT:
        table = session.query(Table).filter_by(number=table_info['number']).first()
        if not table:
            # Если стол не существует в БД, создаем его
            table = Table(number=table_info['number'], is_available=True)
            session.add(table)
            session.commit()
        
        tables.append({
            'number': table.number,
            'is_available': table.is_available
        })
    
    # Создаем изображение с расположением столов
    image_data = create_table_layout(tables)
    
    # Создаем клавиатуру для выбора стола
    keyboard = []
    row = []
    for i, table in enumerate(tables, 1):
        if table['is_available']:
            row.append(InlineKeyboardButton(f"Стол {table['number']}", callback_data=f"select_table_{table['number']}"))
        if len(row) == 3 or i == len(tables):
            keyboard.append(row)
            row = []
    
    keyboard.append([InlineKeyboardButton("Главное меню", callback_data="main_menu")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Отправляем изображение с расположением столов
    await update.callback_query.message.reply_photo(
        photo=image_data,
        caption="Выберите стол для бронирования:\nЗеленым отмечены доступные столы\nКрасным отмечены недоступные столы",
        reply_markup=reply_markup
    )
    
    session.close()

async def select_time_slot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать доступные временные слоты для выбранного стола"""
    query = update.callback_query
    await query.answer()
    
    if query.data.startswith('select_table_'):
        table_number = int(query.data.split('_')[-1])
        context.user_data['selected_table'] = table_number
        context.user_data['booking_step'] = 'select_start'
        await show_available_slots(update, context, "Выберите начальное время:")
    elif query.data.startswith('start_slot_'):
        # Сохраняем начальное время и показываем опции
        _, table_number, timestamp = query.data.split('_')[1:]
        start_time = int(timestamp)
        context.user_data['start_time'] = start_time
        keyboard = [
            [InlineKeyboardButton("Забронировать на 2 часа", callback_data=f"confirm_slot_{table_number}_{start_time}")],
            [InlineKeyboardButton("Выбрать конечное время", callback_data=f"select_end_{table_number}_{start_time}")],
            [InlineKeyboardButton("Назад к выбору стола", callback_data="book_table")],
            [InlineKeyboardButton("Главное меню", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        start_datetime = datetime.fromtimestamp(start_time)
        end_datetime = start_datetime + timedelta(minutes=120)  # Стандартный слот 2 часа
        
        await query.message.edit_caption(
            caption=f"Выбрано время: {start_datetime.strftime('%H:%M')} - {end_datetime.strftime('%H:%M')}\n"
                   f"Стол №{table_number}\n\n"
                   "Выберите действие:",
            reply_markup=reply_markup
        )
    elif query.data.startswith('select_end_'):
        # Показываем слоты для выбора конечного времени
        _, table_number, start_timestamp = query.data.split('_')[1:]
        context.user_data['start_time'] = int(start_timestamp)
        context.user_data['booking_step'] = 'select_end'
        await show_available_slots(update, context, "Выберите конечное время:", int(start_timestamp))
    elif query.data.startswith('confirm_slot_'):
        # Подтверждаем бронирование одного слота
        _, table_number, start_timestamp = query.data.split('_')[1:]
        start_time = int(start_timestamp)
        end_time = datetime.fromtimestamp(start_time) + timedelta(minutes=120)  # Стандартный слот 2 часа
        await confirm_booking_multiple(update, context, int(table_number), start_time, int(end_time.timestamp()))
    elif query.data.startswith('end_slot_'):
        # Подтверждаем бронирование нескольких слотов
        _, table_number, end_timestamp = query.data.split('_')[1:]
        start_time = context.user_data.get('start_time')
        if start_time:
            await confirm_booking_multiple(update, context, int(table_number), start_time, int(end_timestamp))
        else:
            await query.message.reply_text("Ошибка: не найдено начальное время бронирования. Пожалуйста, начните бронирование заново.")

async def show_available_slots(update: Update, context: ContextTypes.DEFAULT_TYPE, title: str, start_from: int = None):
    """Показать доступные временные слоты"""
    table_number = context.user_data['selected_table']
    
    session = Session()
    settings = session.query(ClubSettings).first()
    
    if not settings:
        settings = ClubSettings(
            opening_time=DEFAULT_CLUB_SETTINGS['opening_time'],
            closing_time=DEFAULT_CLUB_SETTINGS['closing_time'],
            slot_duration=DEFAULT_CLUB_SETTINGS['slot_duration']
        )
        session.add(settings)
        session.commit()
    
    # Получаем временные слоты
    slots = get_time_slots(settings.opening_time, settings.closing_time, settings.slot_duration)
    
    # Получаем существующие бронирования для этого стола
    table = session.query(Table).filter_by(number=table_number).first()
    reservations = session.query(Reservation).filter(
        Reservation.table_id == table.id,
        Reservation.status != 'cancelled'
    ).all()
    
    # Создаем клавиатуру с доступными слотами
    keyboard = []
    booking_step = context.user_data.get('booking_step', 'select_start')
    
    for slot in slots:
        # Для выбора конечного времени показываем только слоты после начального
        if start_from is not None and slot[0].timestamp() <= start_from:
            continue
            
        if is_slot_available(table.id, slot[0], slot[1],
                           [{'table_id': r.table_id, 'start_time': r.start_time, 'end_time': r.end_time}
                            for r in reservations]):
            if booking_step == 'select_start':
                callback_data = f"start_slot_{table_number}_{int(slot[0].timestamp())}"
            else:
                callback_data = f"end_slot_{table_number}_{int(slot[1].timestamp())}"
                
            keyboard.append([InlineKeyboardButton(
                format_time_slot(slot),
                callback_data=callback_data
            )])
    
    keyboard.append([InlineKeyboardButton("Назад к выбору стола", callback_data="book_table")])
    keyboard.append([InlineKeyboardButton("Главное меню", callback_data="main_menu")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.callback_query.message.edit_caption(
        caption=f"{title}\nСтол №{table_number}",
        reply_markup=reply_markup
    )
    
    session.close()

async def notify_admin(context, message: str):
    """Отправляет уведомление администратору через Telegram"""
    try:
        await context.bot.send_message(chat_id=ADMIN_ID, text=message)
    except Exception as e:
        logging.error(f"Ошибка при отправке уведомления администратору: {e}")

async def confirm_booking_multiple(update: Update, context: ContextTypes.DEFAULT_TYPE, table_number: int, start_timestamp: int, end_timestamp: int):
    """Подтверждение бронирования нескольких слотов"""
    try:
        query = update.callback_query
        await query.answer()
        
        start_time = datetime.fromtimestamp(start_timestamp)
        end_time = datetime.fromtimestamp(end_timestamp)
        
        if start_time >= end_time:
            await query.message.reply_text(
                "Ошибка: время окончания должно быть позже времени начала."
            )
            return
        
        logger.info(f"Параметры бронирования: стол {table_number}, время {start_time} - {end_time}")
        
        session = Session()
        user = session.query(User).filter_by(telegram_id=update.effective_user.id).first()
        table = session.query(Table).filter_by(number=table_number).first()
        
        # Проверяем, не занят ли уже этот слот
        existing_reservation = session.query(Reservation).filter(
            Reservation.table_id == table.id,
            Reservation.status != 'cancelled',
            Reservation.start_time < end_time,
            Reservation.end_time > start_time
        ).first()
        
        if existing_reservation:
            await query.message.reply_text(
                "Извините, один или несколько выбранных слотов уже забронированы. Пожалуйста, выберите другое время."
            )
            session.close()
            return
        
        # Создаем бронирование
        reservation = Reservation(
            table_id=table.id,
            user_id=user.id,
            start_time=start_time,
            end_time=end_time,
            status='pending'
        )
        session.add(reservation)
        session.commit()
        
        # Заменяем отправку WhatsApp на Telegram
        await notify_admins(context, f"Новое бронирование!\nСтол: {table_number}\nВремя: {format_time_slot((start_time, end_time))}\nКлиент: {user.name} ({user.phone})")
        
        await query.message.edit_caption(
            caption=("Ваша заявка на бронирование отправлена администратору.\n"
                    f"Время: {start_time.strftime('%H:%M')} - {end_time.strftime('%H:%M')}\n"
                    "После подтверждения вы получите уведомление."),
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("Главное меню", callback_data="main_menu")
            ]])
        )
        
        # Очищаем данные бронирования
        if 'start_time' in context.user_data:
            del context.user_data['start_time']
        if 'booking_step' in context.user_data:
            del context.user_data['booking_step']
        
        session.close()
        
    except Exception as e:
        logger.error(f"Ошибка при подтверждении бронирования: {e}")
        logger.error(f"Полный traceback: {traceback.format_exc()}")
        await query.message.reply_text(
            "Произошла ошибка при бронировании. Пожалуйста, попробуйте позже или обратитесь к администратору."
        )

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает админ-панель"""
    user_id = update.effective_user.id
    if not is_admin(user_id):
        if update.message:
            await update.message.reply_text("У вас нет доступа к админ-панели.")
        return

    keyboard = [
        [InlineKeyboardButton("Управление столами", callback_data="manage_tables")],
        [InlineKeyboardButton("Настройки клуба", callback_data="club_settings")],
        [InlineKeyboardButton("Все бронирования", callback_data="all_bookings")],
        [InlineKeyboardButton("Назад", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        try:
            if hasattr(query.message, 'photo'):
                await query.message.edit_caption(
                    caption="Панель администратора:",
                    reply_markup=reply_markup
                )
            else:
                await query.message.edit_text(
                    text="Панель администратора:",
                    reply_markup=reply_markup
                )
        except Exception as e:
            logger.error(f"Ошибка при показе админ-панели: {e}")
            await query.message.reply_text(
                text="Панель администратора:",
                reply_markup=reply_markup
            )
    else:
        await update.message.reply_text(
            "Панель администратора:",
            reply_markup=reply_markup
        )

async def manage_tables(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Управление столами"""
    query = update.callback_query
    await query.answer()
    
    session = Session()
    tables = session.query(Table).all()
    
    keyboard = []
    for table in tables:
        status = "🟢 Доступен" if table.is_available else "🔴 Недоступен"
        keyboard.append([
            InlineKeyboardButton(
                f"Стол {table.number} - {status}",
                callback_data=f"toggle_table_{table.number}"
            )
        ])
    
    keyboard.append([InlineKeyboardButton("Назад в админ панель", callback_data="admin_panel")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message_text = "Управление столами:\nНажмите на стол, чтобы изменить его статус"
    
    try:
        if hasattr(query.message, 'photo'):
            await query.message.edit_caption(
                caption=message_text,
                reply_markup=reply_markup
            )
        else:
            await query.message.edit_text(
                text=message_text,
                reply_markup=reply_markup
            )
    except Exception as e:
        logger.error(f"Ошибка при показе управления столами: {e}")
        await query.message.reply_text(
            text=message_text,
            reply_markup=reply_markup
        )
    
    session.close()

async def toggle_table_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Изменить статус стола"""
    query = update.callback_query
    await query.answer()
    
    table_number = int(query.data.split('_')[-1])
    
    session = Session()
    table = session.query(Table).filter_by(number=table_number).first()
    if table:
        table.is_available = not table.is_available
        session.commit()
    
    await manage_tables(update, context)
    session.close()

async def club_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Настройки клуба"""
    query = update.callback_query
    await query.answer()
    
    session = Session()
    settings = session.query(ClubSettings).first()
    
    if not settings:
        settings = ClubSettings(
            opening_time=DEFAULT_CLUB_SETTINGS['opening_time'],
            closing_time=DEFAULT_CLUB_SETTINGS['closing_time'],
            slot_duration=DEFAULT_CLUB_SETTINGS['slot_duration']
        )
        session.add(settings)
        session.commit()
    
    keyboard = [
        [InlineKeyboardButton("Изменить время открытия", callback_data="set_opening")],
        [InlineKeyboardButton("Изменить время закрытия", callback_data="set_closing")],
        [InlineKeyboardButton("Изменить длительность слота", callback_data="set_duration")],
        [InlineKeyboardButton("Назад в админ панель", callback_data="admin_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message_text = (
        f"Текущие настройки клуба:\n"
        f"Время открытия: {settings.opening_time}\n"
        f"Время закрытия: {settings.closing_time}\n"
        f"Длительность слота: {settings.slot_duration} минут"
    )
    
    try:
        if hasattr(query.message, 'photo'):
            await query.message.edit_caption(
                caption=message_text,
                reply_markup=reply_markup
            )
        else:
            await query.message.edit_text(
                text=message_text,
                reply_markup=reply_markup
            )
    except Exception as e:
        logger.error(f"Ошибка при показе настроек клуба: {e}")
        await query.message.reply_text(
            text=message_text,
            reply_markup=reply_markup
        )
    
    session.close()

async def all_bookings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать все бронирования"""
    query = update.callback_query
    await query.answer()
    
    session = Session()
    today = datetime.now().date()
    reservations = session.query(Reservation).join(Table).join(User).filter(
        Reservation.start_time >= datetime.combine(today, datetime.min.time())
    ).order_by(Reservation.start_time).all()
    
    message = "Все бронирования на сегодня:\n\n"
    keyboard = []
    
    if not reservations:
        message = "На сегодня бронирований нет"
    else:
        for res in reservations:
            status_text = "Ожидает подтверждения" if res.status == 'pending' else "Подтверждено" if res.status == 'confirmed' else "Отменено"
            status_emoji = "🟡" if res.status == 'pending' else "🟢" if res.status == 'confirmed' else "🔴"
            message += (
                f"{status_emoji} Стол {res.table.number}\n"
                f"Время: {res.start_time.strftime('%H:%M')} - {res.end_time.strftime('%H:%M')}\n"
                f"Клиент: {res.user.name} ({res.user.phone})\n"
                f"Статус: {status_text}\n"
            )
            
            # Добавляем кнопки подтверждения/отмены только для ожидающих подтверждения бронирований
            if res.status == 'pending':
                keyboard.append([
                    InlineKeyboardButton("✅ Подтвердить", callback_data=f"confirm_booking_{res.id}"),
                    InlineKeyboardButton("❌ Отменить", callback_data=f"cancel_booking_{res.id}")
                ])
                message += "\n"  # Добавляем пустую строку между бронированиями
    
    keyboard.append([InlineKeyboardButton("Назад в админ панель", callback_data="admin_panel")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        if hasattr(query.message, 'photo'):
            await query.message.edit_caption(
                caption=message,
                reply_markup=reply_markup
            )
        else:
            await query.message.edit_text(
                text=message,
                reply_markup=reply_markup
            )
    except Exception as e:
        logger.error(f"Ошибка при показе всех бронирований: {e}")
        await query.message.reply_text(
            text=message,
            reply_markup=reply_markup
        )
    
    session.close()

async def handle_booking_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка подтверждения бронирования"""
    query = update.callback_query
    await query.answer()
    
    reservation_id = int(query.data.split('_')[-1])
    
    session = Session()
    reservation = session.query(Reservation).filter_by(id=reservation_id).first()
    
    if reservation:
        # Обновляем статус бронирования
        reservation.status = 'confirmed'
        
        # Делаем стол недоступным на время бронирования
        table = session.query(Table).filter_by(id=reservation.table_id).first()
        if table:
            table.is_available = False
        
        session.commit()
        
        # Отправляем уведомление пользователю
        try:
            await context.bot.send_message(
                chat_id=reservation.user.telegram_id,
                text=f"Ваше бронирование подтверждено!\n"
                     f"Стол: {reservation.table.number}\n"
                     f"Время: {reservation.start_time.strftime('%H:%M')} - {reservation.end_time.strftime('%H:%M')}"
            )
        except Exception as e:
            logger.error(f"Ошибка при отправке уведомления пользователю: {e}")
    
    session.close()
    await all_bookings(update, context)

async def handle_booking_cancellation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка отмены бронирования"""
    query = update.callback_query
    await query.answer()
    
    reservation_id = int(query.data.split('_')[-1])
    
    session = Session()
    reservation = session.query(Reservation).filter_by(id=reservation_id).first()
    
    if reservation:
        # Обновляем статус бронирования
        reservation.status = 'cancelled'
        
        # Делаем стол доступным
        table = session.query(Table).filter_by(id=reservation.table_id).first()
        if table:
            table.is_available = True
        
        session.commit()
        
        # Заменяем отправку WhatsApp на Telegram
        await notify_admins(context, f"Бронирование отменено!\nСтол: {reservation.table.number}\nВремя: {format_time_slot((reservation.start_time, reservation.end_time))}\nКлиент: {reservation.user.name} ({reservation.user.phone})")
    
    session.close()
    await all_bookings(update, context)

async def my_bookings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать бронирования пользователя"""
    query = update.callback_query
    await query.answer()
    
    session = Session()
    user = session.query(User).filter_by(telegram_id=update.effective_user.id).first()
    
    if not user:
        if hasattr(query.message, 'photo'):
            await query.message.reply_text(
                "Ошибка: пользователь не найден",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("Главное меню", callback_data="main_menu")
                ]])
            )
            await query.message.delete()
        else:
            await query.message.edit_text(
                "Ошибка: пользователь не найден",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("Главное меню", callback_data="main_menu")
                ]])
            )
        session.close()
        return
    
    today = datetime.now().date()
    reservations = session.query(Reservation).join(Table).filter(
        Reservation.user_id == user.id,
        Reservation.start_time >= datetime.combine(today, datetime.min.time())
    ).order_by(Reservation.start_time).all()
    
    message = "Ваши бронирования на сегодня:\n\n"
    keyboard = []
    
    if not reservations:
        message = "У вас нет активных бронирований"
    else:
        for res in reservations:
            status_text = "Ожидает подтверждения" if res.status == 'pending' else "Подтверждено" if res.status == 'confirmed' else "Отменено"
            status_emoji = "🟡" if res.status == 'pending' else "🟢" if res.status == 'confirmed' else "🔴"
            message += (
                f"{status_emoji} Стол {res.table.number}\n"
                f"Время: {res.start_time.strftime('%H:%M')} - {res.end_time.strftime('%H:%M')}\n"
                f"Статус: {status_text}\n"
            )
            
            # Добавляем кнопку отмены только для неотмененных бронирований
            if res.status != 'cancelled':
                keyboard.append([
                    InlineKeyboardButton("❌ Отменить бронирование", callback_data=f"user_cancel_booking_{res.id}")
                ])
            message += "\n"
    
    keyboard.append([InlineKeyboardButton("Забронировать стол", callback_data="book_table")])
    keyboard.append([InlineKeyboardButton("Главное меню", callback_data="main_menu")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        if hasattr(query.message, 'photo'):
            # Если сообщение содержит фото, отправляем новое сообщение
            await query.message.reply_text(
                text=message,
                reply_markup=reply_markup
            )
            # Удаляем предыдущее сообщение с фото
            await query.message.delete()
        else:
            # Если сообщение без фото, редактируем его
            await query.message.edit_text(
                text=message,
                reply_markup=reply_markup
            )
    except Exception as e:
        logger.error(f"Ошибка при показе бронирований: {e}")
        await query.message.reply_text(
            text=message,
            reply_markup=reply_markup
        )
    
    session.close()

async def handle_user_booking_cancellation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка отмены бронирования пользователем"""
    query = update.callback_query
    await query.answer()
    
    reservation_id = int(query.data.split('_')[-1])
    
    session = Session()
    reservation = session.query(Reservation).filter_by(id=reservation_id).first()
    
    if reservation:
        # Проверяем, что бронирование принадлежит этому пользователю
        user = session.query(User).filter_by(telegram_id=update.effective_user.id).first()
        if reservation.user_id != user.id:
            await query.message.reply_text("Ошибка: это бронирование вам не принадлежит")
            session.close()
            return
            
        # Обновляем статус бронирования
        reservation.status = 'cancelled'
        
        # Делаем стол доступным
        table = session.query(Table).filter_by(id=reservation.table_id).first()
        if table:
            table.is_available = True
        
        session.commit()
        
        # Заменяем отправку WhatsApp на Telegram
        await notify_admins(context, f"Бронирование отменено!\nСтол: {reservation.table.number}\nВремя: {format_time_slot((reservation.start_time, reservation.end_time))}\nКлиент: {user.name} ({user.phone})")
    
    session.close()
    await my_bookings(update, context)

def main():
    """Запуск бота"""
    # Инициализируем базу данных
    init_database()
    
    # Создаем и настраиваем приложение
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Обработчики команд
    application.add_handler(CommandHandler("start", start_command))
    
    # Обработчики callback
    application.add_handler(CallbackQueryHandler(register_handler, pattern="^register$"))
    application.add_handler(CallbackQueryHandler(book_table, pattern="^book_table$"))
    application.add_handler(CallbackQueryHandler(show_main_menu, pattern="^main_menu$"))
    application.add_handler(CallbackQueryHandler(admin_panel, pattern="^admin_panel$"))
    application.add_handler(CallbackQueryHandler(manage_tables, pattern="^manage_tables$"))
    application.add_handler(CallbackQueryHandler(toggle_table_status, pattern=r"^toggle_table_\d+$"))
    application.add_handler(CallbackQueryHandler(club_settings, pattern="^club_settings$"))
    application.add_handler(CallbackQueryHandler(all_bookings, pattern="^all_bookings$"))
    application.add_handler(CallbackQueryHandler(my_bookings, pattern="^my_bookings$"))
    application.add_handler(CallbackQueryHandler(select_time_slot, pattern=r"^select_table_\d+$"))
    application.add_handler(CallbackQueryHandler(select_time_slot, pattern=r"^start_slot_\d+_\d+$"))
    application.add_handler(CallbackQueryHandler(select_time_slot, pattern=r"^end_slot_\d+_\d+$"))
    application.add_handler(CallbackQueryHandler(select_time_slot, pattern=r"^select_end_\d+_\d+$"))
    application.add_handler(CallbackQueryHandler(select_time_slot, pattern=r"^confirm_slot_\d+_\d+$"))
    application.add_handler(CallbackQueryHandler(handle_booking_confirmation, pattern=r"^confirm_booking_\d+$"))
    application.add_handler(CallbackQueryHandler(handle_booking_cancellation, pattern=r"^cancel_booking_\d+$"))
    application.add_handler(CallbackQueryHandler(handle_user_booking_cancellation, pattern=r"^user_cancel_booking_\d+$"))
    
    # Обработчик текстовых сообщений
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    logger.info("Бот запущен и готов к работе")
    
    # Запуск бота
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main() 