"""
Модель для жалоб на контент.
"""
from __future__ import annotations
from datetime import datetime
from sqlalchemy import ForeignKey, Text, String, Enum as SQLEnum, Index, DateTime, JSON, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional, TYPE_CHECKING
import enum

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.message import Message
    from app.models.chat import Chat

class ReportType(str, enum.Enum):
    """Тип жалобы."""
    SPAM = "spam"                   # Спам
    ABUSE = "abuse"                 # Оскорбления/домогательства
    ILLEGAL_CONTENT = "illegal"     # Незаконный контент
    EXTREMISM = "extremism"         # Экстремизм (согласно 114-ФЗ)
    DRUGS = "drugs"                 # Наркотики (согласно 3-ФЗ)
    LGBT_PROPAGANDA = "lgbt"        # ЛГБТ-пропаганда (согласно 483-ФЗ)
    VIOLENCE = "violence"           # Насилие
    OTHER = "other"                 # Другое

class ReportStatus(str, enum.Enum):
    """Статус обработки жалобы."""
    PENDING = "pending"             # На рассмотрении
    IN_REVIEW = "in_review"         # В процессе проверки
    APPROVED = "approved"           # Жалоба обоснована
    REJECTED = "rejected"           # Жалоба отклонена
    AUTO_MODERATED = "auto"         # Автоматически обработано

class ReportTargetType(str, enum.Enum):
    """Тип объекта жалобы."""
    MESSAGE = "message"
    CHAT = "chat"
    USER = "user"
    STORY = "story"


class Report(Base, TimestampMixin):
    """
    Модель жалобы на контент.
    Используется для модерации согласно законодательству РФ.
    """
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Кто пожаловался
    reporter_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="ID пользователя, подавшего жалобу"
    )

    # На что жалуемся
    target_type: Mapped[ReportTargetType] = mapped_column(
        SQLEnum(ReportTargetType),
        nullable=False,
        comment="Тип объекта жалобы"
    )

    target_id: Mapped[int] = mapped_column(
        nullable=False,
        comment="ID объекта жалобы"
    )

    # Если жалоба на сообщение
    message_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("messages.id", ondelete="SET NULL"),
        nullable=True,
        comment="ID сообщения (если жалоба на сообщение)"
    )

    # Если жалоба на чат
    chat_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("chats.id", ondelete="SET NULL"),
        nullable=True,
        comment="ID чата (если жалоба на чат)"
    )

    # Если жалоба на пользователя
    reported_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="ID пользователя, на которого жалуются"
    )

    # Содержание жалобы
    report_type: Mapped[ReportType] = mapped_column(
        SQLEnum(ReportType),
        nullable=False,
        comment="Тип нарушения"
    )

    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Дополнительное описание (макс. 500 символов)"
    )

    evidence: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="Дополнительные доказательства (скриншоты, ссылки)"
    )

    # Статус обработки
    status: Mapped[ReportStatus] = mapped_column(
        SQLEnum(ReportStatus),
        default=ReportStatus.PENDING,
        nullable=False,
        comment="Статус обработки жалобы"
    )

    # Модерация
    moderator_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
        comment="ID модератора, обработавшего жалобу"
    )

    moderator_note: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Заметки модератора"
    )

    action_taken: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Принятое действие (удалено, заблокировано, предупреждение)"
    )

    resolved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Дата обработки жалобы"
    )

    # Автоматическая модерация
    auto_moderated: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Обработано автоматически"
    )

    auto_moderation_score: Mapped[Optional[float]] = mapped_column(
        default=0.0,
        nullable=True,
        comment="Оценка AI-модерации (0-1)"
    )

    # Отношения
    reporter: Mapped["User"] = relationship(
        "User",
        foreign_keys=[reporter_id],
        back_populates="reports"
    )

    reported_user: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[reported_user_id],
        back_populates="reports_on_me"
    )

    message: Mapped[Optional["Message"]] = relationship(
        "Message",
        foreign_keys=[message_id]
    )

    chat: Mapped[Optional["Chat"]] = relationship(
        "Chat",
        foreign_keys=[chat_id]
    )

    moderator: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[moderator_id]
    )

    __table_args__ = (
        Index('ix_reports_status_created', 'status', 'created_at'),
        Index('ix_reports_target', 'target_type', 'target_id'),
        Index('ix_reports_reporter', 'reporter_id', 'status'),
        Index('ix_reports_moderator', 'moderator_id', 'resolved_at'),
    )