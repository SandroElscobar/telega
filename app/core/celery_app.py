"""
Настройка Celery для фоновых задач.
"""

from celery import Celery
from celery.schedules import crontab
from app.core.config import settings
import logging
from prometheus_client import Counter, Histogram
from circuitbreaker import circuit
from opentelemetry.instrumentation.celery import CeleryInstrumentor
import signal
import sys


logger = logging.getLogger(__name__)

CELERY_TASKS_PROCESSED = Counter(
    'celery_tasks_processed_total',
    'Total number of processed tasks',
    ['queue', 'task_name', 'status']
)

CELERY_TASK_DURATION = Histogram(
    'celery_task_duration_seconds',
    'Task duration in seconds',
    ['queue', 'task_name']
)

CELERY_QUEUE_SIZE = Histogram(
    'celery_queue_size',
    'Current queue sizes',
    ['queue_name']
)
# Создаем экземпляр Celery

celery_app = Celery(
    "messenger",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "app.tasks.media",
        "app.tasks.notification",
        "app.tasks.cleanup",
        "app.tasks.premium",
        "app.tasks.moderation",
        "app.tasks.monitoring"
    ]
)

# Настройки Celery
celery_app.conf.update(
    # Сериализация
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,

    task_eager_propagates=False,

    # Поведение при старте (актуально для Celery 5.3+)
    broker_connection_retry_on_startup=True,
    broker_connection_max_retries=10,

    # Очереди задач с приоритетами и DLQ
    task_queues={
        "high_priority": {
            "exchange": "high_priority",
            "routing_key": "high_priority",
            "queue_arguments": {
                'x-max-priority': 10,
                'x-dead-letter-exchange': 'dlx',
                'x-dead-letter-routing-key': 'high_priority.dlq'
            }
        },
        "default": {
            "exchange": "default",
            "routing_key": "default",
            "queue_arguments": {
                'x-dead-letter-exchange': 'dlx',
                'x-dead-letter-routing-key': 'default.dlq'
            }
        },
        "media": {
            "exchange": "media",
            "routing_key": "media",
            "queue_arguments": {
                'x-dead-letter-exchange': 'dlx',
                'x-dead-letter-routing-key': 'media.dlq'
            }
        },
        "notifications": {
            "exchange": "notifications",
            "routing_key": "notifications",
            "queue_arguments": {
                'x-dead-letter-exchange': 'dlx',
                'x-dead-letter-routing-key': 'notifications.dlq'
            }
        },
        "cleanup": {
            "exchange": "cleanup",
            "routing_key": "cleanup",
            "queue_arguments": {
                'x-dead-letter-exchange': 'dlx',
                'x-dead-letter-routing-key': 'cleanup.dlq'
            }
        },
        "premium": {
            "exchange": "premium",
            "routing_key": "premium",
            "queue_arguments": {
                'x-dead-letter-exchange': 'dlx',
                'x-dead-letter-routing-key': 'premium.dlq'
            }
        },
        "moderation": {
            "exchange": "moderation",
            "routing_key": "moderation",
            "queue_arguments": {
                'x-dead-letter-exchange': 'dlx',
                'x-dead-letter-routing-key': 'moderation.dlq'
            }
        },
        # Dead Letter Queues
        "high_priority.dlq": {
            "exchange": "dlx",
            "routing_key": "high_priority.dlq"
        },
        "default.dlq": {
            "exchange": "dlx",
            "routing_key": "default.dlq"
        },
        "media.dlq": {
            "exchange": "dlx",
            "routing_key": "media.dlq"
        },
        "notifications.dlq": {
            "exchange": "dlx",
            "routing_key": "notifications.dlq"
        },
        "cleanup.dlq": {
            "exchange": "dlx",
            "routing_key": "cleanup.dlq"
        },
        "premium.dlq": {
            "exchange": "dlx",
            "routing_key": "premium.dlq"
        },
        "moderation.dlq": {
            "exchange": "dlx",
            "routing_key": "moderation.dlq"
        },
    },

    # Маршрутизация задач по умолчанию
    task_default_queue="default",
    task_default_exchange="default",
    task_default_routing_key="default",

    # Повторные попытки при ошибках
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_track_started=True,
    task_publish_retry=True,
    task_publish_retry_policy={
        'max_retries': 3,
        'interval_start': 0,
        'interval_step': 0.2,
        'interval_max': 0.2,
    },

    # Ограничения
    task_time_limit=30 * 60,  # 30 минут
    task_soft_time_limit=25 * 60,  # 25 минут
    worker_max_tasks_per_child=1000,  # Перезапуск воркера после 1000 задач
    worker_max_memory_per_child=200000,  # 200MB лимит памяти

    # Результаты
    result_expires=3600 * 24,  # 24 часа
    result_backend_transport_options={
        'retry_policy': {
            'timeout': 5.0,
            'interval_start': 0,
            'interval_step': 0.2,
            'interval_max': 0.2,
            'max_retries': 3,
        }
    },

    # Безопасность
    security_key=settings.CELERY_SECURITY_KEY if hasattr(settings, 'CELERY_SECURITY_KEY') else None,
    security_certificate=settings.CELERY_SECURITY_CERT if hasattr(settings, 'CELERY_SECURITY_CERT') else None,
    security_digest='sha256',

    # Мониторинг и метрики
    worker_send_task_events=True,
    task_send_sent_event=True,
    task_protocol=2,

    # Планировщик
    beat_schedule={
        # Очистка просроченных историй каждые 15 минут
        "cleanup-expired-stories": {
            "task": "app.tasks.cleanup.cleanup_expired_stories",
            "schedule": crontab(minute="*/15"),
            "options": {"queue": "cleanup"},
        },
        # Обработка запланированного удаления аккаунтов (раз в день)
        "process-scheduled-deletions": {
            "task": "app.tasks.cleanup.process_scheduled_deletions",
            "schedule": crontab(hour=3, minute=0),  # 3:00 ночи
            "options": {"queue": "cleanup"},
        },
        # Проверка истекающих подписок (раз в час)
        "check-expiring-subscriptions": {
            "task": "app.tasks.premium.check_expiring_subscriptions",
            "schedule": crontab(minute=0),  # Каждый час
            "options": {"queue": "premium"},
        },
        # Автоматическая модерация новых сообщений
        "auto-moderate-new-messages": {
            "task": "app.tasks.moderation.auto_moderate_new_messages",
            "schedule": crontab(minute="*/5"),  # Каждые 5 минут
            "options": {"queue": "moderation"},
        },
        # Очистка старых результатов задач (раз в день)
        "cleanup-old-task-results": {
            "task": "app.tasks.cleanup.cleanup_old_task_results",
            "schedule": crontab(hour=4, minute=0),  # 4:00 ночи
            "options": {"queue": "cleanup"},
        },
        # Мониторинг здоровья системы (каждые 10 минут)
        "system-health-check": {
            "task": "app.tasks.monitoring.system_health_check",
            "schedule": crontab(minute="*/10"),
            "options": {"queue": "default"},
        },
        # Мониторинг очередей (каждые 5 минут)
        "monitor-queue-sizes": {
            "task": "app.tasks.monitoring.monitor_queue_sizes",
            "schedule": crontab(minute="*/5"),
            "options": {"queue": "default"},
        },
        # Автоматическое масштабирование (каждые 10 минут)
        "auto-scale-workers": {
            "task": "app.tasks.monitoring.auto_scale_workers",
            "schedule": crontab(minute="*/10"),
            "options": {"queue": "default"},
        },
        # Проверка соединения с внешними сервисами (каждые 15 минут)
        "check-external-services": {
            "task": "app.tasks.monitoring.check_external_services",
            "schedule": crontab(minute="*/15"),
            "options": {"queue": "default"},
        },
    },

    # Настройки для Redis
    broker_transport_options={
        'visibility_timeout': 3600,  # 1 час
        'fanout_prefix': True,
        'fanout_patterns': True,
        'socket_keepalive': True,
        'socket_timeout': 30,
        'retry_on_timeout': True,
        'max_connections': 10,
        'health_check_interval': 30,
    },

    # Настройки для обработки больших задач
    worker_prefetch_multiplier=1,  # По одной задаче на воркер для fairness
    task_always_eager=False,  # Для продакшена всегда False

    # Кэширование результатов
    result_cache_backend='redis://localhost:6379/2',
    result_cache_max=1000,

    # Отладка
    worker_enable_remote_control=True,
    worker_pool_restarts=True,
)

