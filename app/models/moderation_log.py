"""
Модель логов модерации.
"""
from __future__ import annotations
from datetime import datetime, timedelta
from sqlalchemy import ForeignKey, String, Text, Enum as SQLEnum, JSON, Index, DateTime, func, Boolean, BigInteger
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional, TYPE_CHECKING, Any, Dict
import enum
import json

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class ModerationAction(str, enum.Enum):
    """Действия модератора."""
    # Действия с пользователями
    BAN_USER = "ban_user"  # Блокировка пользователя
    UNBAN_USER = "unban_user"  # Разблокировка пользователя
    WARN_USER = "warn_user"  # Предупреждение пользователю
    MUTE_USER = "mute_user"  # Мут пользователя
    UNMUTE_USER = "unmute_user"  # Снятие мута

    # Действия с контентом
    DELETE_MESSAGE = "delete_message"  # Удаление сообщения
    DELETE_CHAT = "delete_chat"  # Удаление чата
    DELETE_MEDIA = "delete_media"  # Удаление медиафайла
    DELETE_STORY = "delete_story"  # Удаление истории
    EDIT_MESSAGE = "edit_message"  # Редактирование сообщения (модератором)

    # Действия с правами
    GRANT_ADMIN = "grant_admin"  # Назначение администратором
    REVOKE_ADMIN = "revoke_admin"  # Снятие прав администратора
    GRANT_MODERATOR = "grant_moderator"  # Назначение модератором
    REVOKE_MODERATOR = "revoke_moderator"  # Снятие прав модератора

    # Действия с жалобами
    RESOLVE_REPORT = "resolve_report"  # Обработка жалобы
    ESCALATE_REPORT = "escalate_report"  # Эскалация жалобы
    REJECT_REPORT = "reject_report"  # Отклонение жалобы

    # Действия с подписками
    SUSPEND_SUBSCRIPTION = "suspend_subscription"  # Приостановка подписки
    RESTORE_SUBSCRIPTION = "restore_subscription"  # Восстановление подписки
    REFUND_SUBSCRIPTION = "refund_subscription"  # Возврат средств

    # Системные действия
    OVERRIDE_CONTENT = "override_content"  # Принудительное изменение контента
    SYSTEM_ACTION = "system_action"  # Автоматическое действие системы
    CONFIG_CHANGE = "config_change"  # Изменение конфигурации модерации


class ModerationSeverity(str, enum.Enum):
    """Уровень серьезности действия."""
    INFO = "info"  # Информационное
    WARNING = "warning"  # Предупреждение
    MINOR = "minor"  # Незначительное нарушение
    MODERATE = "moderate"  # Умеренное нарушение
    SEVERE = "severe"  # Серьезное нарушение
    CRITICAL = "critical"  # Критическое нарушение


class ModerationStatus(str, enum.Enum):
    """Статус рассмотрения."""
    PENDING = "pending"  # Ожидает рассмотрения
    IN_PROGRESS = "in_progress"  # В процессе
    RESOLVED = "resolved"  # Разрешено
    REJECTED = "rejected"  # Отклонено
    APPEALED = "appealed"  # Обжаловано
    OVERRIDDEN = "overridden"  # Переопределено


