import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, select, func
from datetime import datetime
from config import DATABASE_URL, get_table_layout, get_club_settings

Base = declarative_base()
engine = create_async_engine(DATABASE_URL, echo=False)
async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True)
    phone = Column(String)
    name = Column(String)
    is_admin = Column(Boolean, default=False)

class Table(Base):
    __tablename__ = 'tables'
    id = Column(Integer, primary_key=True)
    number = Column(Integer, unique=True)
    is_available = Column(Boolean, default=True)

class Reservation(Base):
    __tablename__ = 'reservations'
    id = Column(Integer, primary_key=True)
    table_id = Column(Integer, ForeignKey('tables.id'))
    user_id = Column(Integer, ForeignKey('users.id'))
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    status = Column(String, default='pending')
    created_at = Column(DateTime, default=datetime.utcnow)
    table = relationship("Table")
    user = relationship("User")

class ClubSettings(Base):
    __tablename__ = 'club_settings'
    id = Column(Integer, primary_key=True)
    opening_time = Column(String)
    closing_time = Column(String)
    slot_duration = Column(Integer)

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Проверка и инициализация столов
    async with async_session() as session:
        # Проверяем, есть ли столы в базе
        tables_count = await session.scalar(select(func.count()).select_from(Table))
        if tables_count == 0:
            # Добавляем столы из конфигурации
            table_layout = get_table_layout()
            for table_data in table_layout:
                table = Table(number=table_data["number"], is_available=True)
                session.add(table)
        
        # Проверяем настройки клуба
        club_settings = await session.scalar(select(ClubSettings))
        if not club_settings:
            default_settings = get_club_settings()
            club_settings = ClubSettings(
                opening_time=default_settings["opening_time"],
                closing_time=default_settings["closing_time"],
                slot_duration=default_settings["slot_duration"]
            )
            session.add(club_settings)
        
        await session.commit()
