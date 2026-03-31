"""
Задачи для модерации контента.
"""
import logging
import asyncio
from datetime import datetime, timezone, timedelta
from sqlalchemy import select

from app.core.celery_app import task
from app.core.database import db_manager
from app.models.message import Message
from app.models.user import User

logger = logging.getLogger(__name__)


@task(queue="moderation")
def auto_moderate_new_messages() -> dict:
    """
    Автоматическая модерация новых сообщений.
    Запускается каждые 5 минут.
    """

    async def _moderate():
        async with db_manager.session() as session:
            # Находим сообщения, ожидающие модерации
            stmt = select(Message).where(
                Message.moderation_status == "pending",
                Message.created_at > datetime.now(timezone.utc) - timedelta(hours=24)
            ).limit(100)
            result = await session.execute(stmt)
            messages = result.scalars().all()

            moderated_count = 0
            flagged_count = 0

            # Список запрещенных слов (в реальности загружается из БД)
            banned_words = ["spam", "offensive_word", "inappropriate"]

            for message in messages:
                if message.encrypted_content:
                    content_lower = message.encrypted_content.lower()

                # Проверка на запрещенные слова
                is_flagged = any(word in content_lower for word in banned_words)

                if is_flagged:
                    message.moderation_status = "flagged"
                    message.moderated_at = datetime.now(timezone.utc)
                    message.moderation_reason = "Contains banned words"
                    flagged_count += 1
                else:
                    message.moderation_status = "approved"
                    message.moderated_at = datetime.now(timezone.utc)
                    moderated_count += 1

            await session.commit()

            return {
                "total_processed": len(messages),
                "approved": moderated_count,
                "flagged": flagged_count
            }

    try:
        result = asyncio.run(_moderate())
        logger.info(f"Auto-moderation completed: {result}")
        return result
    except Exception as e:
        logger.error(f"Auto-moderation failed: {e}")
        raise


@task(queue="moderation", bind=True)
def moderate_user_content(
        self,
        user_id: int,
        content_type: str,
        content_id: int,
        action: str = "auto"
) -> dict:
    """
    Модерация конкретного контента пользователя.
    """

    async def _moderate():
        async with db_manager.session() as session:
            if content_type == "message":
                stmt = select(Message).where(Message.id == content_id)
                result = await session.execute(stmt)
                content = result.scalar_one_or_none()
            else:
                return {"error": f"Unknown content type: {content_type}"}

            if not content:
                return {"error": "Content not found"}

            # Логика модерации
            if action == "delete":
                content.deleted_at = datetime.now(timezone.utc)
                content.moderation_status = "deleted"
                content.moderation_reason = "Deleted by moderator"
            elif action == "flag":
                content.moderation_status = "flagged"
                content.moderation_reason = "Flagged for review"
            else:
                # Автоматическая проверка
                banned_words = ["spam", "offensive"]
                if any(word in content.content.lower() for word in banned_words):
                    content.moderation_status = "flagged"
                else:
                    content.moderation_status = "approved"

            content.moderated_at = datetime.now(timezone.utc)
            await session.commit()

            return {
                "content_id": content_id,
                "content_type": content_type,
                "status": content.moderation_status,
                "action_taken": action
            }

    try:
        result = asyncio.run(_moderate())
        return result
    except Exception as e:
        logger.error(f"Content moderation failed: {e}")
        raise


# @task(queue="moderation")
# def update_banned_words(banned_words: List[str]) -> dict:
#     """
#     Обновление списка запрещенных слов.
#     """
#     try:
#         # В реальности сохраняем в Redis или БД
#         redis_client = get_redis_client()
#         redis_client.setex(
#             "moderation:banned_words",
#             3600 * 24,  # 24 часа
#             json.dumps(banned_words)
#         )
#
#         logger.info(f"Updated banned words list: {len(banned_words)} words")
#         return {"updated": True, "count": len(banned_words)}
#
#     except Exception as e:
#         logger.error(f"Failed to update banned words: {e}")
#         raise


@task(queue="moderation")
def generate_moderation_report() -> dict:
    """
    Генерация отчета о модерации.
    """

    async def _generate():
        async with db_manager.session() as session:
            now = datetime.now(timezone.utc)
            day_ago = now - timedelta(days=1)
            week_ago = now - timedelta(days=7)

            # Статистика за день
            stmt = select(Message).where(
                Message.moderated_at >= day_ago
            )
            result = await session.execute(stmt)
            today_messages = result.scalars().all()

            # Статистика за неделю
            stmt = select(Message).where(
                Message.moderated_at >= week_ago,
                Message.moderation_status == "flagged"
            )
            result = await session.execute(stmt)
            flagged_week = result.scalars().all()

            report = {
                "period": {
                    "day": day_ago.isoformat(),
                    "week": week_ago.isoformat()
                },
                "today": {
                    "total": len(today_messages),
                    "approved": len([m for m in today_messages if m.moderation_status == "approved"]),
                    "flagged": len([m for m in today_messages if m.moderation_status == "flagged"]),
                    "deleted": len([m for m in today_messages if m.moderation_status == "deleted"])
                },
                "week": {
                    "total_flagged": len(flagged_week),
                    "flagged_by_day": {}
                }
            }

            return report

    try:
        result = asyncio.run(_generate())
        return result
    except Exception as e:
        logger.error(f"Failed to generate moderation report: {e}")
        raise


__all__ = [
    'auto_moderate_new_messages',
    'moderate_user_content',
    # 'update_banned_words',
    'generate_moderation_report'
]