"""
Задачи для отправки уведомлений.
"""
import logging
from typing import Dict, Any, Optional
from sqlalchemy import select
import asyncio
import twilio

from app.core.celery_app import task
from app.core.config import settings
from app.core.database import db_manager

logger = logging.getLogger(__name__)

firebase_initialized = False
try:
    import firebase_admin
    from firebase_admin import messaging, credentials

    if hasattr(settings, 'FIREBASE_CREDENTIALS_PATH') and settings.FIREBASE_CREDENTIALS_PATH:
        cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS_PATH)
        firebase_admin.initialize_app(cred, {
            'projectId': getattr(settings, 'FIREBASE_PROJECT_ID', None),
            'storageBucket': getattr(settings, 'FIREBASE_STORAGE_BUCKET', None)
        })
        firebase_initialized = True
        logger.info("Firebase инициализирован")
    else:
        logger.warning("Firebase не настроен")
except Exception as e:
    logger.error(f"Ошибка инициализации Firebase: {e}")


@task(queue="notifications", bind=True, max_retries=3)
def send_push_notification(
        self,
        user_id: int,
        title: str,
        body: str,
        data: Optional[Dict[str, Any]] = None,
        push_token: Optional[str] = None
) -> dict:
    """
    Отправка push-уведомления пользователю с поддержкой retry.
    """

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
        if not firebase_initialized:
            logger.warning("Firebase не инициализирован, уведомление не отправлено")
            return {"success": False, "error": "Firebase not initialized"}

        token = asyncio.run(_get_push_token())
        if not token:
            logger.warning(f"Нет push-токена для пользователя {user_id}")
            return {"success": False, "error": "No push token"}

        # Создаем сообщение
        from firebase_admin import messaging

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

        # Retry с экспоненциальной задержкой
        if self.request.retries < self.max_retries:
            raise self.retry(
                exc=e,
                countdown=60 * (2 ** self.request.retries)
            )
        raise


@task(queue="notifications")
def send_sms_code(phone_number: str, code: str) -> dict:
    """
    Отправка SMS с кодом подтверждения.
    """
    try:
        # Проверяем настройки SMS провайдера
        # if hasattr(settings, 'TWILIO_ACCOUNT_SID') and settings.TWILIO_ACCOUNT_SID:
        #     # Интеграция с Twilio
        #     from twilio.rest import Client
        #
        #     client = Client(
        #         settings.TWILIO_ACCOUNT_SID,
        #         settings.TWILIO_AUTH_TOKEN
        #     )
        #     message = client.messages.create(
        #         body=f"Ваш код подтверждения: {code}",
        #         from_=settings.TWILIO_PHONE_NUMBER,
        #         to=phone_number
        #     )
        #     logger.info(f"SMS отправлено: {message.sid}")
        #     return {"success": True, "message_sid": message.sid}

        # Имитация для разработки
        logger.info(f"[MOCK] Отправка SMS на {phone_number}: код {code}")
        return {"success": True, "mock": True, "phone": phone_number}

    except Exception as e:
        logger.error(f"Ошибка отправки SMS: {e}")
        raise


@task(queue="notifications")
def send_email_notification(
        email: str,
        subject: str,
        body: str,
        html_body: Optional[str] = None
) -> dict:
    """
    Отправка email уведомления.
    """
    try:
        if not hasattr(settings, 'SMTP_SERVER') or not settings.SMTP_SERVER:
            logger.warning("SMTP не настроен")
            return {"success": False, "error": "SMTP not configured"}

        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart

        # Создаем сообщение
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = settings.SMTP_FROM_EMAIL
        msg['To'] = email

        # Добавляем текстовую версию
        msg.attach(MIMEText(body, 'plain'))

        # Добавляем HTML версию если есть
        if html_body:
            msg.attach(MIMEText(html_body, 'html'))

        # Отправляем
        with smtplib.SMTP(settings.SMTP_SERVER, settings.SMTP_PORT) as server:
            if hasattr(settings, 'SMTP_USE_TLS') and settings.SMTP_USE_TLS:
                server.starttls()

            if hasattr(settings, 'SMTP_USERNAME') and settings.SMTP_USERNAME:
                server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)

            server.send_message(msg)

        logger.info(f"Email отправлен на {email}")
        return {"success": True, "email": email}

    except Exception as e:
        logger.error(f"Ошибка отправки email: {e}")
        raise


@task(queue="notifications")
def send_bulk_notifications(notifications: list) -> dict:
    """
    Массовая отправка уведомлений.
    """
    results = {
        "total": len(notifications),
        "success": 0,
        "failed": 0,
        "errors": []
    }

    for notification in notifications:
        try:
            if notification['type'] == 'push':
                result = send_push_notification(
                    user_id=notification['user_id'],
                    title=notification['title'],
                    body=notification['body'],
                    data=notification.get('data')
                )
            elif notification['type'] == 'email':
                result = send_email_notification(
                    email=notification['email'],
                    subject=notification['subject'],
                    body=notification['body'],
                    html_body=notification.get('html_body')
                )
            else:
                result = {"success": False, "error": f"Unknown type: {notification['type']}"}

            if result.get('success'):
                results['success'] += 1
            else:
                results['failed'] += 1
                results['errors'].append({
                    'notification': notification,
                    'error': result.get('error', 'Unknown error')
                })

        except Exception as e:
            results['failed'] += 1
            results['errors'].append({
                'notification': notification,
                'error': str(e)
            })

    logger.info(f"Bulk notifications sent: {results['success']}/{results['total']}")
    return results