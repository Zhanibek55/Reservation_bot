from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

from config import DATABASE_URL

Base = declarative_base()
engine = create_engine(DATABASE_URL)

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
    status = Column(String, default='pending')  # pending, confirmed, cancelled
    created_at = Column(DateTime, default=datetime.utcnow)
    
    table = relationship("Table")
    user = relationship("User")
    
class ClubSettings(Base):
    __tablename__ = 'club_settings'
    
    id = Column(Integer, primary_key=True)
    opening_time = Column(String)
    closing_time = Column(String)
    slot_duration = Column(Integer)  # в минутах
    
# Создаем таблицы
Base.metadata.create_all(engine) 