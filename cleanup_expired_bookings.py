import asyncio
import logging
from datetime import datetime, timedelta
from sqlalchemy import select, update
from db import async_session, Reservation, init_db

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def cleanup_expired_bookings():
    logger.info("Начинаем проверку и очистку устаревших бронирований...")
    
    # Инициализируем базу данных
    await init_db()
    
    # Текущее время
    now = datetime.now()
    
    async with async_session() as session:
        # Получаем все бронирования, у которых end_time меньше текущего времени
        # и статус не cancelled
        stmt = select(Reservation).where(
            Reservation.end_time < now,
            Reservation.status != 'cancelled'
        )
        result = await session.execute(stmt)
        expired_bookings = result.scalars().all()
        
        if not expired_bookings:
            logger.info("Устаревших бронирований не найдено.")
            return
        
        logger.info(f"Найдено {len(expired_bookings)} устаревших бронирований:")
        
        # Обновляем статус устаревших бронирований на 'expired'
        for booking in expired_bookings:
            booking.status = 'expired'
            logger.info(f"Бронирование #{booking.id} (Стол {booking.table.number}, "
                       f"{booking.start_time.strftime('%Y-%m-%d %H:%M')} - "
                       f"{booking.end_time.strftime('%Y-%m-%d %H:%M')}) "
                       f"помечено как истекшее.")
        
        await session.commit()
        logger.info(f"Всего обновлено {len(expired_bookings)} бронирований.")

if __name__ == "__main__":
    asyncio.run(cleanup_expired_bookings())
