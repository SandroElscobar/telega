"""
Модель историй (Stories) для премиум-пользователей.
"""
from __future__ import annotations
from datetime import datetime
from sqlalchemy import ForeignKey, String, Text, Integer, Enum as SQLEnum, Index, DateTime, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional, TYPE_CHECKING, List
import enum

from app.models.base import Base, TimestampMixin, SoftDeleteMixin

if TYPE_CHECKING:
    from app.models.user import User

class StoryType(str, enum.Enum):
    """Тип истории."""
    PHOTO = "photo"
    VIDEO = "video"
    TEXT = "text"

class StoryPrivacy(str, enum.Enum):
    """Приватность истории."""
    PUBLIC = "public"       # Все видят
    CONTACTS = "contacts"   # Только контакты
    CLOSE_FRIENDS = "close" # Только близкие друзья
    PRIVATE = "private"     # Только выбранные пользователи


class Story(Base, TimestampMixin, SoftDeleteMixin):
    """
    Модель истории (Stories).
    Доступна только для премиум-пользователей.
    """
    __tablename__ = "stories"

    id: Mapped[int] = mapped_column(primary_key=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="ID автора истории"
    )

    story_type: Mapped[StoryType] = mapped_column(
        SQLEnum(StoryType),
        nullable=False,
        comment="Тип контента"
    )

    # Контент
    media_url: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="URL медиафайла"
    )

    thumbnail_url: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="URL миниатюры"
    )

    text_content: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Текстовое содержимое (для текстовых историй)"
    )

    # Шифрование (E2EE для премиум-контента)
    encrypted_content: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Зашифрованное содержимое"
    )

    content_nonce: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        comment="Nonce для расшифровки"
    )

    # Метаданные
    duration: Mapped[int] = mapped_column(
        Integer,
        default=5,
        nullable=False,
        comment="Длительность в секундах"
    )

    privacy: Mapped[StoryPrivacy] = mapped_column(
        SQLEnum(StoryPrivacy),
        default=StoryPrivacy.PUBLIC,
        nullable=False,
        comment="Уровень приватности"
    )

    allowed_user_ids: Mapped[Optional[List[int]]] = mapped_column(
        JSON,
        nullable=True,
        comment="Список ID пользователей, которым доступна история (для PRIVATE)"
    )

    # Статистика
    views_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Количество просмотров"
    )

    reactions_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Количество реакций"
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="Дата истечения (через 24 часа после создания)"
    )

    # Отношения
    user: Mapped["User"] = relationship(
        "User",
        back_populates="stories"
    )

    views: Mapped[List["StoryView"]] = relationship(
        "StoryView",
        back_populates="story",
        cascade="all, delete-orphan"
    )

    reactions: Mapped[List["StoryReaction"]] = relationship(
        "StoryReaction",
        back_populates="story",
        cascade="all, delete-orphan"
    )

    @property
    def is_active(self) -> bool:
        """Проверка, активна ли история."""
        now = datetime.now(self.expires_at.tzinfo)
        return self.expires_at > now and not self.is_deleted

    __table_args__ = (
        Index('ix_stories_user_active', 'user_id', 'expires_at'),
        Index('ix_stories_expires', 'expires_at'),
    )


class StoryView(Base, TimestampMixin):
    """
    Модель просмотра истории.
    """
    __tablename__ = "story_views"

    id: Mapped[int] = mapped_column(primary_key=True)

    story_id: Mapped[int] = mapped_column(
        ForeignKey("stories.id", ondelete="CASCADE"),
        nullable=False,
        comment="ID истории"
    )

    viewer_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="ID пользователя, посмотревшего историю"
    )

    # Отношения
    story: Mapped["Story"] = relationship(
        "Story",
        back_populates="views"
    )

    viewer: Mapped["User"] = relationship(
        "User",
        foreign_keys=[viewer_id]
    )

    __table_args__ = (
        UniqueConstraint('story_id', 'viewer_id', name='uix_story_view'),
        Index('ix_story_views_story', 'story_id'),
    )


class StoryReaction(Base, TimestampMixin):
    """
    Модель реакции на историю.
    """
    __tablename__ = "story_reactions"

    id: Mapped[int] = mapped_column(primary_key=True)

    story_id: Mapped[int] = mapped_column(
        ForeignKey("stories.id", ondelete="CASCADE"),
        nullable=False,
        comment="ID истории"
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="ID пользователя"
    )

    emoji: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Эмодзи реакции"
    )

    # Отношения
    story: Mapped["Story"] = relationship(
        "Story",
        back_populates="reactions"
    )

    user: Mapped["User"] = relationship(
        "User",
        foreign_keys=[user_id]
    )

    __table_args__ = (
        UniqueConstraint("story_id", "user_id", name='uix_story_reactions_unique'),
    )

