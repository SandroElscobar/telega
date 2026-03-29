"""
Клиент для работы с MinIO (S3-совместимое хранилище).
"""
import io
import json
from typing import Optional
from pydantic import Field
from minio import Minio
from minio.error import S3Error
from datetime import datetime
import logging
import uuid


from app.core.config import settings

logger = logging.getLogger(__name__)

class MinIOClient:
    """
    Клиент для работы с MinIO.
    Управляет загрузкой, скачиванием и удалением файлов.
    """
    def __init__(self):
        self.client = None
        self.bucket_name = "messanger-media"
        self._initialized = False

    async def initialize(self):
        """Инициализация клиента MinIO."""
        if self._initialized:
            return

        try:
            self.client = Minio(
                settings.MINIO_ENDPOINT,
                access_key=settings.MINIO_ACCESS_KEY,
                secret_key=settings.MINIO_SECRET_KEY,
                secure=settings.MINIO_SECURE,
            )

            # Создаем bucket если не существует
            if not self.client.bucket_exists(self.bucket_name):
                self.client.make_bucket(self.bucket_name)
                logger.info(f"Создан bucket: {self.bucket_name}")

                # Устанавливаем политику публичного доступа к файлам
                policy = {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Effect": "Allow",
                            "Principal": {"AWS": ["*"]},
                            "Action": ["s3:GetObject"],
                            "Resource": [f"arn:aws:s3:::{self.bucket_name}/*"],
                        }
                    ],
                }
                self.client.set_bucket_policy(self.bucket_name, json.dumps(policy))

            self._initialized = True
            logger.info(f"MinIO клиент инициализирован: {settings.MINIO_ENDPOINT}")

        except Exception as e:
            logger.error(f"Ошибка инициализации MinIO: {e}")
            raise

    async def upload_file(
            self,
            file_data: bytes,
            file_name: str = Field(..., min_length=1, max_length=255),
            content_type: str = "application/octet-stream",
            folder: str = "general"
    ) -> str:
        """
        Загрузка файла в MinIO.

        Args:
            file_data: Байты файла
            file_name: Имя файла
            content_type: MIME тип
            folder: Папка для организации файлов

        Returns:
            URL файла
        """
        if not self._initialized:
            await self.initialize()

        try:
            # Формируем путь: folder/yyyy/mm/dd/uuid_filename
            date_path = datetime.now().strftime("%Y/%m/%d")
            unique_name = f"{uuid.uuid4().hex}_{file_name}"
            object_name = f"{folder}/{date_path}/{unique_name}"

            # Создаем объект в MinIO
            file_size = len(file_data)
            file_stream = io.BytesIO(file_data)

            self.client.put_object(
                bucket_name=self.bucket_name,
                object_name=object_name,
                data=file_stream,
                length=file_size,
                content_type=content_type,
            )

            # Формируем URL
            url = f"{settings.MINIO_PUBLIC_URL}/{self.bucket_name}/{object_name}"
            logger.info(f"Файл загружен: {url}")

            return url

        except S3Error as e:
            logger.error(f"Ошибка загрузки файла в MinIO: {e}")
            raise

    async def get_file(self, object_name: str) -> Optional[bytes]:
        """Скачивание файла из MinIO."""
        if not self._initialized:
            await self.initialize()

        try:
            response = self.client.get_object(
                bucket_name=self.bucket_name,
                object_name=object_name,
            )
            data = response.read()
            response.close()
            response.release_conn()
            return data

        except S3Error as e:
            logger.error(f"Ошибка скачивания файла: {e}")
            return None

    async def delete_file(self, object_name: str) -> bool:
        """Удаление файла из MinIO."""
        if not self._initialized:
            await self.initialize()

        try:
            self.client.remove_object(
                bucket_name=self.bucket_name,
                object_name=object_name,
            )
            logger.info(f"Файл удален: {object_name}")
            return True

        except S3Error as e:
            logger.error(f"Ошибка удаления файла: {e}")
            return False

    async def get_presigned_url(self, object_name: str, expires: int = 3600) -> Optional[str]:
        """Получение временной ссылки на файл."""
        if not self._initialized:
            await self.initialize()

        try:
            url = self.client.presigned_get_object(
                bucket_name=self.bucket_name,
                object_name=object_name,
                expires=expires,
            )
            return url

        except S3Error as e:
            logger.error(f"Ошибка получения presigned URL: {e}")
            return None

# Глобальный экземпляр
minio_client = MinIOClient()