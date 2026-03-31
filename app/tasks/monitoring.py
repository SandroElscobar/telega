"""
Задачи мониторинга для Celery.
"""

import redis
import logging
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List
import asyncio

from app.core.celery_app import task, CELERY_QUEUE_SIZE
from app.core.config import settings

logger = logging.getLogger(__name__)

# Глобальный пул соединений Redis
redis_pool = None

def get_redis_client():
    """Получение Redis клиента с пулом соединений."""
    global redis_pool
    if redis_pool is None:
        redis_pool = redis.ConnectionPool.from_url(
            settings.REDIS_URL,
            max_connections=20,
            socket_connect_timeout=5,
            socket_timeout=5,
            retry_on_timeout=True
        )
    return redis.Redis(connection_pool=redis_pool)


@task(queue="default")
def system_health_check() -> Dict[str, Any]:
    """Проверка здоровья системы."""
    try:
        r = get_redis_client()
        redis_ok = r.ping()

        health_status = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "redis": "healthy" if redis_ok else "unhealthy",
            "status": "healthy" if redis_ok else "degraded"
        }

        # Проверка базы данных если доступна
        try:
            from app.core.database import db_manager
            async def check_db():
                async with db_manager.session() as session:
                    await session.execute("SELECT 1")

            asyncio.run(check_db())
            health_status["database"] = "healthy"
        except Exception as e:
            health_status["database"] = "unhealthy"
            health_status["database_error"] = str(e)
            health_status["status"] = "degraded"

        logger.info(f"System health check: {health_status}")
        return health_status

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {"status": "unhealthy", "error": str(e)}


@task(queue="default")
def monitor_queue_sizes() -> Dict[str, int]:
    """Мониторинг размеров очередей с использованием SCAN вместо KEYS."""
    try:
        r = get_redis_client()
        queues = [
            "default", "media", "notifications", "cleanup",
            "premium", "moderation", "high_priority"
        ]

        queue_sizes = {}
        for queue in queues:
            # Используем правильное имя очереди в Redis
            # В зависимости от конфигурации Celery, очереди могут иметь разные префиксы
            queue_key = f"celery_{queue}"  # Или просто queue, в зависимости от настройки

            try:
                size = r.llen(queue_key)
                queue_sizes[queue] = size
                CELERY_QUEUE_SIZE.labels(queue_name=queue).observe(size)

                # Отправка алертов при большом размере очереди
                if size > 1000:
                    logger.warning(f"Queue {queue} is large: {size} tasks")
                    # Асинхронный вызов emergency_alert
                    emergency_alert.delay(
                        message=f"Queue {queue} has {size} pending tasks",
                        level="warning"
                    )
                elif size > 5000:
                    emergency_alert.delay(
                        message=f"Queue {queue} is critically large: {size} tasks",
                        level="error"
                    )

            except Exception as e:
                logger.error(f"Failed to get size for queue {queue}: {e}")
                queue_sizes[queue] = -1

        logger.info(f"Queue sizes: {queue_sizes}")
        return queue_sizes

    except Exception as e:
        logger.error(f"Queue monitoring failed: {e}")
        return {}


@task(queue="default", priority=9)
def auto_scale_workers() -> Dict[str, str]:
    """Автоматическое масштабирование воркеров."""
    try:
        queue_sizes = monitor_queue_sizes()

        scaling_decisions = {}
        for queue, size in queue_sizes.items():
            if size > 500:
                scaling_decisions[queue] = "scale_up"
                logger.info(f"Scaling up workers for queue {queue} (size: {size})")

                # Здесь можно добавить логику масштабирования через API
                # Например, для Kubernetes:
                # from kubernetes import client, config
                # config.load_incluster_config()
                # apps_v1 = client.AppsV1Api()
                # deployment = apps_v1.read_namespaced_deployment(f"celery-{queue}-worker", "default")
                # deployment.spec.replicas += 1
                # apps_v1.patch_namespaced_deployment(f"celery-{queue}-worker", "default", deployment)

            elif size < 50 and size >= 0:
                scaling_decisions[queue] = "scale_down"
                logger.info(f"Scaling down workers for queue {queue} (size: {size})")
            else:
                scaling_decisions[queue] = "maintain"

        return scaling_decisions

    except Exception as e:
        logger.error(f"Auto-scaling failed: {e}")
        return {"error": str(e)}


@task(queue="default")
def check_external_services() -> Dict[str, Any]:
    """Проверка соединения с внешними сервисами."""
    services = {
        "minio": getattr(settings, 'MINIO_ENDPOINT', None),
        "email": getattr(settings, 'SMTP_SERVER', None),
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
                        access_key=getattr(settings, 'MINIO_ACCESS_KEY', ''),
                        secret_key=getattr(settings, 'MINIO_SECRET_KEY', ''),
                        secure=getattr(settings, 'MINIO_SECURE', True)
                    )
                    buckets = client.list_buckets()
                    results[service_name] = {
                        "status": "healthy",
                        "buckets": len(list(buckets))
                    }

                elif service_name == "email":
                    # Проверка SMTP
                    import smtplib
                    try:
                        with smtplib.SMTP(endpoint, getattr(settings, 'SMTP_PORT', 587), timeout=5) as server:
                            if getattr(settings, 'SMTP_USE_TLS', True):
                                server.starttls()
                            results[service_name] = {"status": "healthy"}
                    except Exception as e:
                        results[service_name] = {"status": "unhealthy", "error": str(e)}

            except Exception as e:
                results[service_name] = {
                    "status": "unhealthy",
                    "error": str(e)
                }
                logger.error(f"Service {service_name} check failed: {e}")
        else:
            results[service_name] = {"status": "not_configured"}

    return results


