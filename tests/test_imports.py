"""
Простейший тест для проверки, что все импорты работают.
"""
import pytest


def test_core_imports():
    """Проверка импорта основных модулей."""
    try:
        from app.core.config import settings
        from fastapi import FastAPI
        import sqlalchemy
        import cryptography
        import jwt
        print(f"✓ Все импорты успешны")
        print(f"  SQLAlchemy: {sqlalchemy.__version__}")
        print(f"  Cryptography: {cryptography.__version__}")
    except ImportError as e:
        pytest.fail(f"Ошибка импорта: {e}")


def test_settings_loading():
    """Проверка загрузки настроек."""
    from app.core.config import settings

    assert settings.ALGORITHM == "HS256"
    assert settings.ACCESS_TOKEN_EXPIRE_MINUTES == 30
    assert settings.DATABASE_URL is not None
    print("✓ Настройки загружены корректно")