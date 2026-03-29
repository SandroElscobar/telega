"""
Задачи для очистки устаревших данных.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
import logging


from app.core.celery_app import task
from app.core.database import db_manager
from app.models.story import Story
from app.models.user import User

logger = logging.getLogger(__name__)


@task(queue="cleanup")
def cleanup_expired_stories():
    """
    Очистка просроченных историй.
    Запускается каждые 15 минут.
    """
    import asyncio

    async def _cleanup():
        async with db_manager.session() as session:
            # Находим просроченные истории
            now = datetime.now(timezone.utc)
            stmt = select(Story).where(Story.expires_at < now, Story.deleted_at.is_(None))
            result = await session.execute(stmt)
            expired_stories = result.scalars().all()

            # Мягкое удаление
            for story in expired_stories:
                story.deleted_at = now
                logger.info(f"История {story.id} просрочена и удалена")

            await session.commit()
            return len(expired_stories)

    try:
        deleted_count = asyncio.run(_cleanup())
        logger.info(f"Очищено просроченных историй: {deleted_count}")
        return {"deleted_count": deleted_count}
    except Exception as e:
        logger.error(f"Ошибка очистки историй: {e}")
        raise


@task(queue="cleanup")
def process_scheduled_deletions():
    """
    Обработка запланированного удаления аккаунтов.
    Запускается раз в сутки.
    """
    import asyncio

    async def _process():
        async with db_manager.session() as session:
            now = datetime.now(timezone.utc)
            threshold = now - timedelta(days=30)

            # Находим аккаунты, ожидающие удаления более 30 дней
            stmt = select(User).where(
                User.deletion_scheduled_at.is_not(None),
                User.deletion_scheduled_at < threshold,
                User.is_deleted == False
            )
            result = await session.execute(stmt)
            users_to_delete = result.scalars().all()

            for user in users_to_delete:
                # Софт-удаление
                user.deleted_at = now
                user.status = "inactive"
                logger.info(f"Аккаунт {user.id} удален по истечении 30 дней")

            await session.commit()
            return len(users_to_delete)

    try:
        deleted_count = asyncio.run(_process())
        logger.info(f"Окончательно удалено аккаунтов: {deleted_count}")
        return {"deleted_count": deleted_count}
    except Exception as e:
        logger.error(f"Ошибка удаления аккаунтов: {e}")
        raise