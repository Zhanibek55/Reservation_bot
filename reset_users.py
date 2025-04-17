import asyncio
import logging
from sqlalchemy import select, delete
from db import async_session, User, Reservation, init_db

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def reset_users():
    logger.info("Начинаем сброс пользователей...")
    
    # Инициализируем базу данных
    await init_db()
    
    async with async_session() as session:
        # Получаем всех пользователей
        stmt = select(User)
        result = await session.execute(stmt)
        users = result.scalars().all()
        
        admin_count = 0
        regular_count = 0
        
        # Выводим информацию о пользователях
        logger.info(f"Всего пользователей в базе: {len(users)}")
        for user in users:
            if user.is_admin:
                admin_count += 1
                logger.info(f"Администратор: {user.name} (ID: {user.telegram_id})")
            else:
                regular_count += 1
                logger.info(f"Обычный пользователь: {user.name} (ID: {user.telegram_id})")
        
        # Удаляем все бронирования обычных пользователей
        for user in users:
            if not user.is_admin:
                # Удаляем бронирования пользователя
                delete_stmt = delete(Reservation).where(Reservation.user_id == user.id)
                await session.execute(delete_stmt)
        
        # Удаляем обычных пользователей
        delete_stmt = delete(User).where(User.is_admin == False)
        result = await session.execute(delete_stmt)
        deleted_count = result.rowcount
        
        await session.commit()
        
        logger.info(f"Удалено {deleted_count} обычных пользователей")
        logger.info(f"Сохранено {admin_count} администраторов")

if __name__ == "__main__":
    asyncio.run(reset_users())
