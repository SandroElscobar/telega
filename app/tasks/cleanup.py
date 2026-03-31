"""
Задачи для очистки устаревших данных.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
import logging
import asyncio


from app.core.celery_app import task
from app.core.database import db_manager
from app.models import UserStatus
from app.models.story import Story
from app.models.user import User

logger = logging.getLogger(__name__)


@task(queue="cleanup")
def cleanup_expired_stories() -> dict:
    """
    Очистка просроченных историй.
    Запускается каждые 15 минут.
    """

    async def _cleanup():
        async with db_manager.session() as session:
            # Находим просроченные истории
            now = datetime.now(timezone.utc)
            stmt = select(Story).where(
                Story.expires_at < now,
                Story.deleted_at.is_(None)
            )
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
def process_scheduled_deletions() -> dict:
    """
    Обработка запланированного удаления аккаунтов.
    Запускается раз в сутки.
    """

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
                user.is_deleted = True
                user.status = UserStatus.INACTIVE
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


@task(queue="cleanup", bind=True)
def cleanup_orphaned_data(self) -> dict:
    """
    Очистка orphaned данных (данных без владельцев).
    """

    async def _cleanup():
        async with db_manager.session() as session:
            # Очистка orphaned stories (истории без пользователей)
            stmt = select(Story).where(
                ~Story.user_id.in_(select(User.id))
            )
            result = await session.execute(stmt)
            orphaned_stories = result.scalars().all()

            for story in orphaned_stories:
                await session.delete(story)
                logger.info(f"Orphaned story {story.id} deleted")

            await session.commit()
            return len(orphaned_stories)

    try:
        deleted_count = asyncio.run(_cleanup())
        logger.info(f"Очищено orphaned данных: {deleted_count}")
        return {"deleted_count": deleted_count}
    except Exception as e:
        logger.error(f"Ошибка очистки orphaned данных: {e}")
        raise