# Инициализация OpenTelemetry
CeleryInstrumentor().instrument()


# Декоратор для привязки задачи к конкретной очереди с метриками
def task(queue: str = "default", priority: int = 5, **kwargs):
    """Декоратор для явного указания очереди задачи с метриками."""

    def decorator(func):
        def wrapper(*args, **kwargs):
            import time
            start_time = time.time()

            try:
                result = func(*args, **kwargs)
                CELERY_TASKS_PROCESSED.labels(
                    queue=queue,
                    task_name=func.__name__,
                    status='success'
                ).inc()
                return result
            except Exception as e:
                CELERY_TASKS_PROCESSED.labels(
                    queue=queue,
                    task_name=func.__name__,
                    status='error'
                ).inc()
                logger.error(f"Task {func.__name__} failed: {e}")
                raise
            finally:
                duration = time.time() - start_time
                CELERY_TASK_DURATION.labels(
                    queue=queue,
                    task_name=func.__name__
                ).observe(duration)

        # Применяем circuit breaker для устойчивости
        wrapped_with_circuit = circuit(
            failure_threshold=5,
            recovery_timeout=60,
            expected_exception=Exception
        )(wrapper)

        return celery_app.task(queue=queue, priority=priority, **kwargs)(wrapped_with_circuit)

    return decorator


