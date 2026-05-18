from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest

from app.models.domain import IncomingMedia, PublishMedia

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class TelegramFileDownloader:
    bot: Bot

    async def download(self, media: IncomingMedia, destination_dir: Path) -> PublishMedia:
        logger.info("local media download started: kind=%s file_id=%s", media.kind, media.file_id)
        try:
            file = await self.bot.get_file(media.file_id)
            suffix = Path(file.file_path or "").suffix or self._default_suffix(media.kind)
            destination = destination_dir / f"{media.kind}-{uuid4().hex}{suffix}"
            await self.bot.download_file(file.file_path, destination=destination)
            logger.info("local media download success: kind=%s path=%s", media.kind, destination)
            logger.info("file downloaded: kind=%s path=%s", media.kind, destination)
            return PublishMedia.local(kind=media.kind, path=destination)
        except TelegramBadRequest as exc:
            if self._is_file_too_big_error(exc):
                logger.info(
                    "local media download failed because file is too big, fallback to telegram file_id: "
                    "kind=%s file_id=%s",
                    media.kind,
                    media.file_id,
                )
            else:
                logger.exception(
                    "local media download failed, fallback to telegram file_id: kind=%s file_id=%s",
                    media.kind,
                    media.file_id,
                )
            logger.info("local media download skipped: using telegram file_id kind=%s", media.kind)
            return PublishMedia.telegram_file_id(kind=media.kind, file_id=media.file_id)
        except Exception:
            logger.exception(
                "local media download failed, fallback to telegram file_id: kind=%s file_id=%s",
                media.kind,
                media.file_id,
            )
            logger.info("local media download skipped: using telegram file_id kind=%s", media.kind)
            return PublishMedia.telegram_file_id(kind=media.kind, file_id=media.file_id)

    def _is_file_too_big_error(self, exc: TelegramBadRequest) -> bool:
        return "file is too big" in str(exc).lower()

    def _default_suffix(self, kind: str) -> str:
        return {
            "photo": ".jpg",
            "video": ".mp4",
            "animation": ".gif",
        }.get(str(kind), ".bin")
