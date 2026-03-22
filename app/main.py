"""
Точка входа в FastAPI приложение.
"""
from fastapi import FastAPI
from contextlib import asynccontextmanager
import logging

from app.core.config import settings
from app.core.database import db_manager, init_db
# from app.core.database import init_db  # Пока закомментируем, создадим позже

# Настройка логирования (можно заменить на loguru позже)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Управляет жизненным циклом приложения.
    Выполняется при старте и завершении работы.
    """
    # Startup
    logger.info("🚀 Запуск приложения...")
    logger.info(f"Режим: {'разработка' if settings.DATABASE_ECHO else 'продакшн'}")

    # Инициализация подключений к БД (будет позже)
    await init_db()
    logger.info("✅ База данных инициализирована")
    yield

    # Shutdown
    logger.info("🛑 Завершение работы приложения...")
    await db_manager.close()
    logger.info("✅ Соединения с БД закрыты")


# Создаем экземпляр FastAPI
app = FastAPI(
    title="Secure Messenger API",
    description="Безопасный мессенджер с сквозным шифрованием",
    version="0.1.0",
    lifespan=lifespan,
    # Документация будет доступна по адресу /docs
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)


@app.get("/")
async def root():
    """Корневой эндпоинт для проверки работы API."""
    return {
        "message": "Secure Messenger API",
        "version": "0.1.0",
        "status": "running",
        "database": "connected",
        "docs": "/api/docs"
    }


@app.get("/health")
async def health_check():
    """Проверка здоровья сервиса."""
    # Проверяем подключение к БД
    try:
        async with db_manager.session() as session:
            await session.execute("SELECT 1")
        db_status = "healthy"
    except Exception as e:
        db_status = f"unhealthy: {e}"

    return {
        "status": "healthy",
        "database": db_status,
        "version": "0.1.0"
    }

# Здесь позже подключим роутеры
# app.include_router(auth_router, prefix="/api/v1/auth", tags=["Authentication"])