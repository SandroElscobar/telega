"""
Модуль безопасности: хеширование паролей, JWT токены, генерация кодов.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
import secrets
import string

from jose import JWTError, jwt
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher
from pwdlib.hashers.bcrypt import BcryptHasher

from app.core.config import settings

# Инициализация PasswordHash с Argon2 (приоритет) и bcrypt для обратной совместимости
password_hash = PasswordHash(
    (
        Argon2Hasher,
        BcryptHasher
    )
)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Проверка пароля.

    Args:
        plain_password: Пароль в открытом виде
        hashed_password: Хеш пароля из БД

    Returns:
        bool: True если пароль совпадает
    """
    return password_hash.verify(plain_password, hashed_password)

def hash_password(password: str) -> str:
    """
    Хеширование пароля с использованием Argon2.

    Args:
        password: Пароль в открытом виде

    Returns:
        str: Хешированный пароль
    """
    return password_hash.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Создание JWT access токена.

    Args:
        data: Данные для кодирования в токен (обычно {"sub": user_id})
        expires_delta: Время жизни токена (по умолчанию из настроек)

    Returns:
        str: JWT токен
    """

    to_encode = data.copy()

    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update(
        {
            "exp": expire,
            "type": "access"
         }
    )

    encode_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY.get_secret_value(),
        algorithm=settings.ALGORITHM
    )

    return encode_jwt


def create_refresh_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Создание JWT refresh токена.

    Args:
        data: Данные для кодирования в токен (обычно {"sub": user_id})
        expires_delta: Время жизни токена (по умолчанию из настроек)

    Returns:
        str: JWT токен
    """

    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_MINUTES)

    to_encode.update(
        {
            "exp": expire,
            "type": "refresh"
        })
    encode_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY.get_secret_value(),
        algorithm=settings.ALGORITHM
    )

    return encode_jwt

def decode_token(token) -> Optional[dict]:
    """
    Декодирование и проверка JWT токена.

    Args:
        token: JWT токен

    Returns:
        Optional[dict]: Данные из токена или None если токен невалидный
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY.get_secret_value(),
            algorithms=[settings.ALGORITHM]
        )
        return payload
    except JWTError:
        return None

def generate_verification_code(length: int = 6) -> str:
    """
    Генерация кода подтверждения (для SMS).

    Args:
        length: Длина кода (по умолчанию 6 цифр)

    Returns:
        str: Цифровой код подтверждения
    """
    return ''.join(secrets.choice(string.digits) for _ in range(length))

def generate_random_password(length: int = 16) -> str:
    """
    Генерация случайного пароля (для OAuth или сброса).

    Args:
        length: Длина пароля

    Returns:
        str: Случайный пароль из букв и цифр
    """
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def create_token_pair(user_id: int) -> Tuple[str, str]:
    """
    Создание пары токенов (access + refresh).

    Args:
        user_id: ID пользователя

    Returns:
        Tuple[str, str]: (access_token, refresh_token)
    """
    access_token = create_access_token(data={"sub": str(user_id)})
    refresh_token = create_refresh_token(data={"sub": str(user_id)})
    return access_token, refresh_token

