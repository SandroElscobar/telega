"""
Настройка Celery для фоновых задач.
"""

from celery import Celery
import celery.schedules
from celery.schedules import crontab
from kombu import Queue, Exchange
from app.core.config import settings
import logging
from prometheus_client import Counter, Histogram
from opentelemetry.instrumentation.celery import CeleryInstrumentor
import signal
import sys
import time
import redis
from functools import wraps
import json

logger = logging.getLogger(__name__)

# Метрики Prometheus
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

# Определение очередей с использованием современного API
task_queues = [
    Queue(
        'high_priority',
        Exchange('high_priority'),
        routing_key='high_priority',
        queue_arguments={
            'x-max-priority': 10,
            'x-dead-letter-exchange': 'dlx',
            'x-dead-letter-routing-key': 'high_priority.dlq'
        }
    ),
    Queue(
        'default',
        Exchange('default'),
        routing_key='default',
        queue_arguments={
            'x-dead-letter-exchange': 'dlx',
            'x-dead-letter-routing-key': 'default.dlq'
        }
    ),
    Queue(
        'media',
        Exchange('media'),
        routing_key='media',
        queue_arguments={
            'x-dead-letter-exchange': 'dlx',
            'x-dead-letter-routing-key': 'media.dlq'
        }
    ),
    Queue(
        'notifications',
        Exchange('notifications'),
        routing_key='notifications',
        queue_arguments={
            'x-dead-letter-exchange': 'dlx',
            'x-dead-letter-routing-key': 'notifications.dlq'
        }
    ),
    Queue(
        'cleanup',
        Exchange('cleanup'),
        routing_key='cleanup',
        queue_arguments={
            'x-dead-letter-exchange': 'dlx',
            'x-dead-letter-routing-key': 'cleanup.dlq'
        }
    ),
    Queue(
        'premium',
        Exchange('premium'),
        routing_key='premium',
        queue_arguments={
            'x-dead-letter-exchange': 'dlx',
            'x-dead-letter-routing-key': 'premium.dlq'
        }
    ),
    Queue(
        'moderation',
        Exchange('moderation'),
        routing_key='moderation',
        queue_arguments={
            'x-dead-letter-exchange': 'dlx',
            'x-dead-letter-routing-key': 'moderation.dlq'
        }
    ),
    # Dead Letter Queues
    Queue('high_priority.dlq', Exchange('dlx'), routing_key='high_priority.dlq'),
    Queue('default.dlq', Exchange('dlx'), routing_key='default.dlq'),
    Queue('media.dlq', Exchange('dlx'), routing_key='media.dlq'),
    Queue('notifications.dlq', Exchange('dlx'), routing_key='notifications.dlq'),
    Queue('cleanup.dlq', Exchange('dlx'), routing_key='cleanup.dlq'),
    Queue('premium.dlq', Exchange('dlx'), routing_key='premium.dlq'),
    Queue('moderation.dlq', Exchange('dlx'), routing_key='moderation.dlq'),
]