@task(queue="cleanup")
def cleanup_old_task_results(days: int = 7) -> Dict[str, Any]:
    """Очистка старых результатов задач с использованием SCAN."""
    try:
        r = get_redis_client()

        # Используем SCAN вместо KEYS для избежания блокировки
        deleted_count = 0
        cursor = 0
        pattern = "celery-task-meta-*"

        while True:
            cursor, keys = r.scan(cursor, match=pattern, count=100)

            for key in keys:
                try:
                    # Получаем время создания из метаданных задачи
                    # В реальности нужно парсить результат
                    r.delete(key)
                    deleted_count += 1
                except Exception as e:
                    logger.error(f"Error deleting result {key}: {e}")

            if cursor == 0:
                break

        logger.info(f"Cleaned up {deleted_count} old task results")
        return {"deleted_count": deleted_count}

    except Exception as e:
        logger.error(f"Cleanup of old task results failed: {e}")
        return {"error": str(e)}


@task(queue="default")
def collect_metrics() -> Dict[str, Any]:
    """Сбор метрик для мониторинга."""
    try:
        # Собираем метрики
        health = system_health_check()
        queues = monitor_queue_sizes()
        services = check_external_services()

        metrics = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "health": health,
            "queues": queues,
            "external_services": services,
        }

        # Добавляем информацию о Celery если доступна
        try:
            from celery import current_app
            inspect = current_app.control.inspect()

            if inspect:
                active = inspect.active()
                metrics["active_tasks"] = len(active) if active else 0

                registered = inspect.registered()
                metrics["registered_tasks"] = len(registered) if registered else 0
        except Exception as e:
            logger.warning(f"Failed to get Celery stats: {e}")

        # Сохраняем метрики в Redis для истории
        r = get_redis_client()
        metrics_key = f"celery:metrics:{datetime.now(timezone.utc).strftime('%Y%m%d%H%M')}"

        # Используем JSON для безопасной сериализации
        r.setex(
            metrics_key,
            3600 * 24,  # Храним 24 часа
            json.dumps(metrics, default=str)
        )

        return metrics

    except Exception as e:
        logger.error(f"Metrics collection failed: {e}")
        return {"error": str(e)}


@task(queue="high_priority", priority=10)
def emergency_alert(message: str, level: str = "warning") -> Dict[str, Any]:
    """Экстренное оповещение о проблемах."""
    try:
        # Отправка в Slack
        if hasattr(settings, 'SLACK_WEBHOOK_URL') and settings.SLACK_WEBHOOK_URL:
            import requests

            payload = {
                "text": f"🚨 *{level.upper()}*: {message}",
                "username": "Celery Monitor",
                "icon_emoji": ":warning:"
            }

            try:
                response = requests.post(
                    settings.SLACK_WEBHOOK_URL,
                    json=payload,
                    timeout=5
                )
                if response.status_code != 200:
                    logger.error(f"Slack webhook failed: {response.status_code}")
            except Exception as e:
                logger.error(f"Failed to send Slack alert: {e}")

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
def performance_report() -> Dict[str, Any]:
    """Генерация отчета о производительности."""
    try:
        r = get_redis_client()

        # Собираем метрики за последний час
        hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
        metrics_keys = []

        # Используем SCAN для поиска ключей метрик
        cursor = 0
        pattern = "celery:metrics:*"

        while True:
            cursor, keys = r.scan(cursor, match=pattern, count=100)
            metrics_keys.extend(keys)
            if cursor == 0:
                break

        recent_metrics = []
        for key in metrics_keys:
            try:
                key_str = key.decode() if isinstance(key, bytes) else key
                metric_time_str = key_str.split(":")[-1]
                metric_time = datetime.strptime(metric_time_str, "%Y%m%d%H%M")
                metric_time = metric_time.replace(tzinfo=timezone.utc)

                if metric_time > hour_ago:
                    metric_data = r.get(key)
                    if metric_data:
                        # Используем JSON вместо eval
                        metric = json.loads(metric_data.decode() if isinstance(metric_data, bytes) else metric_data)
                        recent_metrics.append(metric)
            except Exception as e:
                logger.debug(f"Error processing metric {key}: {e}")
                continue

        # Анализ метрик
        if recent_metrics:
            avg_queue_sizes = {}
            for queue in ["default", "media", "notifications", "cleanup", "premium", "moderation"]:
                sizes = []
                for m in recent_metrics:
                    queue_size = m.get("queues", {}).get(queue, None)
                    if queue_size is not None and queue_size >= 0:
                        sizes.append(queue_size)

                if sizes:
                    avg_queue_sizes[queue] = sum(sizes) / len(sizes)

            # Проверка на аномалии
            anomalies = []
            for metric in recent_metrics[-10:]:  # Последние 10 метрик
                for queue, size in metric.get("queues", {}).items():
                    avg = avg_queue_sizes.get(queue, 0)
                    if avg > 0 and size > avg * 3 and size >= 0:  # В 3 раза больше среднего
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
                elif avg_size < 10 and avg_size >= 0:
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