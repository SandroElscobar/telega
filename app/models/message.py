"""
Модель сообщения с поддержкой сквозного шифрования (E2EE).
"""
from __future__ import annotations
from datetime import datetime
from sqlalchemy import String, Boolean, ForeignKey, Integer, Text, JSON, BigInteger, Enum as SQLEnum, Index, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional, Dict, Any, TYPE_CHECKING
import enum

from app.models.base import Base, TimestampMixin, SoftDeleteMixin

# Импортируем типы только для проверки типов
if TYPE_CHECKING:
    from app.models.user import User
    from app.models.chat import Chat

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