celery_app = Celery(
    "messenger",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_BACKEND_URL,
    include=[
        "app.tasks.media",
        "app.tasks.notifications",
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
    result_accept_content=["json"],  # Добавлено для безопасности
    timezone="UTC",
    enable_utc=True,

    task_eager_propagates=False,

    # Поведение при старте
    broker_connection_retry_on_startup=True,
    broker_connection_max_retries=10,

    # Очереди задач
    task_queues=task_queues,  # Используем список Queue объектов

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
    worker_max_tasks_per_child=1000,
    worker_max_memory_per_child=200000,  # 200MB

    # Результаты
    result_expires=3600 * 24,  # 24 часа
    result_backend_transport_options={
        'retry_policy': {
            'timeout': 5.0,
            'max_retries': 3,
        }
    },
    # Мониторинг и метрики
    worker_send_task_events=True,
    task_send_sent_event=True,

    # Планировщик
    beat_schedule={
        "cleanup-expired-stories": {
            "task": "app.tasks.cleanup.cleanup_expired_stories",
            "schedule": crontab(minute="*/15"),
            "options": {"queue": "cleanup"},
        },
        "process-scheduled-deletions": {
            "task": "app.tasks.cleanup.process_scheduled_deletions",
            "schedule": crontab(hour=3, minute=0),
            "options": {"queue": "cleanup"},
        },
        "check-expiring-subscriptions": {
            "task": "app.tasks.premium.check_expiring_subscriptions",
            "schedule": crontab(minute=0),
            "options": {"queue": "premium"},
        },
        "auto-moderate-new-messages": {
            "task": "app.tasks.moderation.auto_moderate_new_messages",
            "schedule": crontab(minute="*/5"),
            "options": {"queue": "moderation"},
        },
        "cleanup-old-task-results": {
            "task": "app.tasks.monitoring.cleanup_old_task_results",
            "schedule": crontab(hour=4, minute=0),
            "options": {"queue": "cleanup"},
        },
        "system-health-check": {
            "task": "app.tasks.monitoring.system_health_check",
            "schedule": crontab(minute="*/10"),
            "options": {"queue": "default"},
        },
        "monitor-queue-sizes": {
            "task": "app.tasks.monitoring.monitor_queue_sizes",
            "schedule": crontab(minute="*/5"),
            "options": {"queue": "default"},
        },
        "auto-scale-workers": {
            "task": "app.tasks.monitoring.auto_scale_workers",
            "schedule": crontab(minute="*/10"),
            "options": {"queue": "default"},
        },
        "check-external-services": {
            "task": "app.tasks.monitoring.check_external_services",
            "schedule": crontab(minute="*/15"),
            "options": {"queue": "default"},
        },
    },

    # Настройки для Redis
    broker_transport_options={
        'visibility_timeout': 3600,
        'fanout_prefix': True,
        'fanout_patterns': True,
        'socket_keepalive': True,
        'socket_timeout': 30,
        'retry_on_timeout': True,
        'max_connections': 10,
        'health_check_interval': 30,
    },

    # Настройки для обработки задач
    worker_prefetch_multiplier=1,
    task_always_eager=False,
    worker_concurrency=4,  # Добавлено для лучшего контроля
)

# Инициализация OpenTelemetry с обработкой ошибок
try:
    CeleryInstrumentor().instrument()
    logger.info("OpenTelemetry instrumentation initialized")
except Exception as e:
    logger.warning(f"Failed to initialize OpenTelemetry: {e}")


# Улучшенный декоратор задач с метриками и retry tracking
def task(queue: str = "default", priority: int = 5, track_retries: bool = False, **kwargs):
    """Декоратор для явного указания очереди задачи с метриками."""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            is_retry = kwargs.get('_is_retry', False)

            try:
                result = func(*args, **kwargs)

                # Учитываем retry только если нужно
                if not is_retry or track_retries:
                    CELERY_TASKS_PROCESSED.labels(
                        queue=queue,
                        task_name=func.__name__,
                        status='success'
                    ).inc()

                return result
            except Exception as e:
                if not is_retry or track_retries:
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

        # Применяем базовую обертку без circuit breaker (перенесем в задачи)
        return celery_app.task(
            queue=queue,
            priority=priority,
            **kwargs
        )(wrapper)

    return decorator


# Улучшенный декоратор для кэширования с Redis
def cached_task(queue: str = "default", cache_timeout: int = 3600, **kwargs):
    """Декоратор для задач с кэшированием результатов в Redis."""

    def decorator(func):
        @celery_app.task(queue=queue, **kwargs)
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Генерируем ключ кэша
            cache_key = f"task_cache:{func.__name__}:{hash(str(args) + str(kwargs))}"

            try:
                # Пытаемся получить из кэша
                redis_client = redis.from_url(settings.REDIS_URL)
                cached_result = redis_client.get(cache_key)

                if cached_result:
                    logger.debug(f"Cache hit for {func.__name__}")
                    return json.loads(cached_result)

                # Выполняем задачу
                result = func(*args, **kwargs)

                # Сохраняем в кэш
                redis_client.setex(
                    cache_key,
                    cache_timeout,
                    json.dumps(result, default=str)
                )

                return result
            except Exception as e:
                logger.error(f"Cache error for {func.__name__}: {e}")
                # В случае ошибки кэша, просто выполняем задачу
                return func(*args, **kwargs)

        return wrapper

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


# Улучшенная обработка graceful shutdown
def setup_graceful_shutdown():
    """Настройка обработки graceful shutdown."""
    shutdown_requested = False

    def handle_shutdown(signum, frame):
        nonlocal shutdown_requested
        if shutdown_requested:
            logger.warning("Force shutdown...")
            sys.exit(1)

        logger.info("Received shutdown signal, stopping Celery workers gracefully...")
        shutdown_requested = True

        try:
            # Отправляем сигнал остановки
            celery_app.control.shutdown()

            # Даем время на завершение текущих задач
            logger.info("Waiting for tasks to complete (max 30 seconds)...")
            time.sleep(30)

            logger.info("Shutdown complete")
            sys.exit(0)
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
            sys.exit(1)

    signal.signal(signal.SIGTERM, handle_shutdown)
    signal.signal(signal.SIGINT, handle_shutdown)


# Функция для проверки конфигурации
def validate_celery_config():
    """Валидация конфигурации Celery."""
    required_settings = ['REDIS_URL']

    missing = []
    for setting in required_settings:
        if not hasattr(settings, setting) or not getattr(settings, setting):
            missing.append(setting)

    if missing:
        logger.warning(f"Missing Celery settings: {missing}")

    # Проверка соединения с Redis с использованием пула соединений
    try:
        redis_client = redis.from_url(
            settings.REDIS_URL,
            socket_connect_timeout=5,
            socket_timeout=5,
            retry_on_timeout=True
        )
        redis_client.ping()
        logger.info("Redis connection successful")

        # Проверяем создание очередей
        for queue in task_queues:
            logger.debug(f"Queue configured: {queue.name}")

    except Exception as e:
        logger.error(f"Redis connection failed: {e}")
        raise


# Инициализация
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