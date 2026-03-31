"""
Задачи для управления премиум-подписками.
"""
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, update
import logging
import asyncio

from app.core.celery_app import task
from app.core.database import db_manager
from app.models.subscription import Subscription
from app.models.user import User

logger = logging.getLogger(__name__)


@task(queue="premium")
def check_expiring_subscriptions() -> dict:
    """
    Проверка истекающих подписок.
    Отправляет уведомления за 3 дня до истечения.
    """
    async def _check():
        async with db_manager.session() as session:
            now = datetime.now(timezone.utc)
            expiring_soon = now + timedelta(days=3)

            # Находим подписки, истекающие через 3 дня
            stmt = select(Subscription).where(
                Subscription.expires_at <= expiring_soon,
                Subscription.expires_at > now,
                Subscription.auto_renew == True,
                Subscription.is_active == True
            )
            result = await session.execute(stmt)
            subscriptions = result.scalars().all()

            notified_count = 0
            for sub in subscriptions:
                logger.info(f"Подписка {sub.id} истекает {sub.expires_at}")

                # Отправляем уведомление пользователю
                try:
                    from app.tasks.notifications import send_push_notification
                    # Используем delay для асинхронной отправки
                    send_push_notification.delay(
                        user_id=sub.user_id,
                        title="Подписка истекает",
                        body=f"Ваша подписка истекает {sub.expires_at.strftime('%d.%m.%Y')}"
                    )
                    notified_count += 1
                except Exception as e:
                    logger.error(f"Failed to send notification for subscription {sub.id}: {e}")

            # Обновляем статус истекших подписок
            stmt = update(User).where(
                User.premium_until < now,
                User.is_premium == True
            ).values(is_premium=False)
            result = await session.execute(stmt)
            updated_users = result.rowcount

            await session.commit()
            return {
                "expiring_count": len(subscriptions),
                "notified_count": notified_count,
                "expired_users_updated": updated_users
            }

    try:
        result = asyncio.run(_check())
        logger.info(f"Проверка подписок завершена: {result}")
        return result
    except Exception as e:
        logger.error(f"Ошибка проверки подписок: {e}")
        raise


@task(queue="premium")
def activate_premium(user_id: int, subscription_id: int) -> dict:
    """
    Активация премиум-статуса после успешной оплаты.
    """
    async def _activate():
        async with db_manager.session() as session:
            # Получаем подписку
            stmt = select(Subscription).where(Subscription.id == subscription_id)
            result = await session.execute(stmt)
            subscription = result.scalar_one_or_none()

            if not subscription:
                logger.error(f"Подписка {subscription_id} не найдена")
                return {"success": False, "error": "Subscription not found"}

            # Обновляем пользователя
            stmt = update(User).where(User.id == user_id).values(
                is_premium=True,
                premium_until=subscription.expires_at,
                updated_at=datetime.now(timezone.utc)
            )
            await session.execute(stmt)

            # Обновляем статус подписки
            subscription.is_active = True
            subscription.activated_at = datetime.now(timezone.utc)

            await session.commit()
            logger.info(f"Премиум активирован для пользователя {user_id} до {subscription.expires_at}")

            # Отправляем подтверждение
            try:
                from app.tasks.notifications import send_push_notification
                send_push_notification.delay(
                    user_id=user_id,
                    title="Премиум активирован",
                    body=f"Ваша премиум-подписка активна до {subscription.expires_at.strftime('%d.%m.%Y')}"
                )
            except Exception as e:
                logger.error(f"Failed to send activation notification: {e}")

            return {
                "success": True,
                "user_id": user_id,
                "subscription_id": subscription_id,
                "expires_at": subscription.expires_at.isoformat()
            }

    try:
        result = asyncio.run(_activate())
        return result
    except Exception as e:
        logger.error(f"Ошибка активации премиум: {e}")
        raise


@task(queue="premium", bind=True, max_retries=3)
def process_subscription_payment(
    self,
    user_id: int,
    subscription_id: int,
    payment_data: dict
) -> dict:
    """
    Обработка платежа за подписку с поддержкой retry.
    """
    async def _process():
        async with db_manager.session() as session:
            # Получаем подписку
            stmt = select(Subscription).where(Subscription.id == subscription_id)
            result = await session.execute(stmt)
            subscription = result.scalar_one_or_none()

            if not subscription:
                return {"success": False, "error": "Subscription not found"}

            # Здесь должна быть интеграция с платежной системой
            # Например, Stripe, PayPal и т.д.

            # Имитация обработки платежа
            payment_successful = True  # В реальности проверяем статус

            if payment_successful:
                # Активируем премиум
                await session.execute(
                    update(User).where(User.id == user_id).values(
                        is_premium=True,
                        premium_until=subscription.expires_at
                    )
                )

                subscription.is_active = True
                subscription.payment_status = "paid"
                subscription.paid_at = datetime.now(timezone.utc)

                await session.commit()

                return {
                    "success": True,
                    "user_id": user_id,
                    "subscription_id": subscription_id,
                    "message": "Payment processed successfully"
                }
            else:
                return {
                    "success": False,
                    "error": "Payment failed"
                }

    try:
        result = asyncio.run(_process())

        if not result.get("success") and self.request.retries < self.max_retries:
            # Retry с экспоненциальной задержкой
            raise self.retry(
                countdown=60 * (2 ** self.request.retries)
            )

        return result

    except Exception as e:
        logger.error(f"Ошибка обработки платежа: {e}")
        raise


@task(queue="premium")
def cancel_subscription(subscription_id: int, reason: str = None) -> dict:
    """
    Отмена подписки.
    """
    async def _cancel():
        async with db_manager.session() as session:
            stmt = select(Subscription).where(Subscription.id == subscription_id)
            result = await session.execute(stmt)
            subscription = result.scalar_one_or_none()

            if not subscription:
                return {"success": False, "error": "Subscription not found"}

            subscription.is_active = False
            subscription.cancelled_at = datetime.now(timezone.utc)
            subscription.cancellation_reason = reason
            subscription.auto_renew = False

            # Обновляем статус пользователя если подписка не продлевается
            if subscription.expires_at < datetime.now(timezone.utc):
                await session.execute(
                    update(User).where(User.id == subscription.user_id).values(
                        is_premium=False
                    )
                )

            await session.commit()

            logger.info(f"Подписка {subscription_id} отменена")

            # Отправляем уведомление
            try:
                from app.tasks.notifications import send_push_notification
                send_push_notification.delay(
                    user_id=subscription.user_id,
                    title="Подписка отменена",
                    body="Ваша премиум-подписка была отменена"
                )
            except Exception as e:
                logger.error(f"Failed to send cancellation notification: {e}")

            return {
                "success": True,
                "subscription_id": subscription_id,
                "cancelled_at": subscription.cancelled_at.isoformat()
            }

    try:
        result = asyncio.run(_cancel())
        return result
    except Exception as e:
        logger.error(f"Ошибка отмены подписки: {e}")
        raise