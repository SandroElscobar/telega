"""
Модель пользователя.
"""
from datetime import datetime


from sqlalchemy import String, Boolean, Enum as SQLEnum, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional, List
import enum
import re

from app.models.base import Base, TimestampMixin, SoftDeleteMixin

class UserStatus(str, enum.Enum):
    """Статус пользователя в системе."""
    ACTIVE = 'active'
    INACTIVE = 'inactive'
    BLOCKED = 'blocked'
    WAITING_VERIFICATION = 'waiting_verification'

class User(Base, TimestampMixin, SoftDeleteMixin):
    """
    Модель пользователя мессенджера.

    Особенности безопасности:
    - Пароль хранится в виде хеша (Argon2)
    - Номер телефона может использоваться для 2FA
    - Поле public_key для E2EE (публичный ключ пользователя)
    - Поле e2ee_salt для производных ключей
    """
    __tablename__ = 'users'
    id:Mapped[int] = mapped_column(primary_key=True, index=True)
    phone_number:Mapped[int] = mapped_column(
        String(20),
        unique=True,
        index=True,
        nullable=False,
        comment="Номер телефона в международном формате (например, +79001234567)"
    )
    phone_number_verified:Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Подтвержден ли номер телефона"
    )

    username: Mapped[Optional[str]] = mapped_column(
        String(50),
        unique=True,
        index=True,
        nullable=False,
        comment="Уникальное имя пользователя (может быть не задано)"
    )

    full_name:Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment='Полное имя пользователя'
    )

    bio: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="Биография или описание профиля."
    )

    # Аутентификация

    hashed_password:Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Хеш пароля (Argon2). Может быть null для OAuth/SSO"
    )

    # Статус

    status:Mapped[UserStatus] = mapped_column(
        SQLEnum(UserStatus),
        default=UserStatus.WAITING_VERIFICATION,
        nullable=False,
        comment="Текущий статус учетной записи"
    )

    is_online:Mapped[Optional[datetime]] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Флаг онлайн/офлайн"
    )

    last_seen_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Последнее время активности."
    )

    # E2EE (сквозное шифрование)
    public_key:Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Публичный ключ пользователя для E2EE (в формате PEM"
    )

    e2ee_salt: Mapped[Optional[str]]= mapped_column(
        String(64),
        nullable=True,
        comment="Соли для производных ключей (hex"
    )

    signed_pre_key: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Подписанный предварительный ключ для E2EE"
    )

    push_token_update_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Время последнего обновления токена push-уведомлений"
    )

    language_code: Mapped[str] = mapped_column(
        String(10),
        default="en",
        nullable=False,
        comment="Код языка пользователя"
    )

    theme: Mapped[str] = mapped_column(
        String(20),
        default="light",
        nullable=False,
        comment="Тема оформления (light/dark/system)"
    )

    notifications_enabled: Mapped [ bool ] = mapped_column (
        Boolean,
        default=True,
        nullable=False,
        comment="Включены ли уведомления"
    )

    # Отношения с другими таблицами
    # send_messages: Mapped[List["Message"]] = relationship(
    #     back_populates="sender",
    #     foreign_keys="Message.sender_id"
    # )
    #
    # receive_messages: Mapped[List["Message"]] = relationship(
    #     back_populates="receiver",
    #     foreign_keys="[Message.receiver_id]"
    # )
    #
    # chats: Mapped[List["ChatParticipant"]] = relationship(
    #     back_populates="user"
    # )

    def __repr__(self) -> str:
        return f"<User (id = {self.id}, phone = {self.phone_number}, username = {self.username})>"
    #
    @property
    def is_active(self)->bool:
        """Проверяет, что данный user является пользователь активным"""
        return self.status == UserStatus.ACTIVE and not self.is_deleted

    @property
    def is_verified(self) -> bool:
        """Проверка подтвердил телефон?"""
        return self.phone_number_verified

    @staticmethod
    def normalize_phone_number(phone: str):
        """Приведение номеров к единому формат"""
        # Удаление всех символов кроме цифр и знаков плюса (+)
        cleaned = re.sub(r'[^\d\+]', '', phone)
        # Если номер без +, добавляем +
        if not cleaned.startswith('+'):
            cleaned = '+' + cleaned

        return cleaned






