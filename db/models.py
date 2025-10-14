from sqlalchemy import Column, Integer, String, DateTime, Boolean, BigInteger, ForeignKey, Text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, relationship

# Настройка асинхронного подключения к SQLite3
DB_URL = "sqlite+aiosqlite:///db/database.db"
engine = create_async_engine(DB_URL)  # Асинхронный движок SQLAlchemy
Session = async_sessionmaker(expire_on_commit=False, bind=engine)  # Фабрика сессий


class Base(DeclarativeBase, AsyncAttrs):
    """Базовый класс для декларативных моделей с поддержкой асинхронных атрибутов"""
    pass


class User(Base):
    """Модель для хранения запросов на подписку"""
    __tablename__ = "user"

    user_id = Column(BigInteger, primary_key=True)  # ID пользователя Telegram
    username = Column(String, nullable=True)  # @username пользователя
    first_name = Column(String, nullable=True)  # Имя пользователя
    last_name = Column(String, nullable=True)  # Фамилия пользователя
    user_is_block = Column(Boolean, default=False)  # Флаг блокировки пользователя

    # Связь с вопросами
    questions = relationship("Question", back_populates="user")
    # Связь с отзывами
    reviews = relationship("Review", back_populates="user")


class Question(Base):
    """Модель для хранения вопросов пользователей"""
    __tablename__ = "question"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey('user.user_id'), nullable=False)
    question = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False)
    answer = Column(String, nullable=True)
    answered_at = Column(DateTime, nullable=True)

    # Связь с пользователем
    user = relationship("User", back_populates="questions")


class Event(Base):
    """Модель для хранения мероприятий"""
    __tablename__ = "event"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String, nullable=False)  # Название мероприятия
    description = Column(String, nullable=False)  # Описание мероприятия
    event_date = Column(DateTime, nullable=False)  # Дата в формате DateTime
    video_url = Column(String, nullable=True)  # Ссылка на видео
    created_at = Column(DateTime, nullable=False)  # Дата создания

    # Связь с отзывами
    reviews = relationship("Review", back_populates="event", cascade="all, delete-orphan")


class Review(Base):
    """Модель для хранения отзывов о мероприятиях"""
    __tablename__ = "review"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey('user.user_id'), nullable=False)
    event_id = Column(Integer, ForeignKey('event.id', ondelete="CASCADE"), nullable=False)
    text = Column(Text, nullable=False)  # Текст отзыва
    created_at = Column(DateTime, nullable=False)  # Дата создания отзыва

    # Связь с пользователем
    user = relationship("User", back_populates="reviews")
    # Связь с мероприятием
    event = relationship("Event", back_populates="reviews")


class Post(Base):
    """Модель для хранения поста"""
    __tablename__ = "post"

    id = Column(Integer, primary_key=True, autoincrement=True)
    type = Column(Text, nullable=False)
    media = Column(Text, nullable=True)
    text = Column(Text, nullable=True)
    button_text = Column(Text, nullable=True)
    button_link = Column(Text, nullable=True)
    send_at = Column(DateTime, nullable=False)
    flag = Column(Boolean, default=False)


async def create_tables():
    """Создает таблицы в базе данных"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
