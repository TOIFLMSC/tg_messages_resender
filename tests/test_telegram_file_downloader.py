from pathlib import Path

import pytest
from aiogram.exceptions import TelegramBadRequest

from app.models.domain import IncomingMedia, MediaKind, MediaSourceType
from app.services.telegram_file_downloader import TelegramFileDownloader


class FakeTelegramFile:
    file_path = "videos/file.mp4"


class SuccessfulBot:
    async def get_file(self, file_id: str) -> FakeTelegramFile:
        return FakeTelegramFile()

    async def download_file(self, file_path: str, destination: Path) -> None:
        destination.write_bytes(b"fake")


class TooBigBot:
    async def get_file(self, file_id: str):
        raise TelegramBadRequest(method=None, message="Bad Request: file is too big")


class BrokenBot:
    async def get_file(self, file_id: str):
        raise TelegramBadRequest(method=None, message="Bad Request: something else")


@pytest.mark.asyncio
async def test_download_success_returns_local_media(tmp_path: Path) -> None:
    downloader = TelegramFileDownloader(SuccessfulBot())

    result = await downloader.download(IncomingMedia(MediaKind.VIDEO, "file-id"), tmp_path)

    assert result.source_type == MediaSourceType.LOCAL
    assert result.path is not None
    assert result.path.exists()
    assert result.file_id is None


@pytest.mark.asyncio
async def test_file_too_big_falls_back_to_telegram_file_id(tmp_path: Path) -> None:
    downloader = TelegramFileDownloader(TooBigBot())

    result = await downloader.download(IncomingMedia(MediaKind.VIDEO, "large-video-file-id"), tmp_path)

    assert result.source_type == MediaSourceType.TELEGRAM_FILE_ID
    assert result.file_id == "large-video-file-id"
    assert result.path is None


@pytest.mark.asyncio
async def test_other_download_error_also_falls_back_to_telegram_file_id(tmp_path: Path) -> None:
    downloader = TelegramFileDownloader(BrokenBot())

    result = await downloader.download(IncomingMedia(MediaKind.ANIMATION, "animation-file-id"), tmp_path)

    assert result.source_type == MediaSourceType.TELEGRAM_FILE_ID
    assert result.file_id == "animation-file-id"
    assert result.path is None
