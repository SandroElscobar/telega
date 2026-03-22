"""
Базовые классы для всех SQLAlchemy моделей.
"""

from datetime import datetime
from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from typing import Optional

class Base(DeclarativeBase):
    """
    Базовый класс для всех моделей.
    Все модели будут наследоваться от него.
    """
    pass

class TimestampMixin:
    """
    Миксин для добавления полей created_at и updated_at.
    """
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Дата и время создания записи"
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment='Дата и время последнего обновления'
    )

class SoftDeleteMixin:
    """
    Миксин для "мягкого" удаления (пометка записи как удаленной, без физического удаления).
    """
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="Дата и время удаления (если не NULL - запись считается удаленной)"
    )
    @property
    def is_deleted(self) -> bool:
        """Проверка, удалена ли запись."""
        return self.deleted_at is not None