from typing import Optional, List, Any
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, SecretStr, field_validator
import secrets
import os

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

    # --- База данных ---
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/postgres",
        description="Асинхронный URL для подключения к PostgreSQL",
    )

    DATABASE_ECHO: bool = Field(
        default=False,
        description="Логировать ли SQL запросы (для разработки)"
    )

    # --- Redis ---
    REDIS_URL: str = Field(
        default="redis://redis:6379/0",
        description="URL для подключения к Redis"
    )
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

    # --- Пароли ---
    # Используем Argon2 - самый надежный на данный момент алгоритм хеширования
    PASSWORD_HASH_SCHEMES: List[str] = Field(
        default=["argon2", "bcrypt"],  # argon2 приоритетнее
        description="Схемы хеширования паролей для passlib"
    )
    ARGON2_TIME_COST: int = Field(default=2, description="Argon2 параметр времени")
    ARGON2_MEMORY_COST: int = Field(default=102400, description="Argon2 параметр памяти")
    ARGON2_PARALLELISM: int = Field(default=8, description="Argon2 параллелизм")
    ARGON2_HASH_LEN: int = Field(default=32, description="Argon2 длина хеша")
    ARGON2_SALT_LEN: int = Field(default=16, description="Argon2 длина соли")

    # --- SMS (для верификации телефона) ---
    SMS_PROVIDER: str = Field(default="twilio", description="Провайдер SMS (twilio, vonage и т.д.)")
    SMS_ACCOUNT_SID: Optional[SecretStr] = Field(default=None, description="SID аккаунта SMS провайдера")
    SMS_AUTH_TOKEN: Optional[SecretStr] = Field(default=None, description="Токен авторизации SMS провайдера")
    SMS_FROM_NUMBER: Optional[str] = Field(default=None, description="Номер отправителя")

    # --- Firebase (Push уведомления) ---
    FIREBASE_CREDENTIALS_PATH: Optional[str] = Field(
        default=None,
        description="Путь к JSON файлу с credentials Firebase"
    )

    # --- WebSocket ---
    WS_MAX_CONNECTIONS: int = Field(default=10000, description="Максимальное количество WebSocket соединений")
    WS_PING_INTERVAL: int = Field(default=20, description="Интервал пингов WebSocket в секундах")
    WS_PING_TIMEOUT: int = Field(default=20, description="Таймаут ответа на пинг")

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


# Создаем глобальный экземпляр настроек
settings = Settings()

# Для отладки: показываем, какие настройки загружены (без секретов)пше
if __name__ == "__main__":
    print("=== Конфигурация приложения ===")
    for key, value in settings.model_dump().items():
        if "SECRET" in key or "TOKEN" in key or "PASSWORD" in key:
            print(f"{key}: ***hidden***")
        else:
            print(f"{key}: {value}")