# Декоратор для задач с кэшированием
def cached_task(queue: str = "default", cache_timeout: int = 3600, **kwargs):
    """Декоратор для задач с кэшированием результатов."""

    def decorator(func):
        from functools import lru_cache

        @lru_cache(maxsize=100)
        def cached_wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        return celery_app.task(
            queue=queue,
            **kwargs
        )(cached_wrapper)

    return decorator


# Функция для инициализации Celery в приложении
def init_celery(app):
    """Инициализация Celery с Flask/FastAPI приложением."""

    class ContextTask(celery_app.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery_app.Task = ContextTask
    return celery_app


# Обработка graceful shutdown
def setup_graceful_shutdown():
    """Настройка обработки graceful shutdown."""

    def handle_shutdown(signum, frame):
        logger.info("Received shutdown signal, stopping Celery workers gracefully...")
        celery_app.control.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGTERM, handle_shutdown)
    signal.signal(signal.SIGINT, handle_shutdown)


# Функция для проверки конфигурации
def validate_celery_config():
    """Валидация конфигурации Celery."""
    required_settings = [
        'REDIS_URL',
        'CELERY_SECURITY_KEY',
        'CELERY_SECURITY_CERT'
    ]

    missing = []
    for setting in required_settings:
        if not hasattr(settings, setting) or not getattr(settings, setting):
            missing.append(setting)

    if missing:
        logger.warning(f"Missing Celery settings: {missing}")

    # Проверка соединения с Redis
    try:
        import redis
        r = redis.from_url(settings.REDIS_URL)
        r.ping()
        logger.info("Redis connection successful")
    except Exception as e:
        logger.error(f"Redis connection failed: {e}")
        raise


# Инициализация при импорте
setup_graceful_shutdown()

# Экспортируем метрики для Prometheus
__all__ = [
    'celery_app',
    'task',
    'cached_task',
    'init_celery',
    'validate_celery_config',
    'CELERY_TASKS_PROCESSED',
    'CELERY_TASK_DURATION',
    'CELERY_QUEUE_SIZE'
]