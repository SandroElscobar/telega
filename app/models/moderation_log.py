"""
Модель логов модерации.
"""
from __future__ import annotations
from datetime import datetime
from sqlalchemy import ForeignKey, String, Text, Enum as SQLEnum, JSON, Index, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional, TYPE_CHECKING
import enum

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class ModerationAction(str, enum.Enum):
    """Действия модератора."""
    BAN_USER = "ban_user"  # Блокировка пользователя
    UNBAN_USER = "unban_user"  # Разблокировка пользователя
    DELETE_MESSAGE = "delete_message"  # Удаление сообщения
    DELETE_CHAT = "delete_chat"  # Удаление чата
    WARN_USER = "warn_user"  # Предупреждение пользователю
    MUTE_USER = "mute_user"  # Мут пользователя
    UNMUTE_USER = "unmute_user"  # Снятие мута
    GRANT_ADMIN = "grant_admin"  # Назначение администратором
    REVOKE_ADMIN = "revoke_admin"  # Снятие прав администратора
    RESOLVE_REPORT = "resolve_report"  # Обработка жалобы
    OVERRIDE_CONTENT = "override_content"  # Принудительное изменение контента


class ModerationLog(Base):
    """
    Лог действий модераторов для аудита.
    """
    __tablename__ = "moderation_logs"

    id: Mapped[int] = mapped_column(primary_key=True)

    moderator_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="ID модератора"
    )

    action: Mapped[ModerationAction] = mapped_column(
        SQLEnum(ModerationAction),
        nullable=False,
        comment="Совершенное действие"
    )

    target_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Тип объекта (user, message, chat)"
    )

    target_id: Mapped[int] = mapped_column(
        nullable=False,
        comment="ID объекта"
    )

    reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Причина действия"
    )

    ip_address: Mapped[Optional[str]] = mapped_column(
        String(45),
        nullable=True,
        comment="IP адрес модератора"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Дата и время действия"
    )

    # Отношения
    moderator: Mapped["User"] = relationship(
        "User",
        foreign_keys=[moderator_id]
    )

    __table_args__ = (
        Index('ix_moderation_logs_moderator', 'moderator_id', 'created_at'),
        Index('ix_moderation_logs_target', 'target_type', 'target_id'),
        Index('ix_moderation_logs_action', 'action'),
    )