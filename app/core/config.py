from typing import Optional, List, Any
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, SecretStr, field_validator
import secrets

class Settings(BaseSettings):
    """
    Настройки приложения, загружаемые из переменных окружения или .env файла.
    Используем Pydantic для валидации и автоматического парсинга типов.
    """
    # Модель Pydantic для настроек, указываем, что можно брать данные из .env
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # ==================== БАЗА ДАННЫХ ====================
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/postgres",
        description="Асинхронный URL для подключения к PostgreeSQL",
    )

    DATABASE_ECHO: bool = Field(
        default=False,
        description="Логировать ли SQL запросы (для разработки)"
    )

    # ==================== MINIO / S3 ====================
    MINIO_ENDPOINT: str = Field(
        default="localhost:9000",
        description="Endpoint MinIO (например, localhost:9000 или s3.amazonaws.com)"
    )
    MINIO_ACCESS_KEY: str = Field(
        default="minioadmin",
        description="Access Key для MinIO/S3"
    )
    MINIO_SECRET_KEY: SecretStr = Field(
        default=SecretStr("minioadmin"),
        description="Secret Key для MinIO/S3"
    )
    MINIO_SECURE: bool = Field(
        default=False,
        description="Использовать HTTPS для подключения к MinIO"
    )
    MINIO_PUBLIC_URL: str = Field(
        default="http://localhost:9000",
        description="Публичный URL для доступа к файлам (может отличаться от endpoint)"
    )
    MINIO_BUCKET_NAME: str = Field(
        default="messenger-media",
        description="Имя bucket для хранения медиафайлов"
    )

    # --- Redis ---
    # ==================== REDIS ====================
    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        description="URL для подключения к Redis"
    )

    # ==================== БЕЗОПАСНОСТЬ И JWT ====================
    SECRET_KEY: SecretStr = Field(
        default=...,  # ... означает обязательное поле
        description="Секретный ключ для подписи JWT. Обязательно сменить в продакшне!"
    )
    ALGORITHM: str = Field(
        default="HS256",
        description="Алгоритм шифрования JWT"
    )
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(
        default=30,
        description="Время жизни access токена в минутах"
    )
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(
        default=7,
        description="Время жизни refresh токена в днях"
    )

    # ==================== ПАРОЛИ (pwdlib) ====================
    PASSWORD_HASH_SCHEMES: List[str] = Field(
        default=["argon2", "bcrypt"],  # argon2 приоритетнее
        description="Схемы хеширования паролей для passlib"
    )
    ARGON2_TIME_COST: int = Field(default=2, description="Argon2 параметр времени")
    ARGON2_MEMORY_COST: int = Field(default=102400, description="Argon2 параметр памяти")
    ARGON2_PARALLELISM: int = Field(default=8, description="Argon2 параллелизм")
    ARGON2_HASH_LEN: int = Field(default=32, description="Argon2 длина хеша")
    ARGON2_SALT_LEN: int = Field(default=16, description="Argon2 длина соли")

    # ==================== SMS ПРОВАЙДЕР ====================
    SMS_PROVIDER: str = Field(
        default="twilio",
        description="Провайдер SMS (twilio, smsru, vonage и т.д.)"
    )
    TWILIO_ACCOUNT_SID: Optional[str] = Field(
        default=None,
        description="SID аккаунта Twilio"
    )
    TWILIO_AUTH_TOKEN: Optional[SecretStr] = Field(
        default=None,
        description="Токен авторизации Twilio"
    )
    TWILIO_PHONE_NUMBER: Optional[str] = Field(
        default=None,
        description="Номер отправителя Twilio"
    )
    SMSRU_API_ID: Optional[SecretStr] = Field(
        default=None,
        description="API ID для SMS.ru"
    )
    SMS_CODE_LENGTH: int = Field(
        default=6,
        description="Длина SMS кода подтверждения"
    )
    SMS_CODE_EXPIRE_MINUTES: int = Field(
        default=5,
        description="Время жизни SMS кода в минутах"
    )

    # --- Firebase (Push уведомления) ---
    FIREBASE_CREDENTIALS_PATH: Optional[str] = Field(
        default=None,
        description="Путь к JSON файлу с credentials Firebase"
    )
    FIREBASE_PROJECT_ID: Optional[str] = Field(
        default=None,
        description="ID проекта Firebase"
    )

    # --- WebSocket ---
    WS_MAX_CONNECTIONS: int = Field(default=10000, description="Максимальное количество WebSocket соединений")
    WS_PING_INTERVAL: int = Field(default=20, description="Интервал пингов WebSocket в секундах")
    WS_PING_TIMEOUT: int = Field(default=20, description="Таймаут ответа на пинг")

    # ==================== CELERY ====================
    CELERY_BROKER_URL: Optional[str] = Field(
        default=None,
        description="URL брокера Celery (по умолчанию используется REDIS_URL)"
    )
    CELERY_BACKEND_URL: Optional[str] = Field(
        default=None,
        description="URL бекенда Celery (по умолчанию используется REDIS_URL)"
    )
    CELERY_TASK_ALWAYS_EAGER: bool = Field(
        default=False,
        description="Выполнять задачи синхронно (для тестов)"
    )

    # ==================== AI МОДЕРАЦИЯ ====================
    MODERATION_API_URL: Optional[str] = Field(
        default=None,
        description="URL API для AI модерации"
    )
    MODERATION_API_KEY: Optional[SecretStr] = Field(
        default=None,
        description="Ключ API для AI модерации"
    )
    MODERATION_AUTO_DELETE_THRESHOLD: float = Field(
        default=0.9,
        description="Порог уверенности для автоматического удаления (0-1)"
    )

    # ==================== ПЛАТЕЖНЫЕ СИСТЕМЫ ====================
    PAYMENT_PROVIDER: str = Field(
        default="yookassa",
        description="Платежный провайдер (yookassa, stripe)"
    )

    # YooKassa
    YOOKASSA_SHOP_ID: Optional[str] = Field(
        default=None,
        description="Shop ID для YooKassa"
    )
    YOOKASSA_SECRET_KEY: Optional[SecretStr] = Field(
        default=None,
        description="Secret Key для YooKassa"
    )

    # Stripe
    STRIPE_SECRET_KEY: Optional[SecretStr] = Field(
        default=None,
        description="Secret Key для Stripe"
    )
    STRIPE_WEBHOOK_SECRET: Optional[SecretStr] = Field(
        default=None,
        description="Webhook Secret для Stripe"
    )

    # ==================== ПРЕМИУМ ====================
    PREMIUM_PRICE_MONTHLY: float = Field(
        default=299.0,
        description="Цена месячной подписки в рублях"
    )
    PREMIUM_PRICE_QUARTERLY: float = Field(
        default=799.0,
        description="Цена квартальной подписки в рублях"
    )
    PREMIUM_PRICE_YEARLY: float = Field(
        default=2499.0,
        description="Цена годовой подписки в рублях"
    )
    PREMIUM_PRICE_LIFETIME: float = Field(
        default=9999.0,
        description="Цена пожизненной подписки в рублях"
    )

    # ==================== НАСТРОЙКИ ПРИЛОЖЕНИЯ ====================
    APP_NAME: str = Field(
        default="Secure Messenger",
        description="Название приложения"
    )
    APP_VERSION: str = Field(
        default="1.0.0",
        description="Версия приложения"
    )
    DEBUG: bool = Field(
        default=False,
        description="Режим отладки"
    )

    # ==================== RATE LIMITING ====================
    RATE_LIMIT_ENABLED: bool = Field(
        default=True,
        description="Включить ограничение частоты запросов"
    )
    RATE_LIMIT_REQUESTS: int = Field(
        default=100,
        description="Максимальное количество запросов"
    )
    RATE_LIMIT_PERIOD: int = Field(
        default=60,
        description="Период для rate limiting в секундах"
    )

    # ==================== АККАУНТ И БЕЗОПАСНОСТЬ ====================
    ACCOUNT_DELETION_DELAY_DAYS: int = Field(
        default=30,
        description="Задержка удаления аккаунта в днях"
    )
    MAX_LOGIN_ATTEMPTS: int = Field(
        default=5,
        description="Максимальное количество неудачных попыток входа"
    )
    BLOCK_DURATION_MINUTES: int = Field(
        default=15,
        description="Длительность блокировки после неудачных попыток"
    )

    @field_validator("SECRET_KEY", mode='before')
    @classmethod
    def validate_secret_key(cls, v: Any):
        """Проверяем, что секретный ключ не пустой и достаточно длинный."""
        if v is ... or v is None or (isinstance(v, str) and v == ""):
            # В разработке можно использовать предупреждение, в продакшне - ошибку
            import warnings
            warnings.warn(
                "SECRET_KEY не установлен! Используется небезопасный ключ по умолчанию. "
                "ОБЯЗАТЕЛЬНО установите SECRET_KEY в .env файле для продакшна!",
                RuntimeWarning
            )
            # Возвращаем тестовый ключ (только для разработки!)
            return secrets.token_urlsafe(32)
        return v

    @field_validator("CELERY_BROKER_URL", mode="before")
    @classmethod
    def set_celery_broker_default(cls, v, info):
        """Если CELERY_BROKER_URL не задан, используем REDIS_URL."""
        if not v:
            redis_url = info.data.get("REDIS_URL")
            if redis_url:
                return redis_url
        return v

    @property
    def minio_secure(self) -> bool:
        """Свойство для удобного доступа к MINIO_SECURE."""
        return self.MINIO_SECURE

    @property
    def minio_endpoint_with_scheme(self) -> str:
        """Возвращает endpoint с протоколом для подключения."""
        scheme = "https" if self.MINIO_SECURE else "http"
        return f"{scheme}://{self.MINIO_ENDPOINT}"

    @property
    def minio_public_endpoint(self) -> str:
        """Возвращает публичный endpoint для доступа к файлам."""
        if self.MINIO_PUBLIC_URL:
            return self.MINIO_PUBLIC_URL
        return self.minio_endpoint_with_scheme
# Создаем глобальный экземпляр настроек
settings = Settings()

# Для отладки: показываем, какие настройки загружены (без секретов)пше
if __name__ == "__main__":
    print("=" * 60)
    print("Конфигурация приложения")
    print("=" * 60)

    for key, value in settings.model_dump().items():
        # Скрываем секретные значения
        if any(secret in key.upper() for secret in ["SECRET", "TOKEN", "PASSWORD", "KEY"]):
            print(f"{key}: ***hidden***")
        else:
            print(f"{key}: {value}")

    print("\n" + "=" * 60)
    print("MinIO настройки:")
    print(f"  Endpoint: {settings.minio_endpoint_with_scheme}")
    print(f"  Public URL: {settings.minio_public_endpoint}")
    print(f"  Bucket: {settings.MINIO_BUCKET_NAME}")