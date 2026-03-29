"""
Задачи для отправки уведомлений.
"""
import logging
from typing import Dict, Any
import firebase_admin
from firebase_admin import messaging, credentials
from sqlalchemy import select

from app.core.celery_app import task
from app.core.config import settings
from app.core.database import db_manager

logger = logging.getLogger(__name__)

# Инициализация Firebase (если настроен)
if settings.FIREBASE_CREDENTIALS_PATH:
    cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS_PATH)
    firebase_admin.initialize_app(cred)
    logger.info("Firebase инициализирован")


@task(queue="notifications")
def send_push_notification(
        user_id: int,
        title: str,
        body: str,
        data: Dict[str, Any] = None,
        push_token: str = None
):
    """
    Отправка push-уведомления пользователю.
    """
    import asyncio

    async def _get_push_token():
        if push_token:
            return push_token

        async with db_manager.session() as session:
            from app.models.user import User
            stmt = select(User).where(User.id == user_id)
            result = await session.execute(stmt)
            user = result.scalar_one_or_none()
            return user.push_token if user else None

    try:
        token = asyncio.run(_get_push_token())
        if not token:
            logger.warning(f"Нет push-токена для пользователя {user_id}")
            return

        # Создаем сообщение
        message = messaging.Message(
            notification=messaging.Notification(
                title=title,
                body=body,
            ),
            data=data or {},
            token=token,
            android=messaging.AndroidConfig(
                priority="high",
                notification=messaging.AndroidNotification(
                    sound="default",
                    channel_id="messages",
                ),
            ),
            apns=messaging.APNSConfig(
                payload=messaging.APNSPayload(
                    aps=messaging.Aps(
                        sound="default",
                        badge=1,
                    ),
                ),
            ),
        )

        # Отправляем
        response = messaging.send(message)
        logger.info(f"Уведомление отправлено: {response}")
        return {"success": True, "message_id": response}

    except Exception as e:
        logger.error(f"Ошибка отправки push-уведомления: {e}")
        raise


@task(queue="notifications")
def send_sms_code(phone_number: str, code: str):
    """
    Отправка SMS с кодом подтверждения.
    """
    # TODO: Интеграция с SMS-провайдером
    # Пока имитация
    logger.info(f"Отправка SMS на {phone_number}: код {code}")

    # Пример для Twilio
    # from twilio.rest import Client
    # client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
    # message = client.messages.create(
    #     body=f"Ваш код подтверждения: {code}",
    #     from_=settings.TWILIO_PHONE_NUMBER,
    #     to=phone_number
    # )

    return {"success": True, "phone": phone_number}