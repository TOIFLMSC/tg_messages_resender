from pathlib import Path

import pytest

from app.models.config_models import PublishingConfig
from app.models.domain import CleanedText, MediaKind, PublishMedia, TextEntity
from app.services.publisher import Publisher
from app.utils.entities import py_index_to_utf16_offset, utf16_len


class FakeBot:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    async def send_message(self, **kwargs):
        self.calls.append(("send_message", kwargs))

    async def send_photo(self, **kwargs):
        self.calls.append(("send_photo", kwargs))

    async def send_video(self, **kwargs):
        self.calls.append(("send_video", kwargs))

    async def send_animation(self, **kwargs):
        self.calls.append(("send_animation", kwargs))

    async def send_media_group(self, **kwargs):
        self.calls.append(("send_media_group", kwargs))


def footer_text() -> CleanedText:
    text = "Пример текста\n\n🖤 Channel 🖤"
    return CleanedText(
        text=text,
        entities=[
            TextEntity(
                type="text_link",
                offset=py_index_to_utf16_offset(text, text.index("Channel")),
                length=utf16_len("Channel"),
                url="https://t.me/channellink",
            )
        ],
    )


@pytest.mark.asyncio
async def test_publish_text_uses_entities_without_parse_mode() -> None:
    bot = FakeBot()
    publisher = Publisher(bot, PublishingConfig())

    await publisher.publish_text(-1002, footer_text())

    method, kwargs = bot.calls[0]
    assert method == "send_message"
    assert kwargs["parse_mode"] is None
    assert kwargs["text"] == "Пример текста\n\n🖤 Channel 🖤"
    assert kwargs["entities"][0].type == "text_link"
    assert kwargs["entities"][0].url == "https://t.me/channellink"


@pytest.mark.asyncio
async def test_publish_single_media_caption_uses_entities_without_parse_mode(tmp_path: Path) -> None:
    media_path = tmp_path / "photo.jpg"
    media_path.write_bytes(b"fake")
    bot = FakeBot()
    publisher = Publisher(bot, PublishingConfig())

    await publisher.publish_single_media(-1002, PublishMedia.local(MediaKind.PHOTO, media_path), footer_text())

    method, kwargs = bot.calls[0]
    assert method == "send_photo"
    assert kwargs["parse_mode"] is None
    assert kwargs["caption"] == "Пример текста\n\n🖤 Channel 🖤"
    assert kwargs["caption_entities"][0].type == "text_link"
    assert kwargs["caption_entities"][0].url == "https://t.me/channellink"


@pytest.mark.asyncio
async def test_publish_media_group_caption_uses_entities_without_parse_mode(tmp_path: Path) -> None:
    media_path = tmp_path / "photo.jpg"
    media_path.write_bytes(b"fake")
    bot = FakeBot()
    publisher = Publisher(bot, PublishingConfig())

    await publisher.publish_media_group(-1002, [PublishMedia.local(MediaKind.PHOTO, media_path)], footer_text())

    method, kwargs = bot.calls[0]
    assert method == "send_media_group"
    first_media = kwargs["media"][0]
    assert first_media.parse_mode is None
    assert first_media.caption == "Пример текста\n\n🖤 Channel 🖤"
    assert first_media.caption_entities[0].type == "text_link"
    assert first_media.caption_entities[0].url == "https://t.me/channellink"


@pytest.mark.asyncio
async def test_publish_single_media_can_use_telegram_file_id() -> None:
    bot = FakeBot()
    publisher = Publisher(bot, PublishingConfig())

    await publisher.publish_single_media(
        -1002,
        PublishMedia.telegram_file_id(MediaKind.VIDEO, "video-file-id"),
        footer_text(),
    )

    method, kwargs = bot.calls[0]
    assert method == "send_video"
    assert kwargs["video"] == "video-file-id"
    assert kwargs["caption"] == "Пример текста\n\n🖤 Channel 🖤"
    assert kwargs["caption_entities"][0].url == "https://t.me/channellink"


@pytest.mark.asyncio
async def test_publish_media_group_can_mix_local_and_telegram_file_id(tmp_path: Path) -> None:
    media_path = tmp_path / "photo.jpg"
    media_path.write_bytes(b"fake")
    bot = FakeBot()
    publisher = Publisher(bot, PublishingConfig())

    await publisher.publish_media_group(
        -1002,
        [
            PublishMedia.local(MediaKind.PHOTO, media_path),
            PublishMedia.telegram_file_id(MediaKind.VIDEO, "video-file-id"),
        ],
        footer_text(),
    )

    method, kwargs = bot.calls[0]
    assert method == "send_media_group"
    assert kwargs["media"][0].media.path == media_path
    assert kwargs["media"][1].media == "video-file-id"
