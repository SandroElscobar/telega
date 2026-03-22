"""
Модели для чатов и участников.
"""
from __future__ import annotations
from datetime import datetime

from sqlalchemy import String, Boolean, ForeignKey, Integer, Enum as SQLEnum, Text, DateTime, func, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional, List, TYPE_CHECKING
import enum

from app.models.base import Base, TimestampMixin, SoftDeleteMixin

# Импортируем типы только для проверки типов
if TYPE_CHECKING:
    from app.models.user import User
    from app.models.message import Message

class ChatType(str, enum.Enum):
    """Тип чата"""
    PRIVATE = "private"
    GROUP = "group"
    CHANNEL = "channel"


class Chat(Base, TimestampMixin, SoftDeleteMixin):
    """
    Модель чата (личный, групповой или канал).
    """
    __tablename__ = "chats"
    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

    chat_type: Mapped[ChatType] = mapped_column(
        SQLEnum(ChatType),
        nullable=False,
        comment="Тип чата"
    )

    title: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="Название чата (для групп и каналов)"
    )

    description: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="Описание чата (для групп и каналов)"
    )

    avatar_url: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="URL аватара чата"
    )

    created_by_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
        comment="ID пользователя, создавшего чат"
    )

    encryption_key: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Зашифрованный ключ группы (для групповых чатов)"
    )

    encryption_salt: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        comment="Соль для производных ключей группы"
    )

    #Настройки

    is_public: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Публичный ли чат (можно найти через поиск)"
    )

    join_link: Mapped[Optional[str]] = mapped_column(
        String(255),
        unique=True,
        nullable=True,
        comment="Ссылка-приглашение в чат"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=func.now(),  # при создании
        onupdate=func.now()
    )

    # Отношения
    created_by: Mapped["User"] = relationship(
        "User",
        back_populates="created_chat",
        foreign_keys=[created_by_id],
    )

    participants: Mapped[List["ChatParticipant"]] = relationship(
        "ChatParticipant",
        back_populates="chat",
        cascade="all, delete-orphan",
        lazy="selectin"
    )

    messages: Mapped[List["Message"]] = relationship(
        "Message",
        back_populates="chat",
        cascade="all, delete-orphan",
        lazy="selectin"
    )

class ParticipantRole(str, enum.Enum):
    """Роль участников чата"""
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    BANNED = "banned"

class ChatParticipant(Base, TimestampMixin):
    """Модели участника чата (связующая таблица многие-ко-многим"""
    __tablename__ = "chat_participants"
    id: Mapped[int] = mapped_column(
        primary_key=True,
    )
    chat_id: Mapped[int] = mapped_column(
        ForeignKey("chats.id", ondelete="CASCADE"),
        nullable=False,
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    role: Mapped[ParticipantRole] = mapped_column(
        SQLEnum(ParticipantRole),
        default=ParticipantRole.MEMBER,
        nullable=False,
        comment="Роль участника"
    )

    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Время присоединения к чату"
    )

    last_read_message_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="ID последнего прочитанного сообщения"
    )

    muted_until: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="До какого времени отключены уведомления (NULL = не отключены)"
    )

    # Для E2EE в групповых чатах
    group_key_encrypted: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Ключ группы, зашифрованный публичным ключом пользователя"
    )

    # Отношения
    chat: Mapped["Chat"] = relationship(
        "Chat",
        back_populates="participants"
    )
    user: Mapped["User"] = relationship(
        "User",
        back_populates="chat_participants"
    )

    __table_args__ = (
        # Уникальность пары (чат, пользователь)
        UniqueConstraint('chat_id', 'user_id', name='uix_chat_participant'),
        Index('ix_chat_participants_user_id', 'user_id'),
        Index('ix_chat_participants_chat_id', 'chat_id'),
    )