class ModerationLog(Base):
    """
    Лог действий модераторов для аудита и аналитики.
    """
    __tablename__ = "moderation_logs"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Кто совершил действие
    moderator_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="ID модератора (или 0 для системных действий)"
    )

    # Тип и объект действия
    action: Mapped[ModerationAction] = mapped_column(
        SQLEnum(ModerationAction),
        nullable=False,
        comment="Совершенное действие"
    )

    severity: Mapped[ModerationSeverity] = mapped_column(
        SQLEnum(ModerationSeverity),
        default=ModerationSeverity.INFO,
        nullable=False,
        comment="Уровень серьезности"
    )

    target_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Тип объекта (user, message, chat, media, story, subscription)"
    )

    target_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        comment="ID объекта"
    )

    # Дополнительные идентификаторы
    target_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
        comment="ID пользователя, к которому относится действие (если отличается от target_id)"
    )

    # Причины и детали
    reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Причина действия (текстовое описание)"
    )

    reason_code: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Код причины для автоматической обработки (например: 'spam', 'abuse', 'nsfw')"
    )

    # Детали в формате JSON
    details: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
        default=dict,
        comment="Дополнительные детали в формате JSON"
    )

    # Данные до и после (для отслеживания изменений)
    data_before: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
        comment="Данные до изменения (для edit действий)"
    )

    data_after: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
        comment="Данные после изменения (для edit действий)"
    )

    # Статус рассмотрения
    status: Mapped[ModerationStatus] = mapped_column(
        SQLEnum(ModerationStatus),
        default=ModerationStatus.RESOLVED,
        nullable=False,
        comment="Статус рассмотрения"
    )

    # Временные метки
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Дата и время действия"
    )

    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Дата окончания действия (для временных блокировок)"
    )

    resolved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Дата разрешения (для жалоб)"
    )

    # Метаданные
    ip_address: Mapped[Optional[str]] = mapped_column(
        String(45),
        nullable=True,
        comment="IP адрес модератора"
    )

    user_agent: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="User Agent модератора"
    )

    request_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="ID запроса для трассировки"
    )

    # Автоматические действия
    is_automatic: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Автоматическое действие системы"
    )

    auto_trigger: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Триггер автоматического действия"
    )

    confidence_score: Mapped[Optional[float]] = mapped_column(
        default=0.0,
        nullable=True,
        comment="Уверенность AI/автоматической модерации (0-1)"
    )

    # Связанные записи
    related_log_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("moderation_logs.id"),
        nullable=True,
        comment="ID связанного лога (например, для appeal)"
    )

    # Отношения
    moderator: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[moderator_id],
        backref="moderation_actions"
    )

    target_user: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[target_user_id],
        backref="received_moderation_actions"
    )

    related_log: Mapped[Optional["ModerationLog"]] = relationship(
        "ModerationLog",
        remote_side=[id],
        backref="appeals"
    )

    __table_args__ = (
        # Основные индексы
        Index('ix_moderation_logs_moderator', 'moderator_id', 'created_at'),
        Index('ix_moderation_logs_target', 'target_type', 'target_id'),
        Index('ix_moderation_logs_action', 'action'),
        Index('ix_moderation_logs_severity', 'severity'),
        Index('ix_moderation_logs_status', 'status'),

        # Составные индексы для частых запросов
        Index('ix_moderation_logs_user_action', 'target_user_id', 'action', 'created_at'),
        Index('ix_moderation_logs_auto', 'is_automatic', 'created_at'),
        Index('ix_moderation_logs_expires', 'expires_at'),

        # Индекс для поиска по коду причины
        Index('ix_moderation_logs_reason_code', 'reason_code'),

        # Для аналитики по датам
        Index('ix_moderation_logs_created_date', func.date(created_at)),
    )

    @property
    def is_active(self) -> bool:
        """Проверка, активно ли еще действие (для временных блокировок/мутов)."""
        if self.expires_at:
            return datetime.now(self.expires_at.tzinfo) < self.expires_at
        return True

    @property
    def duration_days(self) -> Optional[int]:
        """Длительность действия в днях (для временных блокировок)."""
        if self.expires_at and self.created_at:
            delta = self.expires_at - self.created_at
            return delta.days
        return None

    def to_dict(self, include_details: bool = True) -> Dict[str, Any]:
        """Преобразование в словарь для API."""
        result = {
            "id": self.id,
            "moderator_id": self.moderator_id,
            "action": self.action.value,
            "severity": self.severity.value,
            "target_type": self.target_type,
            "target_id": self.target_id,
            "target_user_id": self.target_user_id,
            "reason": self.reason,
            "reason_code": self.reason_code,
            "status": self.status.value,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "is_automatic": self.is_automatic,
            "is_active": self.is_active
        }

        if include_details:
            result.update({
                "details": self.details,
                "ip_address": self.ip_address,
                "user_agent": self.user_agent,
                "confidence_score": self.confidence_score
            })

        return result

    def set_details(self, **kwargs) -> None:
        """Установка деталей действия."""
        if self.details is None:
            self.details = {}
        self.details.update(kwargs)

    def get_detail(self, key: str, default: Any = None) -> Any:
        """Получение детали действия."""
        return self.details.get(key, default) if self.details else default

    @classmethod
    def create_ban_log(
        cls,
        moderator_id: int,
        target_user_id: int,
        reason: str,
        reason_code: str,
        duration_days: Optional[int] = None,
        **kwargs
    ) -> "ModerationLog":
        """Создание лога бана пользователя."""
        expires_at = None
        if duration_days:
            expires_at = datetime.now() + timedelta(days=duration_days)

        return cls(
            moderator_id=moderator_id,
            action=ModerationAction.BAN_USER,
            severity=ModerationSeverity.SEVERE,
            target_type="user",
            target_id=target_user_id,
            target_user_id=target_user_id,
            reason=reason,
            reason_code=reason_code,
            expires_at=expires_at,
            **kwargs
        )

    @classmethod
    def create_mute_log(
        cls,
        moderator_id: int,
        target_user_id: int,
        reason: str,
        duration_days: Optional[int] = None,
        **kwargs
    ) -> "ModerationLog":
        """Создание лога мута пользователя."""
        expires_at = None
        if duration_days:
            expires_at = datetime.now() + timedelta(days=duration_days)

        return cls(
            moderator_id=moderator_id,
            action=ModerationAction.MUTE_USER,
            severity=ModerationSeverity.MODERATE,
            target_type="user",
            target_id=target_user_id,
            target_user_id=target_user_id,
            reason=reason,
            reason_code="mute",
            expires_at=expires_at,
            **kwargs
        )

    @classmethod
    def create_delete_message_log(
        cls,
        moderator_id: int,
        message_id: int,
        user_id: int,
        reason: str,
        message_content: Optional[str] = None,
        **kwargs
    ) -> "ModerationLog":
        """Создание лога удаления сообщения."""
        details = {"message_content": message_content} if message_content else {}

        return cls(
            moderator_id=moderator_id,
            action=ModerationAction.DELETE_MESSAGE,
            severity=ModerationSeverity.MODERATE,
            target_type="message",
            target_id=message_id,
            target_user_id=user_id,
            reason=reason,
            reason_code="inappropriate_content",
            details=details,
            **kwargs
        )