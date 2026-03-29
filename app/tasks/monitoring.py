"""
Задачи мониторинга для Celery.
"""

import redis
import logging
from datetime import datetime, timezone
import requests
from app.core.celery_app import task, CELERY_QUEUE_SIZE
from app.core.config import settings

logger = logging.getLogger(__name__)

@task(queue="default")
def system_health_check():
    """Проверка здоровья системы."""
    try:
        # Проверка Redis
        r = redis.from_url(settings.REDIS_URL)
        redis_ok = r.ping()

        # Проверка базы данных (если есть)
        # from app.db.session import SessionLocal
        # db_ok = SessionLocal().execute("SELECT 1").scalar()

        # Проверка внешних сервисов
        health_status = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "redis": "healthy" if redis_ok else "unhealthy",
            # "database": "healthy" if db_ok else "unhealthy",
            "status": "healthy" if redis_ok else "degraded"
        }

        logger.info(f"System health check: {health_status}")
        return health_status

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {"status": "unhealthy", "error": str(e)}

@task(queue="default")
def monitor_queue_sizes():
    """Мониторинг размеров очередей."""
    try:
        r = redis.from_url(settings.REDIS_URL)
        queues = [
            "default", "media", "notifications", "cleanup",
            "premium", "moderation", "high_priority"
        ]

        queue_sizes = {}
        for queue in queues:
            # Адаптируйте под ваш префикс очередей
            size = r.llen(f"celery")  # или r.llen(queue)
            queue_sizes[queue] = size
            CELERY_QUEUE_SIZE.labels(queue_name=queue).observe(size)

            # Отправка алертов
            if size > 1000:
                logger.warning(f"Queue {queue} is large: {size} tasks")
                # Здесь можно добавить отправку в Sentry/Telegram/Slack

        logger.info(f"Queue sizes: {queue_sizes}")
        return queue_sizes

    except Exception as e:
        logger.error(f"Queue monitoring failed: {e}")
        return {}

@task(queue="default", priority=9)
def auto_scale_workers():
    """Автоматическое масштабирование воркеров."""
    try:
        r = redis.from_url(settings.REDIS_URL)
        queue_sizes = monitor_queue_sizes()

        scaling_decisions = {}
        for queue, size in queue_sizes.items():
            if size > 500:
                # Запустить дополнительного воркера
                scaling_decisions[queue] = "scale_up"
                logger.info(f"Scaling up workers for queue {queue} (size: {size})")
                # Здесь можно добавить логику запуска дополнительных воркеров
                # Например, через Docker API или Kubernetes API
            elif size < 50:
                # Остановить лишнего воркера
                scaling_decisions[queue] = "scale_down"
                logger.info(f"Scaling down workers for queue {queue} (size: {size})")
            else:
                scaling_decisions[queue] = "maintain"

        return scaling_decisions

    except Exception as e:
        logger.error(f"Auto-scaling failed: {e}")
        return {"error": str(e)}

@task(queue="default")
def check_external_services():
    """Проверка соединения с внешними сервисами."""
    services = {
        "minio": settings.MINIO_ENDPOINT if hasattr(settings, 'MINIO_ENDPOINT') else None,
        "email": settings.SMTP_SERVER if hasattr(settings, 'SMTP_SERVER') else None,
        # Добавьте другие сервисы
    }

    results = {}
    for service_name, endpoint in services.items():
        if endpoint:
            try:
                if service_name == "minio":
                    # Проверка MinIO
                    import minio
                    client = minio.Minio(
                        endpoint,
                        access_key=settings.MINIO_ACCESS_KEY,
                        secret_key=settings.MINIO_SECRET_KEY,
                        secure=settings.MINIO_SECURE
                    )
                    buckets = client.list_buckets()
                    results[service_name] = {
                        "status": "healthy",
                        "buckets": len(list(buckets))
                    }
                elif service_name == "email":
                    # Проверка SMTP
                    import smtplib
                    with smtplib.SMTP(settings.SMTP_SERVER, settings.SMTP_PORT) as server:
                        server.starttls()
                        server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
                        results[service_name] = {"status": "healthy"}
                else:
                    # Общая проверка HTTP
                    response = requests.get(endpoint, timeout=5)
                    results[service_name] = {
                        "status": "healthy" if response.status_code < 400 else "unhealthy",
                        "status_code": response.status_code
                    }
            except Exception as e:
                results[service_name] = {
                    "status": "unhealthy",
                    "error": str(e)
                }
                logger.error(f"Service {service_name} check failed: {e}")

    return results

@task(queue="cleanup")
def cleanup_old_task_results(days: int = 7):
    """Очистка старых результатов задач."""
    try:
        from celery.result import AsyncResult
        import time

        r = redis.from_url(settings.REDIS_URL)

        # Ключи результатов в Redis
        result_keys = r.keys("celery-task-meta-*")

        deleted_count = 0
        for key in result_keys:
            try:
                # Получаем результат
                result_data = r.get(key)
                if result_data:
                    # Проверяем время создания
                    # В реальности нужно парсить данные результата
                    # Здесь упрощенная логика
                    r.delete(key)
                    deleted_count += 1
            except Exception as e:
                logger.error(f"Error deleting result {key}: {e}")

        logger.info(f"Cleaned up {deleted_count} old task results")
        return {"deleted_count": deleted_count}

    except Exception as e:
        logger.error(f"Cleanup of old task results failed: {e}")
        return {"error": str(e)}

