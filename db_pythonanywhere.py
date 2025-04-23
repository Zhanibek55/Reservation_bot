import asyncio
import os
import sys
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, select, func, create_engine
from sqlalchemy.orm import Session
from datetime import datetime
from config import DATABASE_URL, get_table_layout, get_club_settings

Base = declarative_base()

# Используем синхронный SQLite
engine = create_engine(DATABASE_URL.replace('sqlite+aiosqlite', 'sqlite'), echo=False)

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

# Асинхронная обертка для синхронного движка
class AsyncSessionWrapper:
    def __init__(self):
        self.session = Session(engine)
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.session.close()
    
    async def execute(self, *args, **kwargs):
        result = self.session.execute(*args, **kwargs)
        return result
    
    async def scalar(self, *args, **kwargs):
        result = self.session.scalar(*args, **kwargs)
        return result
    
    async def commit(self):
        self.session.commit()
    
    async def refresh(self, obj):
        self.session.refresh(obj)
    
    def add(self, obj):
        self.session.add(obj)
    
    def add_all(self, objs):
        self.session.add_all(objs)
    
    def scalars(self):
        return self.session.scalars()

# Функция для создания асинхронной сессии
async def async_session():
    return AsyncSessionWrapper()

def init_db_sync():
    """Синхронная инициализация базы данных"""
    Base.metadata.create_all(engine)
    
    with Session(engine) as session:
        # Проверяем, есть ли столы в базе
        tables_count = session.scalar(select(func.count()).select_from(Table))
        if tables_count == 0:
            # Добавляем столы из конфигурации
            table_layout = get_table_layout()
            for table_data in table_layout:
                table = Table(number=table_data["number"], is_available=True)
                session.add(table)
        
        # Проверяем настройки клуба
        club_settings = session.scalar(select(ClubSettings))
        if not club_settings:
            default_settings = get_club_settings()
            club_settings = ClubSettings(
                opening_time=default_settings["opening_time"],
                closing_time=default_settings["closing_time"],
                slot_duration=default_settings["slot_duration"]
            )
            session.add(club_settings)
        
        session.commit()

async def init_db():
    """Асинхронная обертка для инициализации базы данных"""
    init_db_sync()
    return True
