"""
Pydantic схемы для аутентификации.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional
import re

class PhoneNumberRequest(BaseModel):
    """Запрос на отправку SMS-кода."""
    phone_number: str = Field(..., description="Номер телефона в международном формате")
    @field_validator("phone_number")
    @classmethod
    def validate_phone_number(cls, v: str):
        """Валидация и нормализация номера телефона."""
        # Удаляем все кроме цифр и +
        cleaned = re.sub(r'[^\d\+]', '', v)
        # Проверяем, что номер начинается с +
        if not cleaned.startswith('+'):
            cleaned = '+' + cleaned

        # Базовая проверка длины (минимальная длина номера с кодом страны)
        if len(cleaned) < 10:
            raise ValueError('Некорректный номер телефона')

        return cleaned

class VerifyCodeRequest(BaseModel):
    """Запрос на подтверждение кода."""
    phone_number: str = Field(..., description="Номер телефона")
    code: str = Field(..., min_length=6, max_length=6, description="Код подтверждения")

class RegisterRequest(BaseModel):
    """Запрос на регистрацию."""
    phone_number: str = Field(..., description="Номер телефона")
    verification_code: str = Field(..., min_length=6, max_length=6, description="Код подтверждения")
    username: str = Field(..., min_length=3, max_length=50, description="Имя пользователя")
    password: str = Field(..., min_length=8, max_length=100, description="Пароль")
    full_name: Optional[str] = Field(max_length=100, description="Полное имя")

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        """Валидация username: только буквы, цифры, подчеркивание."""
        if not re.match(r'^[a-zA-Z0-9_]+$', v):
            raise ValueError('Имя пользователя может содержать только буквы, цифры и подчеркивание')
        else:
            return v.lower()

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Валидация пароля."""
        if len(v) < 8:
            raise ValueError('Пароль должен содержать минимум 8 символов')
        if not any(c.isupper() for c in v):
            raise ValueError('Пароль должен содержать хотя бы одну заглавную букву')
        if not any(c.isdigit() for c in v):
            raise ValueError('Пароль должен содержать хотя бы одну цифру')
        return v

    class LoginRequest(BaseModel):
        """Запрос на вход."""
        username: str = Field(..., description="Имя пользователя или номер телефона")
        password: str = Field(..., description="Пароль")

    class TokenResponse(BaseModel):
        """Ответ с токенами."""
        access_token: str
        refresh_token: str
        token_type: str = "bearer"

    class RefreshTokenRequest(BaseModel):
        """Запрос на обновление токенов."""
        refresh_token: str

    class UserResponse(BaseModel):
        """Ответ с данными пользователя."""
        id: int
        phone_number: str
        username: Optional[str]
        full_name: Optional[str]
        bio: Optional[str]
        phone_number_verified: bool
        is_online: bool
        last_seen_at: Optional[str]
        language_code: str
        theme: str
        notifications_enabled: bool

        class Config:
            from_attributes = True

class VerificationCodeResponse(BaseModel):
    """Ответ с информацией о коде (только для разработки)."""
    success: bool
    code: Optional[str] = None  # Только в dev режиме
    expires_in: int = 300  # 5 минут