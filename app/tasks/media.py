"""
Задачи для обработки медиафайлов.
"""
import logging
from PIL import Image
import io

from app.core.celery_app import celery_app, task
from app.core.minio_client import minio_client

logger = logging.getLogger(__name__)


@task(queue="media")
async def process_uploaded_image(file_data: bytes, file_name: str) -> dict:
    """
    Обработка загруженного изображения:
    - Создание миниатюр
    - Оптимизация размера
    - Определение размеров
    """
    try:
        # Открываем изображение
        img = Image.open(io.BytesIO(file_data))

        # Получаем размеры
        width, height = img.size

        # Создаем миниатюру (200px по большей стороне)
        thumbnail_size = 200
        if width > height:
            new_width = thumbnail_size
            new_height = int(height * (thumbnail_size / width))
        else:
            new_height = thumbnail_size
            new_width = int(width * (thumbnail_size / height))

        img.thumbnail((new_width, new_height), Image.Resampling.LANCZOS)

        # Сохраняем миниатюру
        thumb_io = io.BytesIO()
        img.save(thumb_io, format='JPEG', quality=85)
        thumb_data = thumb_io.getvalue()

        # Загружаем миниатюру
        thumb_url = await minio_client.upload_file(
            thumb_data,
            f"thumb_{file_name}",
            "image/jpeg",
            folder="thumbnails"
        )

        return {
            "width": width,
            "height": height,
            "thumbnail_url": thumb_url,
            "processed": True
        }

    except Exception as e:
        logger.error(f"Ошибка обработки изображения: {e}")
        raise


@task(queue="media")
def process_video_thumbnail(video_data: bytes, file_name: str) -> str:
    """
    Создание миниатюры для видео.
    """
    # TODO: Интеграция с ffmpeg
    # Пока возвращаем заглушку
    return None