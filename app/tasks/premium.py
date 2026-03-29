"""
Задачи для управления премиум-подписками.
"""
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, update
import logging

from app.core.celery_app import task
from app.core.database import db_manager
from app.models.subscription import Subscription
from app.models.user import User

logger = logging.getLogger(__name__)


@task(queue="premium")
def check_expiring_subscriptions():
    """
    Проверка истекающих подписок.
    Отправляет уведомления за 3 дня до истечения.
    """
    import asyncio

    async def _check():
        async with db_manager.session() as session:
            now = datetime.now(timezone.utc)
            expiring_soon = now + timedelta(days=3)

            # Находим подписки, истекающие через 3 дня
            stmt = select(Subscription).where(
                Subscription.expires_at <= expiring_soon,
                Subscription.expires_at > now,
                Subscription.auto_renew == True
            )
            result = await session.execute(stmt)
            subscriptions = result.scalars().all()

            for sub in subscriptions:
                logger.info(f"Подписка {sub.id} истекает {sub.expires_at}")

                # TODO: Отправить уведомление пользователю
                # from app.tasks.notifications import send_push_notification
                # send_push_notification.delay(
                #     user_id=sub.user_id,
                #     title="Подписка истекает",
                #     body=f"Ваша подписка истекает {sub.expires_at.strftime('%d.%m.%Y')}"
                # )

            # Обновляем статус истекших подписок
            stmt = update(User).where(
                User.premium_until < now,
                User.is_premium == True
            ).values(is_premium=False)
            await session.execute(stmt)

            await session.commit()
            return len(subscriptions)

    try:
        count = asyncio.run(_check())
        logger.info(f"Проверено истекающих подписок: {count}")
        return {"checked_count": count}
    except Exception as e:
        logger.error(f"Ошибка проверки подписок: {e}")
        raise


@task(queue="premium")
def activate_premium(user_id: int, subscription_id: int):
    """
    Активация премиум-статуса после успешной оплаты.
    """
    import asyncio

    async def _activate():
        async with db_manager.session() as session:
            # Получаем подписку
            stmt = select(Subscription).where(Subscription.id == subscription_id)
            result = await session.execute(stmt)
            subscription = result.scalar_one_or_none()

            if not subscription:
                logger.error(f"Подписка {subscription_id} не найдена")
                return False

            # Обновляем пользователя
            stmt = update(User).where(User.id == user_id).values(
                is_premium=True,
                premium_until=subscription.expires_at
            )
            await session.execute(stmt)

            await session.commit()
            logger.info(f"Премиум активирован для пользователя {user_id} до {subscription.expires_at}")
            return True

    try:
        success = asyncio.run(_activate())
        return {"success": success, "user_id": user_id}
    except Exception as e:
        logger.error(f"Ошибка активации премиум: {e}")
        raise