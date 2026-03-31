"""
Задачи для обработки медиафайлов.
"""
import logging
from PIL import Image
import io
import asyncio

from app.core.celery_app import celery_app, task
from app.core.minio_client import minio_client

logger = logging.getLogger(__name__)


@task(queue="media")
def process_uploaded_image(file_data: bytes, file_name: str) -> dict:
    """
    Обработка загруженного изображения (синхронная версия).
    """
    try:
        # Открываем изображение
        img = Image.open(io.BytesIO(file_data))

        # Получаем размеры
        width, height = img.size

        # Создаем миниатюру
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

        # Загружаем миниатюру (синхронный вызов)
        thumb_url = asyncio.run(minio_client.upload_file(
            thumb_data,
            f"thumb_{file_name}",
            "image/jpeg",
            folder="thumbnails"
        ))

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
def process_video_thumbnail(video_data: bytes, file_name: str) -> dict:
    """
    Создание миниатюры для видео.
    """
    try:
        # TODO: Интеграция с ffmpeg
        # Используем ffmpeg-python или subprocess
        # Пример с ffmpeg-python:
        # import ffmpeg
        #
        # async def _process():
        #     # Сохраняем временный файл
        #     temp_input = f"/tmp/{file_name}"
        #     temp_output = f"/tmp/thumb_{file_name}.jpg"
        #
        #     with open(temp_input, 'wb') as f:
        #         f.write(video_data)
        #
        #     # Извлекаем кадр на 1 секунде
        #     (
        #         ffmpeg
        #         .input(temp_input, ss=1)
        #         .output(temp_output, vframes=1)
        #         .run(quiet=True)
        #     )
        #
        #     # Читаем миниатюру
        #     with open(temp_output, 'rb') as f:
        #         thumb_data = f.read()
        #
        #     # Загружаем в MinIO
        #     thumb_url = await minio_client.upload_file(
        #         thumb_data,
        #         f"thumb_{file_name}.jpg",
        #         "image/jpeg",
        #         folder="thumbnails"
        #     )
        #
        #     # Очищаем временные файлы
        #     os.unlink(temp_input)
        #     os.unlink(temp_output)
        #
        #     return {"thumbnail_url": thumb_url}
        #
        # return asyncio.run(_process())

        # Пока возвращаем заглушку
        return {
            "thumbnail_url": None,
            "processed": False,
            "message": "Video processing not implemented yet"
        }

    except Exception as e:
        logger.error(f"Ошибка обработки видео: {e}")
        raise


@task(queue="media", bind=True, max_retries=3)
def process_media_batch(self, media_items: list) -> dict:
    """
    Пакетная обработка медиафайлов с поддержкой retry.
    """
    results = []
    failed_items = []

    for item in media_items:
        try:
            if item['type'] == 'image':
                result = process_uploaded_image(item['data'], item['name'])
            elif item['type'] == 'video':
                result = process_video_thumbnail(item['data'], item['name'])
            else:
                result = {"error": f"Unknown type: {item['type']}"}

            results.append(result)

        except Exception as e:
            logger.error(f"Failed to process {item['name']}: {e}")
            failed_items.append(item)

    # Если есть неудачные элементы и есть попытки, ретраим
    if failed_items and self.request.retries < self.max_retries:
        raise self.retry(
            exc=Exception(f"Failed items: {len(failed_items)}"),
            countdown=60 * (2 ** self.request.retries)  # Экспоненциальная задержка
        )

    return {
        "processed": len(results),
        "failed": len(failed_items),
        "results": results
    }