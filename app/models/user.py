"""
Модель пользователя.
"""
from __future__ import annotations
from datetime import datetime


from sqlalchemy import String, Boolean, Enum as SQLEnum, DateTime, Text, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional, List, TYPE_CHECKING
import enum
import re

from app.models.base import Base, TimestampMixin, SoftDeleteMixin

if TYPE_CHECKING:
    from app.models.message import Message
    from app.models.chat import Chat, ChatParticipant
    from app.models.contact import Contact
    from app.models.report import Report
    from app.models.sticker import StickerPack
    from app.models.story import Story
    from app.models.subscription import Subscription

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
    phone_number:Mapped[str] = mapped_column(
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

    is_online:Mapped[bool] = mapped_column(
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

    push_token: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Токен для push-уведомлений (FCM)"
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

    is_premium: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Флаг премиум-аккаунта"
    )

    premium_until: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Дата окончания премиум-подписки"
    )

    can_be_found_by_phone: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Можно ли найти пользователя по номеру телефона"
    )

    show_phone_number: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Показывать ли номер телефона в профиле"
    )

    show_last_seen: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Показывать ли время последней активности"
    )

    # Настройки чата
    auto_download_media: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Автоматически загружать медиа"
    )
    auto_download_media_mobile: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Автозагрузка медиа в мобильной сети"
    )

    # Удаление аккаунта
    deletion_scheduled_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Дата запланированного удаления аккаунта"
    )

    deletion_reason: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Причина удаления аккаунта"
    )
    is_deleted: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment=" Удален ли пользователь"
    )


    # Отношения с другими таблицами
    send_messages: Mapped[List["Message"]] = relationship(
        "Message",
        back_populates="sender",
        foreign_keys="[Message.sender_id]",
        cascade="all, delete-orphan",
        lazy = "selectin"
    )

    chat_participants: Mapped[list["ChatParticipant"]] = relationship(
        "ChatParticipant",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin"
    )

    chats: Mapped[List["Chat"]] = relationship(
        "Chat",
        secondary="chat_participants",
        overlaps="chat_participants",  # указываем, что это отношение перекрывается с chat_participants
        viewonly=True,  # или False, если хотите изменять через user.chats
        lazy="selectin"
    )

    created_chat: Mapped[List["Chat"]] = relationship(
        "Chat",
        back_populates="created_by",
        foreign_keys="[Chat.created_by_id]",
        cascade="all, delete-orphan",
        lazy="selectin"
    )

    # Связь "пользователь -> его контакты"
    # Пользователь добавляет других пользователей в свой список контактов
    # При удалении пользователя все его контакты также удаляются (cascade="all, delete-orphan")
    contacts: Mapped[List["Contact"]] = relationship(
        "Contact",
        foreign_keys="Contact.user_id",
        back_populates="user",
        cascade="all, delete-orphan"
    )

    # Обратная связь "кто добавил текущего пользователя в контакты"
    # Показывает, в чьих списках контактов находится данный пользователь
    contact_of: Mapped[List["Contact"]] = relationship(
        "Contact",
        foreign_keys="Contact.contact_user_id",
        back_populates="contact_user"
    )

    # Репорты (жалобы), созданные пользователем
    # Пользователь может пожаловаться на других пользователей или контент
    reports: Mapped[List["Report"]] = relationship(
        "Report",
        foreign_keys="Report.reporter_id",
        back_populates="reporter"
    )

    # Репорты (жалобы), созданные на пользователя
    # Показывает, сколько раз и кем был пожалован данный пользователь
    reports_on_me: Mapped[List["Report"]] = relationship(
        "Report",
        foreign_keys="Report.reported_user_id",
        back_populates="reported_user"
    )

    owned_sticker_packs: Mapped[List["StickerPack"]] = relationship(
        "StickerPack",
        foreign_keys="StickerPack.owner_id",
        back_populates="owner"
    )

    # Истории (сторис), созданные пользователем
    # Пользователь может публиковать множество историй
    stories: Mapped[List["Story"]] = relationship(
        "Story",
        back_populates="user"
    )

    # Подписки пользователя
    # Например, подписки на премиум-доступ, уведомления и т.д.
    subscriptions: Mapped[List["Subscription"]] = relationship(
        "Subscription",
        back_populates="user"
    )

    owned_sticker_packs: Mapped[List["StickerPack"]] = relationship(back_populates="owner")

    # Индексы
    __table_args__ = (
        Index('ix_users_deletion_scheduled', 'deletion_scheduled_at'),
        Index('ix_users_premium_until', 'premium_until'),
    )


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






