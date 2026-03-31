"""
Модель сообщения с поддержкой сквозного шифрования (E2EE).
"""
from __future__ import annotations
from datetime import datetime
from sqlalchemy import String, Boolean, ForeignKey, Integer, Text, JSON, BigInteger, Enum as SQLEnum, Index, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional, Dict, Any, TYPE_CHECKING, List
import enum

from app.models.base import Base, TimestampMixin, SoftDeleteMixin

# Импортируем типы только для проверки типов
if TYPE_CHECKING:
    from app.models.user import User
    from app.models.chat import Chat
    from app.models.reaction import Reaction
    from app.models.moderation_log import ModerationStatus

class MessageType(str, enum.Enum):
    """Тип сообщения."""
    TEXT = "text"
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    FILE = "file"
    LOCATION = "location"
    CONTACT = "contact"
    STICKER = "sticker"
    SERVICE = "service"

class MessageStatus(str, enum.Enum):
    """Статус сообщения"""
    SENT = "sent"                 # Отправлено на сервер
    DELIVERED = "delivered"       # Доставлено получателю
    READ = "read"                 # Прочитано
    FAILED = "failed"             # Ошибка отправки

class Message(Base, TimestampMixin, SoftDeleteMixin):
    """
    Модель сообщения.

    Особенности E2EE:
    - Содержимое сообщения (encrypted_content) хранится в зашифрованном виде
    - Ключи шифрования никогда не хранятся на сервере
    - IV (вектор инициализации) хранится отдельно для каждого сообщения
    - Медиафайлы также шифруются перед загрузкой
    """

    __tablename__ = "messages"
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    # Связи
    chat_id: Mapped[int] = mapped_column(
        ForeignKey("chats.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    sender_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True, # NULL если пользователь удален
        index=True,
    )

    # Тип и статус
    message_type: Mapped[MessageType] = mapped_column(
        SQLEnum(MessageType, values_callable=lambda x: [e.value for e in x]),
        default=MessageType.TEXT,
        nullable=False,
    )

    status: Mapped[MessageStatus] = mapped_column(
        SQLEnum(MessageStatus),
        default=MessageStatus.SENT,
        nullable=False
    )

    encrypted_content: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Зашифрованное содержимое сообщения (base64)"
    )

    content_nonce: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        comment="Nonce/IV для расшифровки (base64)"
    )

    # Для сообщения с медиа
    media_url: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="URL медиафайла (сам файл тоже зашифрован)"
    )
    media_encrypted_key: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Ключ для расшифровки медиа, зашифрованный публичным ключом получателя"
    )

    media_iv: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        comment="Nonce для расшифровки медиа"
    )

    media_size: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Размер медиафайла в байтах"
    )

    media_mime_type: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="MIME тип медиафайла"
    )
    # Метаданные (не шифруются, нужны для поиска/фильтрации)
    meta: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
        comment="Публичные метаданные (не шифруются)"
    )

    service_action: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Тип служебного действия"
    )

    # Для ответов на сообщения
    reply_to_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("messages.id"),
        nullable=True,
        comment="ID сообщения, на которое отвечаем"
    )

    forwarded_from_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        nullable=True,
        comment="ID оригинального сообщения (если переслано)"
    )

    is_pinned: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Закреплено ли сообщение"
    )

    pinned_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
        comment="Кто закрепил сообщение"
    )

    pinned_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Когда было закреплено"
    )

    reactions_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Количество реакций (денормализация)"
    )

    edit_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Количество правок сообщения"
    )

    edited_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Время последней правки"
    )

    # ========== ПОЛЯ МОДЕРАЦИИ (ДОБАВЛЕНЫ) ==========

    # Статус модерации
    moderation_status: Mapped[ModerationStatus] = mapped_column(
        SQLEnum(ModerationStatus),
        default=ModerationStatus.PENDING,
        nullable=False,
        index=True,
        comment="Статус модерации сообщения"
    )

    # Причина модерации (если заблокировано или удалено)
    moderation_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Причина блокировки/удаления сообщения"
    )

    # Код причины для автоматической обработки
    moderation_reason_code: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Код причины модерации (например: 'spam', 'abuse', 'nsfw')"
    )

    # Кто провел модерацию (ID модератора или 0 для автоматической)
    moderated_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
        comment="ID модератора, который провел модерацию"
    )

    # Время модерации
    moderated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Время проведения модерации"
    )

    # Связанный лог модерации
    moderation_log_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("moderation_logs.id"),
        nullable=True,
        comment="ID записи в логе модерации"
    )

    # Количество жалоб на сообщение
    reports_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Количество жалоб на сообщение"
    )

    # Автоматическая модерация
    auto_moderated: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Было ли сообщение обработано автоматической модерацией"
    )

    # Оценка AI/автоматической модерации (0-1)
    moderation_score: Mapped[Optional[float]] = mapped_column(
        default=0.0,
        nullable=True,
        comment="Оценка риска от AI модерации (0-1)"
    )

    # Признак, что сообщение прошло AI проверку
    ai_checked: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Проверено ли сообщение AI"
    )

    # Время AI проверки
    ai_checked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Время AI проверки"
    )

    # Для обжалования
    appeal_status: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Статус обжалования (pending, approved, rejected)"
    )

    appeal_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Причина обжалования"
    )

    appeal_created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Время создания обжалования"
    )

    appeal_resolved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Время разрешения обжалования"
    )

    appeal_resolved_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
        comment="Кто разрешил обжалование"
    )

    # ========== ОСТАЛЬНЫЕ ПОЛЯ ==========


    # Отношения
    chat: Mapped["Chat"] = relationship(
        "Chat",
        back_populates="messages",
        foreign_keys=[chat_id]
    )
    sender: Mapped["User"] = relationship(
        "User",
        foreign_keys=[sender_id],
        back_populates="send_messages"
    )

    reply_to: Mapped["Message"] = relationship(
        "Message",
        remote_side=[id],
        foreign_keys=[reply_to_id],
        back_populates="replies"
    )
    replies: Mapped[list["Message"]] = relationship(
        "Message",
        foreign_keys=[reply_to_id],
        back_populates="reply_to"
    )

    reactions: Mapped[List["Reaction"]] = relationship(
        "Reaction",
        back_populates="message",
        cascade="all, delete-orphan"
    )

    pinned_by: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[pinned_by_id]
    )

    # Индексы для быстрого поиска
    __table_args__ = (
        Index('ix_messages_chat_created', 'chat_id', 'created_at'),
        Index('ix_messages_sender_status', 'sender_id', 'status'),
        Index('ix_messages_status_created', 'status', 'created_at'),
    )

    @property
    def is_service_message(self) -> bool:
        """Проверка, является ли сообщение служебным."""
        return self.message_type == MessageType.SERVICE

    @property
    def has_media(self) -> bool:
        """Проверка, есть ли у сообщения медиавложение."""
        return self.media_url is not None