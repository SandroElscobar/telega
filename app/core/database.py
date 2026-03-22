"""
Настройка подключения к базе данных через SQLAlchemy.
"""

from sqlalchemy.ext.asyncio import (
    AsyncSession, async_sessionmaker, create_async_engine, AsyncEngine
)

from typing import AsyncGenerator, Optional
import contextlib

from app.core.config import settings

class DataBaseManager:
    """
    Менеджер для работы с базой данных.
    Управляет движком и сессиями SQLAlchemy.
    """
    def __init__(self):
        self.engine: Optional[AsyncEngine] = None
        self.async_session_maker: Optional[async_sessionmaker[AsyncSession]] = None

    def init(self, database_url: str = None, echo: bool = None):
        """
        Инициализация подключения к БД.
        Должна вызываться при старте приложения.
        """
        database_url = database_url or settings.DATABASE_URL
        echo = echo if echo is not None else settings.DATABASE_ECHO

        # Создаем асинхронный движок
        self.engine = create_async_engine(
            database_url,
            echo=echo, # Логирование SQL запросов
            future=True,  # Использовать новые возможности SQLAlchemy 2.0
            pool_size=20, # Размер пула соединений
            max_overflow=20,  # Максимальное количество соединений сверх pool_size
            pool_pre_ping=True,  # Проверка соединения перед использованием
            pool_recycle=3600   # Переиспользовать соединения каждый час
        )

        self.async_session_maker = async_sessionmaker(
            bind=self.engine,
            class_=AsyncSession,
            expire_on_commit=False,  # Не делать объекты устаревшими после commit
            autoflush=False, # Отключить autoflush (не загружать данные сразу)
        )

    async def close(self):
        """Закрытие всех подключений"""
        if self.engine:
            await self.engine.dispose()

    @contextlib.asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Контекстный менеджер для получения сессии БД.
        Сессия автоматически закрывается после использования.

        Пример:
            async with db_manager.session() as session:
                result = await session.execute(...)
        """

        if not self.async_session_maker:
            raise RuntimeError("Database manager не инициализирован. Вызовите init(")
        async with self.async_session_maker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Зависимость для FastAPI для получения сессии БД.
        Используется с Depends().
        """
        async with self.session() as session:
            yield session

db_manager = DataBaseManager()

# Функция для инициализации экземпляра менеджера БД
async def init_db():
    """Инициализация базы данных при старте приложения."""
    db_manager.init()

    # В разработке можно создавать таблицы автоматически
    if settings.DATABASE_ECHO: # Только в dev режиме
        from app.models.base import Base
        async with db_manager.engine.begin() as conn:
            # Создаем все таблицы (в продакшен используем миграции
            await conn.run_sync(Base.metadata.create_all)
