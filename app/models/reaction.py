"""
Модель реакции на сообщение.
"""
from sqlalchemy import ForeignKey, UniqueConstraint, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import TYPE_CHECKING

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.message import Message

class Reaction(Base, TimestampMixin):
    """
    Модель реакции на сообщение (лайк, сердечко и т.д.)
    """
    __tablename__ = "reactions"
    id: Mapped[int] = mapped_column(primary_key=True)
    message_id: Mapped[int] = mapped_column(
        ForeignKey("messages.id", ondelete="CASCADE"),
        nullable=False,
        comment="ID сообщения"
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="ID пользователя, поставившего реакцию"
    )
    emoji: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Эмодзи реакции (например, '❤️', '👍', '😂')"
    )

    # Отношения
    message: Mapped["Message"] = relationship(
        "Message",
        back_populates="reactions"
    )

    user: Mapped["User"] = relationship(
        "User",
        foreign_keys=[user_id]
    )

    __table_args__ = (
        UniqueConstraint('message_id', 'user_id', name='uix_message_user_reaction'),
        Index('ix_reactions_message_emoji', 'message_id', 'emoji'),
        Index('ix_reactions_user_id', 'user_id'),
    )