"""
Модели для премиум-подписок и платежей.
"""
from __future__ import annotations
from datetime import datetime
from sqlalchemy import ForeignKey, String, Numeric, Enum as SQLEnum, Index, DateTime, func, JSON, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional, TYPE_CHECKING
import enum

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User

class SubscriptionPlan(str, enum.Enum):
    """Тарифные планы."""
    MONTHLY = "monthly"     # 1 месяц
    QUARTERLY = "quarterly" # 3 месяца
    YEARLY = "yearly"       # 12 месяцев
    LIFETIME = "lifetime"   # Навсегда (ограниченное предложение)

class PaymentStatus(str, enum.Enum):
    """Статус платежа."""
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    REFUNDED = "refunded"
    CANCELLED = "cancelled"

class PaymentProvider(str, enum.Enum):
    """Платежный провайдер."""
    YOOKASSA = "yookassa"
    STRIPE = "stripe"
    APPLE = "apple"
    GOOGLE = "google"


class Subscription(Base, TimestampMixin):
    """
    Модель премиум-подписки пользователя.
    """
    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="ID пользователя"
    )

    plan: Mapped[SubscriptionPlan] = mapped_column(
        SQLEnum(SubscriptionPlan),
        nullable=False,
        comment="Тарифный план"
    )

    starts_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Дата начала подписки"
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="Дата окончания подписки"
    )

    auto_renew: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Автоматическое продление"
    )

    cancelled_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Дата отмены автопродления"
    )

    # Отношения
    user: Mapped["User"] = relationship(
        "User",
        back_populates="subscriptions"
    )

    payments: Mapped[list["Payment"]] = relationship(
        "Payment",
        back_populates="subscription",
        cascade="all, delete-orphan"
    )

    @property
    def is_active(self) -> bool:
        """Проверка активна ли подписка."""
        now = datetime.now(self.expires_at.tzinfo)
        return self.expires_at > now and not self.cancelled_at

    __table_args__ = (
        Index('ix_subscriptions_user_active', 'user_id', 'expires_at'),
        Index('ix_subscriptions_expires', 'expires_at'),
    )


class Payment(Base, TimestampMixin):
    """
    Модель платежа.
    """
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="ID пользователя"
    )

    subscription_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("subscriptions.id"),
        nullable=True,
        comment="ID подписки (если есть)"
    )

    amount: Mapped[float] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        comment="Сумма в рублях"
    )

    currency: Mapped[str] = mapped_column(
        String(3),
        default="RUB",
        nullable=False,
        comment="Валюта"
    )

    provider: Mapped[PaymentProvider] = mapped_column(
        SQLEnum(PaymentProvider),
        nullable=False,
        comment="Платежный провайдер"
    )

    provider_payment_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="ID платежа у провайдера"
    )

    status: Mapped[PaymentStatus] = mapped_column(
        SQLEnum(PaymentStatus),
        default=PaymentStatus.PENDING,
        nullable=False,
        comment="Статус платежа"
    )

    description: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Описание покупки"
    )

    receipt_url: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="URL чека"
    )


    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Дата завершения платежа"
    )

    # Отношения
    user: Mapped["User"] = relationship(
        "User",
        foreign_keys=[user_id]
    )

    subscription: Mapped[Optional["Subscription"]] = relationship(
        "Subscription",
        back_populates="payments"
    )

    __table_args__ = (
        Index('ix_payments_user_status', 'user_id', 'status'),
        Index('ix_payments_provider_id', 'provider', 'provider_payment_id'),
        Index('ix_payments_completed', 'completed_at'),
    )