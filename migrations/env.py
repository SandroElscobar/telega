import asyncio
from logging.config import fileConfig
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# Добавляем путь к проекту
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

# Импортируем настройки и модели
from app.core.config import settings
from app.models.base import Base
from app.models.user import User
from app.models.chat import Chat, ChatParticipant
from app.models.message import Message

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
target_metadata = Base.metadata

# Устанавливаем URL базы данных из настроек
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL.replace("+asyncpg", ""))
# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    # Для оффлайн режима убираем +asyncpg из URL
    url = settings.DATABASE_URL.replace("+asyncpg", "")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode using SYNCHRONOUS database driver.

    This is the correct approach for Alembic migrations:
    - Uses synchronous psycopg2 driver (not asyncpg)
    - Removes +asyncpg from the connection URL
    - Creates a synchronous engine specifically for migrations

    """
    # Берем URL без asyncpg для синхронного подключения
    # postgresql+asyncpg://... -> postgresql://...
    sync_url = settings.DATABASE_URL.replace("+asyncpg", "")

    # Переопределяем URL в конфигурации Alembic
    config.set_main_option("sqlalchemy.url", sync_url)

    # Создаем синхронный движок для миграций
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
