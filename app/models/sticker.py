"""
Модели для стикеров и стикер-паков.
"""
from __future__ import annotations
from sqlalchemy import ForeignKey, String, Boolean, Integer, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional, TYPE_CHECKING, List

from app.models.base import Base, TimestampMixin, SoftDeleteMixin

if TYPE_CHECKING:
    from app.models.user import User


class StickerPack(Base, TimestampMixin, SoftDeleteMixin):
    """
    Модель набора стикеров (стикер-пак).
    """
    __tablename__ = "sticker_packs"

    id: Mapped[int] = mapped_column(primary_key=True)

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Название набора стикеров"
    )

    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Отображаемое название"
    )

    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="ID владельца (создателя)"
    )

    cover_sticker_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="ID стикера-обложки"
    )

    is_premium: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Только для премиум-пользователей"
    )

    is_official: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Официальный набор от платформы"
    )

    stickers_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Количество стикеров в наборе"
    )

    # Отношения
    owner: Mapped["User"] = relationship(
        "User",
        foreign_keys=[owner_id],
        back_populates="owned_sticker_packs"
    )

    stickers: Mapped[List["Sticker"]] = relationship(
        "Sticker",
        back_populates="pack",
        cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index('ix_sticker_packs_owner', 'owner_id'),
        Index('ix_sticker_packs_premium', 'is_premium'),
    )


class Sticker(Base, TimestampMixin, SoftDeleteMixin):
    """
    Модель стикера.
    """
    __tablename__ = "stickers"

    id: Mapped[int] = mapped_column(primary_key=True)

    pack_id: Mapped[int] = mapped_column(
        ForeignKey("sticker_packs.id", ondelete="CASCADE"),
        nullable=False,
        comment="ID набора стикеров"
    )

    emoji: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Связанный эмодзи"
    )

    file_url: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="URL файла стикера (WebP/PNG)"
    )

    file_size: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Размер файла в байтах"
    )

    width: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Ширина"
    )

    height: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Высота"
    )

    order: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Порядок в наборе"
    )

    # Отношения
    pack: Mapped["StickerPack"] = relationship(
        "StickerPack",
        back_populates="stickers"
    )

    __table_args__ = (
        Index('ix_stickers_pack_order', 'pack_id', 'order'),
    )