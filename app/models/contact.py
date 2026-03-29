"""
Модель для контактов пользователя.
"""
from sqlalchemy import ForeignKey, UniqueConstraint, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional, TYPE_CHECKING

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User

class Contact(Base, TimestampMixin):
    """
    Модель контакта пользователя.
    Связывает пользователя с его контактами из телефонной книги.
    """
    __tablename__ = "contacts"
    id: Mapped[int] = mapped_column(primary_key=True, )

    user_id: Mapped[int] = mapped_column(
        ForeignKey('users.id', ondelete='CASCADE'),
        nullable=False,
        comment="ID владельца контакта"
    )
    contact_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        comment="ID пользователя в системе (если зарегистрирован)"
    )

    phone_number: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Номер телефона контакта"
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Имя контакта (как сохранено в телефонной книге)"
    )

    # Отношения
    user: Mapped["User"] = relationship(
        "User",
        foreign_keys=[user_id],
        back_populates="contacts"
    )

    contact_user: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[contact_user_id],
        back_populates="contact_of"
    )

    __table_args__ = (
        UniqueConstraint('user_id', 'phone_number', name='uix_user_contact_phone'),
        Index('ix_contacts_user_phone', 'user_id', 'phone_number'),
        Index('ix_contacts_contact_user_id', 'contact_user_id'),
    )
