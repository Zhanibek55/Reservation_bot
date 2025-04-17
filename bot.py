import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from db import async_session, User, Table, Reservation, ClubSettings, init_db
from utils import create_table_layout_image, get_time_slots, format_time_slot, is_slot_available
from config import BOT_TOKEN, ADMIN_IDS, get_club_settings
from sqlalchemy import select
from sqlalchemy.orm import joinedload

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

async def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

async def notify_admins(context: ContextTypes.DEFAULT_TYPE, message: str):
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(chat_id=admin_id, text=message)
        except Exception as e:
            logger.error(f"Ошибка при отправке уведомления администратору {admin_id}: {e}")

async def safe_edit_message(update: Update, text: str, reply_markup=None):
    """
    Безопасно редактирует сообщение, учитывая его тип (текст или фото)
    
    Args:
        update: Объект обновления Telegram
        text: Новый текст или подпись
        reply_markup: Клавиатура (опционально)
    """
    if not update.callback_query or not update.callback_query.message:
        if update.message:
            return await update.message.reply_text(text, reply_markup=reply_markup)
        return False
        
    message = update.callback_query.message
    
    try:
        # Если сообщение содержит фото
        if hasattr(message, 'photo') and message.photo:
            return await message.edit_caption(caption=text, reply_markup=reply_markup)
        # Если обычное текстовое сообщение
        else:
            return await update.callback_query.edit_message_text(text, reply_markup=reply_markup)
    except Exception as e:
        logger.error(f"Ошибка при редактировании сообщения: {e}")
        # В случае ошибки отправляем новое сообщение
        return await message.reply_text(text, reply_markup=reply_markup)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.telegram_id == update.effective_user.id))
        if not user:
            keyboard = [[InlineKeyboardButton("Зарегистрироваться", callback_data="register")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                f"Привет, {update.effective_user.first_name}! Для использования бота необходимо зарегистрироваться.",
                reply_markup=reply_markup
            )
        else:
            await show_main_menu(update, context)

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("Забронировать стол", callback_data="book")],
        [InlineKeyboardButton("Мои бронирования", callback_data="my_bookings")]
    ]
    if await is_admin(update.effective_user.id):
        keyboard.append([InlineKeyboardButton("Админ панель", callback_data="admin_panel")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.message:
        await update.message.reply_text("Главное меню:", reply_markup=reply_markup)
    elif update.callback_query:
        await safe_edit_message(update, "Главное меню:", reply_markup)

async def register_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    context.user_data['registration'] = {'step': 'name'}
    await update.callback_query.edit_message_text("Пожалуйста, введите ваше имя:")

async def process_registration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    
    # Проверяем на каком шаге регистрации мы находимся
    registration_data = context.user_data.get('registration', {})
    step = registration_data.get('step', 'name')
    
    if step == 'name':
        # Сохраняем имя и запрашиваем телефон
        context.user_data['registration'] = {'step': 'phone', 'name': text}
        await update.message.reply_text(f"Спасибо, {text}! Теперь, пожалуйста, введите ваш номер телефона:")
        return
    
    elif step == 'phone':
        # Получаем имя из сохраненных данных
        name = registration_data.get('name', 'Пользователь')
        phone = text
        
        # Сохраняем данные в базу
        async with async_session() as session:
            # Проверяем, существует ли уже пользователь с таким telegram_id
            existing_user = await session.scalar(select(User).where(User.telegram_id == update.effective_user.id))
            
            if existing_user:
                # Если пользователь уже существует, обновляем его данные
                existing_user.name = name
                existing_user.phone = phone
                await session.commit()
                await update.message.reply_text(f"Ваши данные обновлены, {name}!")
            else:
                # Если пользователь не существует, создаем нового
                user = User(
                    telegram_id=update.effective_user.id,
                    name=name,
                    phone=phone,
                    is_admin=await is_admin(update.effective_user.id)
                )
                session.add(user)
                await session.commit()
                await update.message.reply_text(f"Спасибо за регистрацию, {name}!")
        
        # Очищаем данные регистрации
        context.user_data.pop('registration', None)
        
        # Показываем главное меню
        await show_main_menu(update, context)

async def book_table(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    
    async with async_session() as session:
        # Получаем все столы
        tables = (await session.execute(select(Table))).scalars().all()
        table_states = [{'number': t.number, 'is_available': t.is_available} for t in tables]
        
        # Создаем изображение с расположением столов
        img_bytes = create_table_layout_image(table_states)
        
        # Создаем клавиатуру для выбора стола
        keyboard = []
        row = []
        for i, table in enumerate(tables):
            if table.is_available:
                button = InlineKeyboardButton(f"Стол {table.number}", callback_data=f"select_table_{table.number}")
                row.append(button)
                if (i + 1) % 3 == 0 or i == len(tables) - 1:
                    keyboard.append(row)
                    row = []
        
        keyboard.append([InlineKeyboardButton("Назад", callback_data="back_to_main")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Отправляем изображение и клавиатуру
        await update.callback_query.message.reply_photo(
            photo=img_bytes,
            caption="Выберите доступный стол для бронирования:",
            reply_markup=reply_markup
        )

async def select_table(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    
    # Получаем номер стола из callback_data
    table_number = int(update.callback_query.data.split('_')[-1])
    context.user_data['selected_table'] = table_number
    
    # Получаем текущую дату и доступные слоты
    from datetime import datetime, timedelta
    today = datetime.now().date()
    dates = [today + timedelta(days=i) for i in range(7)]  # Показываем на неделю вперед
    
    # Создаем клавиатуру для выбора даты
    keyboard = []
    for date in dates:
        date_str = date.strftime("%d.%m.%Y")
        keyboard.append([InlineKeyboardButton(date_str, callback_data=f"select_date_{date.strftime('%Y-%m-%d')}")])
    
    keyboard.append([InlineKeyboardButton("Назад", callback_data="book")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await safe_edit_message(update, f"Выбран стол {table_number}. Выберите дату бронирования:", reply_markup)

async def select_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    
    # Получаем выбранную дату из callback_data
    date_str = update.callback_query.data.split('_')[-1]
    context.user_data['selected_date'] = date_str
    
    # Получаем настройки клуба для определения доступных слотов
    async with async_session() as session:
        club_settings = await session.scalar(select(ClubSettings))
        if not club_settings:
            # Используем настройки по умолчанию, если в базе нет
            from config import get_club_settings
            default_settings = get_club_settings()
            opening_time = default_settings["opening_time"]
            closing_time = default_settings["closing_time"]
            slot_duration = default_settings["slot_duration"]
        else:
            opening_time = club_settings.opening_time
            closing_time = club_settings.closing_time
            slot_duration = club_settings.slot_duration
    
    # Получаем доступные слоты для выбранной даты и стола
    from datetime import datetime
    selected_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    table_number = context.user_data['selected_table']
    
    # Получаем все слоты для этого дня
    time_slots = get_time_slots(opening_time, closing_time, slot_duration)
    
    # Проверяем доступность каждого слота
    available_slots = []
    async with async_session() as session:
        for slot in time_slots:
            start_time, end_time = slot
            # Используем время из datetime объектов и комбинируем с выбранной датой
            start_datetime = datetime.combine(selected_date, start_time.time())
            end_datetime = datetime.combine(selected_date, end_time.time())
            
            # Проверяем, есть ли уже бронирования на этот слот
            existing_reservation = await session.scalar(
                select(Reservation).where(
                    Reservation.table_id == table_number,
                    Reservation.start_time <= end_datetime,
                    Reservation.end_time >= start_datetime,
                    Reservation.status != 'cancelled'
                )
            )
            
            if not existing_reservation:
                available_slots.append((start_datetime, end_datetime))
    
    # Создаем клавиатуру для выбора времени
    keyboard = []
    for slot in available_slots:
        start_time, end_time = slot
        slot_str = format_time_slot((start_time, end_time))
        keyboard.append([InlineKeyboardButton(
            slot_str, 
            callback_data=f"select_time_{start_time.timestamp()}_{end_time.timestamp()}"
        )])
    
    keyboard.append([InlineKeyboardButton("Назад", callback_data=f"select_table_{table_number}")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if available_slots:
        await safe_edit_message(update, f"Выбран стол {table_number} на {selected_date.strftime('%d.%m.%Y')}. Выберите время:", reply_markup)
    else:
        await safe_edit_message(update, f"На выбранную дату нет доступных слотов для стола {table_number}. Выберите другую дату:", reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Назад к выбору даты", callback_data=f"select_table_{table_number}")]
        ]))

async def select_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    
    # Получаем данные о времени из callback_data
    parts = update.callback_query.data.split('_')
    start_timestamp = float(parts[-2])
    end_timestamp = float(parts[-1])
    
    # Сохраняем в контексте
    context.user_data['start_time'] = start_timestamp
    context.user_data['end_time'] = end_timestamp
    
    # Получаем данные о бронировании
    table_number = context.user_data['selected_table']
    date_str = context.user_data['selected_date']
    
    from datetime import datetime
    start_time = datetime.fromtimestamp(start_timestamp)
    end_time = datetime.fromtimestamp(end_timestamp)
    
    # Форматируем информацию о бронировании
    booking_info = (
        f"Подтвердите бронирование:\n\n"
        f"Стол: {table_number}\n"
        f"Дата: {start_time.strftime('%d.%m.%Y')}\n"
        f"Время: {start_time.strftime('%H:%M')} - {end_time.strftime('%H:%M')}"
    )
    
    # Создаем клавиатуру для подтверждения
    keyboard = [
        [InlineKeyboardButton("Подтвердить", callback_data="confirm_booking")],
        [InlineKeyboardButton("Отмена", callback_data=f"select_date_{date_str}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await safe_edit_message(update, booking_info, reply_markup)

async def confirm_booking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    
    # Получаем данные о бронировании из контекста
    table_number = context.user_data['selected_table']
    start_timestamp = context.user_data['start_time']
    end_timestamp = context.user_data['end_time']
    
    from datetime import datetime
    start_time = datetime.fromtimestamp(start_timestamp)
    end_time = datetime.fromtimestamp(end_timestamp)
    
    # Создаем бронирование в базе данных
    async with async_session() as session:
        # Получаем пользователя
        user = await session.scalar(select(User).where(User.telegram_id == update.effective_user.id))
        if not user:
            await safe_edit_message(update, "Ошибка: пользователь не найден. Пожалуйста, зарегистрируйтесь.")
            return
        
        # Получаем стол
        table = await session.scalar(select(Table).where(Table.number == table_number))
        if not table:
            await safe_edit_message(update, "Ошибка: выбранный стол не найден.")
            return
        
        # Проверяем, не занят ли слот
        existing_reservation = await session.scalar(
            select(Reservation).where(
                Reservation.table_id == table.id,
                Reservation.start_time <= end_time,
                Reservation.end_time >= start_time,
                Reservation.status != 'cancelled'
            )
        )
        
        if existing_reservation:
            await safe_edit_message(update, "Извините, этот слот уже забронирован. Пожалуйста, выберите другое время.")
            return
        
        # Создаем новое бронирование
        new_reservation = Reservation(
            table_id=table.id,
            user_id=user.id,
            start_time=start_time,
            end_time=end_time,
            status='pending'
        )
        session.add(new_reservation)
        await session.commit()
        
        # Уведомляем администраторов о новом бронировании
        admin_message = (
            f"Новое бронирование!\n\n"
            f"Пользователь: {user.name} ({user.phone})\n"
            f"Стол: {table_number}\n"
            f"Дата: {start_time.strftime('%d.%m.%Y')}\n"
            f"Время: {start_time.strftime('%H:%M')} - {end_time.strftime('%H:%M')}"
        )
        await notify_admins(context, admin_message)
    
    # Сообщаем пользователю об успешном бронировании
    success_message = (
        f"Бронирование успешно создано!\n\n"
        f"Стол: {table_number}\n"
        f"Дата: {start_time.strftime('%d.%m.%Y')}\n"
        f"Время: {start_time.strftime('%H:%M')} - {end_time.strftime('%H:%M')}\n\n"
        f"Статус: Ожидает подтверждения администратором"
    )
    
    keyboard = [[InlineKeyboardButton("Вернуться в главное меню", callback_data="back_to_main")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await safe_edit_message(update, success_message, reply_markup)

async def back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await show_main_menu(update, context)

async def my_bookings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with async_session() as session:
        bookings = (await session.execute(select(Reservation).where(Reservation.user_id == update.effective_user.id))).scalars().all()
        text = "Ваши бронирования:\n"
        for b in bookings:
            text += f"Стол {b.table_id}: {format_time_slot((b.start_time, b.end_time))} — {b.status}\n"
        await update.callback_query.answer()
        await safe_edit_message(update, text)

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not await is_admin(user_id):
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
        await safe_edit_message(update, "Панель администратора:", reply_markup)
    else:
        await update.message.reply_text(
            "Панель администратора:",
            reply_markup=reply_markup
        )

async def manage_tables(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    async with async_session() as session:
        tables = (await session.execute(select(Table))).scalars().all()
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
        await safe_edit_message(update, message_text, reply_markup)

async def toggle_table_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    table_number = int(query.data.split('_')[-1])
    async with async_session() as session:
        table = (await session.execute(select(Table).where(Table.number == table_number))).scalar_one_or_none()
        if table:
            table.is_available = not table.is_available
            await session.commit()
    await manage_tables(update, context)

async def club_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()
    
    async with async_session() as session:
        # Получаем настройки клуба напрямую из базы данных
        stmt = select(ClubSettings)
        result = await session.execute(stmt)
        settings = result.scalar_one_or_none()
        
        if not settings:
            from config import DEFAULT_CLUB_SETTINGS
            settings = ClubSettings(
                opening_time=DEFAULT_CLUB_SETTINGS['opening_time'],
                closing_time=DEFAULT_CLUB_SETTINGS['closing_time'],
                slot_duration=DEFAULT_CLUB_SETTINGS['slot_duration']
            )
            session.add(settings)
            await session.commit()
            
            # Повторно получаем настройки, чтобы убедиться, что они сохранились
            stmt = select(ClubSettings)
            result = await session.execute(stmt)
            settings = result.scalar_one_or_none()
        
        # Выводим текущие настройки из базы данных
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
        
        # Используем правильный метод для отправки сообщения
        if update.callback_query:
            await safe_edit_message(update, message_text, reply_markup)
        else:
            # Если функция вызвана не из callback_query
            await update.message.reply_text(message_text, reply_markup=reply_markup)

async def all_bookings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    async with async_session() as session:
        # Используем joinedload для предварительной загрузки связанных объектов
        stmt = (
            select(Reservation)
            .options(joinedload(Reservation.table), joinedload(Reservation.user))
            .order_by(Reservation.start_time)
        )
        
        result = await session.execute(stmt)
        reservations = result.scalars().all()
        
        keyboard = []
        message = "Все бронирования:\n\n"
        
        if not reservations:
            message += "Бронирований нет."
        else:
            for res in reservations:
                status_text = "Ожидает подтверждения" if res.status == 'pending' else "Подтверждено" if res.status == 'confirmed' else "Отменено"
                status_emoji = "🟡" if res.status == 'pending' else "🟢" if res.status == 'confirmed' else "🔴"
                message += (
                    f"{status_emoji} Стол {res.table.number}\n"
                    f"Время: {res.start_time.strftime('%H:%M')} - {res.end_time.strftime('%H:%M')}\n"
                    f"Клиент: {res.user.name} ({res.user.phone if res.user.phone else 'нет телефона'})\n"
                    f"Статус: {status_text}\n"
                )
                if res.status == 'pending':
                    keyboard.append([
                        InlineKeyboardButton("✅ Подтвердить", callback_data=f"confirm_booking_{res.id}"),
                        InlineKeyboardButton("❌ Отменить", callback_data=f"cancel_booking_{res.id}")
                    ])
                    message += "\n"
        keyboard.append([InlineKeyboardButton("Назад в админ панель", callback_data="admin_panel")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await safe_edit_message(update, message, reply_markup)

async def handle_booking_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    booking_id = int(query.data.split('_')[-1])
    action = "confirm" if "confirm_booking" in query.data else "cancel"
    
    async with async_session() as session:
        booking = await session.get(Reservation, booking_id)
        if not booking:
            await safe_edit_message(update, "Бронирование не найдено.")
            return
        
        if action == "confirm":
            booking.status = "confirmed"
            status_text = "подтверждено"
        else:
            booking.status = "cancelled"
            status_text = "отменено"
        
        await session.commit()
        
        # Уведомляем пользователя о изменении статуса бронирования
        user = await session.get(User, booking.user_id)
        if user:
            try:
                table = await session.get(Table, booking.table_id)
                table_number = table.number if table else booking.table_id
                
                user_message = (
                    f"Статус вашего бронирования изменен!\n\n"
                    f"Стол: {table_number}\n"
                    f"Дата: {booking.start_time.strftime('%d.%m.%Y')}\n"
                    f"Время: {booking.start_time.strftime('%H:%M')} - {booking.end_time.strftime('%H:%M')}\n"
                    f"Новый статус: {status_text}"
                )
                await context.bot.send_message(chat_id=user.telegram_id, text=user_message)
            except Exception as e:
                logger.error(f"Ошибка при отправке уведомления пользователю: {e}")
        
        # Обновляем сообщение администратора
        await safe_edit_message(update, f"Бронирование #{booking_id} {status_text}!", 
                             InlineKeyboardMarkup([[InlineKeyboardButton("Вернуться к списку", callback_data="all_bookings")]]))

async def handle_booking_cancellation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    booking_id = int(query.data.split('_')[-1])
    
    async with async_session() as session:
        booking = await session.get(Reservation, booking_id)
        if not booking:
            await safe_edit_message(update, "Бронирование не найдено.")
            return
        
        booking.status = "cancelled"
        
        # Обновляем статус стола, если нужно
        table = await session.get(Table, booking.table_id)
        if table:
            table.is_available = True
        
        await session.commit()
        
        # Уведомляем пользователя об отмене бронирования
        user = await session.get(User, booking.user_id)
        if user:
            try:
                table_number = table.number if table else booking.table_id
                
                user_message = (
                    f"Ваше бронирование отменено!\n\n"
                    f"Стол: {table_number}\n"
                    f"Дата: {booking.start_time.strftime('%d.%m.%Y')}\n"
                    f"Время: {booking.start_time.strftime('%H:%M')} - {booking.end_time.strftime('%H:%M')}"
                )
                await context.bot.send_message(chat_id=user.telegram_id, text=user_message)
                
                # Уведомляем администраторов
                admin_message = (
                    f"Бронирование отменено!\n"
                    f"Стол: {table_number}\n"
                    f"Время: {format_time_slot((booking.start_time, booking.end_time))}\n"
                    f"Клиент: {user.name} ({user.phone if user.phone else 'нет телефона'})"
                )
                await notify_admins(context, admin_message)
            except Exception as e:
                logger.error(f"Ошибка при отправке уведомлений: {e}")
        
        # Обновляем сообщение администратора
        await safe_edit_message(update, f"Бронирование #{booking_id} отменено!", 
                             InlineKeyboardMarkup([[InlineKeyboardButton("Вернуться к списку", callback_data="all_bookings")]]))

async def handle_user_booking_cancellation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    reservation_id = int(query.data.split('_')[-1])
    async with async_session() as session:
        reservation = (await session.execute(select(Reservation).where(Reservation.id == reservation_id))).scalar_one_or_none()
        if reservation:
            user = reservation.user
            if user.telegram_id == update.effective_user.id:
                reservation.status = 'cancelled'
                table = (await session.execute(select(Table).where(Table.id == reservation.table_id))).scalar_one_or_none()
                if table:
                    table.is_available = True
                await session.commit()
                try:
                    await notify_admins(context, f"Бронирование отменено!\nСтол: {reservation.table.number}\nВремя: {format_time_slot((reservation.start_time, reservation.end_time))}\nКлиент: {user.name} ({user.phone})")
                except Exception as e:
                    logger.error(f"Ошибка при отправке уведомления админам: {e}")
    await my_bookings(update, context)

async def confirm_booking_multiple(update: Update, context: ContextTypes.DEFAULT_TYPE, table_number: int, start_timestamp: int, end_timestamp: int):
    try:
        query = update.callback_query
        await query.answer()
        from datetime import datetime as dt
        start_time = dt.fromtimestamp(start_timestamp)
        end_time = dt.fromtimestamp(end_timestamp)
        if start_time >= end_time:
            await query.message.reply_text("Ошибка: время окончания должно быть позже времени начала.")
            return
        async with async_session() as session:
            table = (await session.execute(select(Table).where(Table.number == table_number))).scalar_one_or_none()
            user = (await session.execute(select(User).where(User.telegram_id == update.effective_user.id))).scalar_one_or_none()
            if not (table and user):
                await query.message.reply_text("Ошибка: не найден стол или пользователь.")
                return
            reservation = Reservation(
                table_id=table.id,
                user_id=user.id,
                start_time=start_time,
                end_time=end_time,
                status='pending'
            )
            session.add(reservation)
            await session.commit()
            await notify_admins(context, f"Новая заявка на бронирование:\nСтол: {table.number}\nВремя: {format_time_slot((start_time, end_time))}\nКлиент: {user.name} ({user.phone})")
        await show_main_menu(update, context)
    except Exception as e:
        logger.error(f"Ошибка при подтверждении бронирования: {e}")
        await update.callback_query.message.reply_text("Произошла ошибка при бронировании. Пожалуйста, попробуйте позже или обратитесь к администратору.")

async def book_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /book для бронирования стола"""
    # Проверяем, зарегистрирован ли пользователь
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.telegram_id == update.effective_user.id))
        if not user:
            keyboard = [[InlineKeyboardButton("Зарегистрироваться", callback_data="register")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                "Для бронирования стола необходимо зарегистрироваться.",
                reply_markup=reply_markup
            )
            return
    
    # Получаем доступные столы и отображаем их
    async with async_session() as session:
        tables = (await session.execute(select(Table))).scalars().all()
        table_states = []
        
        for table in tables:
            table_states.append({
                "number": table.number,
                "is_available": table.is_available
            })
        
        # Создаем изображение с расположением столов
        img_bytes = create_table_layout_image(table_states)
        
        # Создаем клавиатуру с доступными столами
        keyboard = []
        row = []
        for i, table in enumerate(tables):
            if table.is_available:
                if len(row) < 3:  # Максимум 3 кнопки в ряду
                    row.append(InlineKeyboardButton(f"Стол {table.number}", callback_data=f"select_table_{table.number}"))
                else:
                    keyboard.append(row)
                    row = [InlineKeyboardButton(f"Стол {table.number}", callback_data=f"select_table_{table.number}")]
        
        if row:  # Добавляем оставшиеся кнопки
            keyboard.append(row)
        
        keyboard.append([InlineKeyboardButton("Назад", callback_data="back_to_main")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_photo(
            photo=img_bytes,
            caption="Выберите доступный стол для бронирования:",
            reply_markup=reply_markup
        )

async def my_bookings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /my_bookings для просмотра бронирований пользователя"""
    # Проверяем, зарегистрирован ли пользователь
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.telegram_id == update.effective_user.id))
        if not user:
            keyboard = [[InlineKeyboardButton("Зарегистрироваться", callback_data="register")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                "Для просмотра бронирований необходимо зарегистрироваться.",
                reply_markup=reply_markup
            )
            return
        
        # Получаем бронирования пользователя
        stmt = (
            select(Reservation)
            .options(joinedload(Reservation.table))
            .where(Reservation.user_id == user.id)
            .order_by(Reservation.start_time)
        )
        result = await session.execute(stmt)
        bookings = result.scalars().all()
        
        text = "Ваши бронирования:\n\n"
        if not bookings:
            text += "У вас нет активных бронирований."
        else:
            for b in bookings:
                status_text = "Ожидает подтверждения" if b.status == 'pending' else "Подтверждено" if b.status == 'confirmed' else "Отменено"
                status_emoji = "🟡" if b.status == 'pending' else "🟢" if b.status == 'confirmed' else "🔴"
                text += (
                    f"{status_emoji} Стол {b.table.number}\n"
                    f"Дата: {b.start_time.strftime('%d.%m.%Y')}\n"
                    f"Время: {b.start_time.strftime('%H:%M')} - {b.end_time.strftime('%H:%M')}\n"
                    f"Статус: {status_text}\n\n"
                )
        
        keyboard = [[InlineKeyboardButton("Вернуться в главное меню", callback_data="back_to_main")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(text, reply_markup=reply_markup)

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /admin для доступа к админ-панели"""
    user_id = update.effective_user.id
    if not await is_admin(user_id):
        await update.message.reply_text("У вас нет доступа к админ-панели.")
        return
    
    # Создаем клавиатуру админ-панели
    keyboard = [
        [InlineKeyboardButton("Все бронирования", callback_data="all_bookings")],
        [InlineKeyboardButton("Управление столами", callback_data="manage_tables")],
        [InlineKeyboardButton("Настройки клуба", callback_data="club_settings")],
        [InlineKeyboardButton("Вернуться в главное меню", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text("Панель администратора:", reply_markup=reply_markup)

async def set_opening(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['settings_step'] = 'set_opening'
    await query.message.reply_text("Введите новое время открытия клуба (HH:MM):")

async def set_closing(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['settings_step'] = 'set_closing'
    await query.message.reply_text("Введите новое время закрытия клуба (HH:MM):")

async def set_duration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['settings_step'] = 'set_duration'
    await query.message.reply_text("Введите новую длительность слота (в минутах):")

async def handle_settings_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    step = context.user_data.get('settings_step')
    text = update.message.text.strip()
    
    if not step:
        await update.message.reply_text("Ошибка: неизвестный шаг настройки.")
        return
    
    try:
        async with async_session() as session:
            # Получаем настройки из базы данных
            stmt = select(ClubSettings)
            result = await session.execute(stmt)
            settings = result.scalar_one_or_none()
            
            if not settings:
                from config import DEFAULT_CLUB_SETTINGS
                settings = ClubSettings(
                    opening_time=DEFAULT_CLUB_SETTINGS['opening_time'],
                    closing_time=DEFAULT_CLUB_SETTINGS['closing_time'],
                    slot_duration=DEFAULT_CLUB_SETTINGS['slot_duration']
                )
                session.add(settings)
                await session.commit()
                
                # Повторно получаем настройки
                stmt = select(ClubSettings)
                result = await session.execute(stmt)
                settings = result.scalar_one_or_none()
            
            if step == 'set_opening':
                # Проверяем формат времени и преобразуем его
                try:
                    # Пробуем разные форматы ввода
                    import re
                    # Удаляем все, кроме цифр и точек/двоеточий
                    clean_text = re.sub(r'[^\d\.\:]', '', text)
                    
                    # Проверяем, содержит ли ввод точку или двоеточие
                    if '.' in clean_text:
                        parts = clean_text.split('.')
                        hours = int(parts[0])
                        minutes = int(parts[1]) if len(parts) > 1 and parts[1] else 0
                    elif ':' in clean_text:
                        parts = clean_text.split(':')
                        hours = int(parts[0])
                        minutes = int(parts[1]) if len(parts) > 1 and parts[1] else 0
                    else:
                        # Если ввод только цифры, предполагаем, что это часы
                        hours = int(clean_text)
                        minutes = 0
                    
                    # Проверяем корректность значений
                    if hours < 0 or hours > 23 or minutes < 0 or minutes > 59:
                        raise ValueError("Некорректное время")
                    
                    # Форматируем время в нужный формат
                    formatted_time = f"{hours:02d}:{minutes:02d}"
                    
                    # Обновляем настройки в базе данных
                    settings.opening_time = formatted_time
                    await session.commit()
                    
                    # Проверяем, что настройки обновились
                    await session.refresh(settings)
                    
                    await update.message.reply_text(f"Время открытия установлено: {settings.opening_time}")
                except Exception as e:
                    logger.error(f"Ошибка при обработке времени открытия: {e}")
                    await update.message.reply_text("Ошибка: введите время в формате ЧЧ:ММ или ЧЧ.ММ")
                    return
            
            elif step == 'set_closing':
                # Проверяем формат времени и преобразуем его
                try:
                    # Пробуем разные форматы ввода
                    import re
                    # Удаляем все, кроме цифр и точек/двоеточий
                    clean_text = re.sub(r'[^\d\.\:]', '', text)
                    
                    # Проверяем, содержит ли ввод точку или двоеточие
                    if '.' in clean_text:
                        parts = clean_text.split('.')
                        hours = int(parts[0])
                        minutes = int(parts[1]) if len(parts) > 1 and parts[1] else 0
                    elif ':' in clean_text:
                        parts = clean_text.split(':')
                        hours = int(parts[0])
                        minutes = int(parts[1]) if len(parts) > 1 and parts[1] else 0
                    else:
                        # Если ввод только цифры, предполагаем, что это часы
                        hours = int(clean_text)
                        minutes = 0
                    
                    # Проверяем корректность значений
                    if hours < 0 or hours > 23 or minutes < 0 or minutes > 59:
                        raise ValueError("Некорректное время")
                    
                    # Форматируем время в нужный формат
                    formatted_time = f"{hours:02d}:{minutes:02d}"
                    
                    # Обновляем настройки в базе данных
                    settings.closing_time = formatted_time
                    await session.commit()
                    
                    # Проверяем, что настройки обновились
                    await session.refresh(settings)
                    
                    await update.message.reply_text(f"Время закрытия установлено: {settings.closing_time}")
                except Exception as e:
                    logger.error(f"Ошибка при обработке времени закрытия: {e}")
                    await update.message.reply_text("Ошибка: введите время в формате ЧЧ:ММ или ЧЧ.ММ")
                    return
            
            elif step == 'set_duration':
                try:
                    # Удаляем все, кроме цифр
                    clean_text = ''.join(filter(str.isdigit, text))
                    duration = int(clean_text)
                    if duration <= 0:
                        raise ValueError("Длительность должна быть положительным числом")
                    
                    # Обновляем настройки в базе данных
                    settings.slot_duration = duration
                    await session.commit()
                    
                    # Проверяем, что настройки обновились
                    await session.refresh(settings)
                    
                    await update.message.reply_text(f"Длительность слота установлена: {settings.slot_duration} минут")
                except ValueError:
                    await update.message.reply_text("Ошибка: введите целое положительное число для длительности слота.")
                    return
            
            # Очищаем шаг настройки
            context.user_data.pop('settings_step', None)
            
            # Создаем объект для передачи в club_settings
            class DummyCallback:
                message = update.message
                callback_query = None
            
            dummy_update = Update(update.update_id, message=update.message)
            dummy_update.callback_query = DummyCallback()
            
            # Показываем обновленные настройки
            await club_settings(dummy_update, context)
    
    except Exception as e:
        logger.error(f"Ошибка при обновлении настроек: {e}")
        await update.message.reply_text("Произошла ошибка при обновлении настроек. Пожалуйста, попробуйте еще раз.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Справка по использованию бота:\n\n"
                                    "/start - начать работу с ботом\n"
                                    "/help - показать справку\n"
                                    "Зарегистрироваться - зарегистрироваться в системе\n"
                                    "Забронировать стол - забронировать стол\n"
                                    "Мои бронирования - показать мои бронирования\n"
                                    "Админ панель - показать административную панель (для администраторов)")

async def main():
    await init_db()
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Настраиваем команды меню бота - только самые необходимые
    commands = [
        BotCommand("book", "Забронировать стол"),
        BotCommand("my_bookings", "Мои бронирования"),
        BotCommand("admin", "Админ панель")
    ]
    await app.bot.set_my_commands(commands)
    
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("book", book_command))
    app.add_handler(CommandHandler("my_bookings", my_bookings_command))
    app.add_handler(CommandHandler("admin", admin_command))
    app.add_handler(CallbackQueryHandler(register_handler, pattern="register"))
    app.add_handler(CallbackQueryHandler(book_table, pattern="book"))
    app.add_handler(CallbackQueryHandler(my_bookings, pattern="my_bookings"))
    app.add_handler(CallbackQueryHandler(admin_panel, pattern="admin_panel"))
    app.add_handler(CallbackQueryHandler(manage_tables, pattern="manage_tables"))
    app.add_handler(CallbackQueryHandler(toggle_table_status, pattern="toggle_table_"))
    app.add_handler(CallbackQueryHandler(club_settings, pattern="club_settings"))
    app.add_handler(CallbackQueryHandler(all_bookings, pattern="all_bookings"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, process_registration))
    app.add_handler(CallbackQueryHandler(handle_booking_confirmation, pattern=r"^confirm_booking_\d+$"))
    app.add_handler(CallbackQueryHandler(handle_booking_cancellation, pattern=r"^cancel_booking_\d+$"))
    app.add_handler(CallbackQueryHandler(set_opening, pattern="set_opening"))
    app.add_handler(CallbackQueryHandler(set_closing, pattern="set_closing"))
    app.add_handler(CallbackQueryHandler(set_duration, pattern="set_duration"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_settings_input))
    app.add_handler(CallbackQueryHandler(select_table, pattern=r"^select_table_\d+$"))
    app.add_handler(CallbackQueryHandler(select_date, pattern=r"^select_date_\d{4}-\d{2}-\d{2}$"))
    app.add_handler(CallbackQueryHandler(select_time, pattern=r"^select_time_[\d\.]+_[\d\.]+$"))
    app.add_handler(CallbackQueryHandler(confirm_booking, pattern="confirm_booking"))
    app.add_handler(CallbackQueryHandler(back_to_main, pattern="back_to_main"))
    
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    
    try:
        while True:
            await asyncio.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        await app.updater.stop()
        await app.stop()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