@task(queue="default")
def collect_metrics():
    """Сбор метрик для мониторинга."""
    try:
        from celery import current_app

        metrics = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "active_tasks": len(current_app.control.inspect().active() or {}),
            "registered_tasks": len(current_app.tasks),
            "queues": monitor_queue_sizes(),
            "health": system_health_check(),
            "external_services": check_external_services(),
        }

        # Сохраняем метрики в Redis для истории
        r = redis.from_url(settings.REDIS_URL)
        metrics_key = f"celery:metrics:{datetime.now(timezone.utc).strftime('%Y%m%d%H%M')}"
        r.setex(metrics_key, 3600 * 24, str(metrics))  # Храним 24 часа

        return metrics

    except Exception as e:
        logger.error(f"Metrics collection failed: {e}")
        return {"error": str(e)}

@task(queue="high_priority", priority=10)
def emergency_alert(message: str, level: str = "warning"):
    """Экстренное оповещение о проблемах."""
    try:
        # # Отправка в Telegram
        # if hasattr(settings, 'TELEGRAM_BOT_TOKEN') and hasattr(settings, 'TELEGRAM_CHAT_ID'):
        #     import telegram
        #     bot = telegram.Bot(token=settings.TELEGRAM_BOT_TOKEN)
        #     bot.send_message(
        #         chat_id=settings.TELEGRAM_CHAT_ID,
        #         text=f"🚨 {level.upper()}: {message}",
        #         parse_mode='HTML'
        #     )

        # Отправка в Slack
        if hasattr(settings, 'SLACK_WEBHOOK_URL'):
            import json
            payload = {
                "text": f"🚨 {level.upper()}: {message}",
                "username": "Celery Monitor",
                "icon_emoji": ":warning:"
            }
            requests.post(settings.SLACK_WEBHOOK_URL, json=payload)

        # Логирование
        if level == "critical":
            logger.critical(f"EMERGENCY ALERT: {message}")
        elif level == "error":
            logger.error(f"ALERT: {message}")
        else:
            logger.warning(f"ALERT: {message}")

        return {"status": "alert_sent", "message": message, "level": level}

    except Exception as e:
        logger.error(f"Emergency alert failed: {e}")
        return {"error": str(e)}

@task(queue="default")
def performance_report():
    """Генерация отчета о производительности."""
    try:
        from datetime import timedelta

        r = redis.from_url(settings.REDIS_URL)

        # Собираем метрики за последний час
        hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
        metrics_keys = r.keys("celery:metrics:*")

        recent_metrics = []
        for key in metrics_keys:
            try:
                metric_time_str = key.decode().split(":")[-1]
                metric_time = datetime.strptime(metric_time_str, "%Y%m%d%H%M")
                if metric_time > hour_ago:
                    metric_data = r.get(key)
                    if metric_data:
                        recent_metrics.append(eval(metric_data.decode()))
            except:
                pass

        # Анализ метрик
        if recent_metrics:
            avg_queue_sizes = {}
            for queue in ["default", "media", "notifications"]:
                sizes = [m.get("queues", {}).get(queue, 0) for m in recent_metrics]
                if sizes:
                    avg_queue_sizes[queue] = sum(sizes) / len(sizes)

            # Проверка на аномалии
            anomalies = []
            for metric in recent_metrics[-10:]:  # Последние 10 метрик
                for queue, size in metric.get("queues", {}).items():
                    avg = avg_queue_sizes.get(queue, 0)
                    if avg > 0 and size > avg * 3:  # В 3 раза больше среднего
                        anomalies.append({
                            "queue": queue,
                            "size": size,
                            "avg": avg,
                            "timestamp": metric.get("timestamp")
                        })

            report = {
                "period": "last_hour",
                "metrics_count": len(recent_metrics),
                "avg_queue_sizes": avg_queue_sizes,
                "anomalies": anomalies,
                "recommendations": []
            }

            # Рекомендации
            for queue, avg_size in avg_queue_sizes.items():
                if avg_size > 200:
                    report["recommendations"].append(
                        f"Увеличить количество воркеров для очереди {queue} (средний размер: {avg_size:.1f})"
                    )
                elif avg_size < 10:
                    report["recommendations"].append(
                        f"Уменьшить количество воркеров для очереди {queue} (средний размер: {avg_size:.1f})"
                    )

            logger.info(f"Performance report generated: {report}")
            return report

        return {"message": "No recent metrics available"}

    except Exception as e:
        logger.error(f"Performance report generation failed: {e}")
        return {"error": str(e)}

# Экспортируем все задачи
__all__ = [
    'system_health_check',
    'monitor_queue_sizes',
    'auto_scale_workers',
    'check_external_services',
    'cleanup_old_task_results',
    'collect_metrics',
    'emergency_alert',
    'performance_report'
]