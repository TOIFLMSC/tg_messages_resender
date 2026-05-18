from __future__ import annotations

import logging
from dataclasses import dataclass

from aiogram import Bot
from aiogram.types import FSInputFile, InputMediaAnimation, InputMediaPhoto, InputMediaVideo

from app.models.config_models import PublishingConfig
from app.models.domain import CleanedText, MediaKind, MediaSourceType, PublishMedia
from app.utils.entities import domain_entities_to_aiogram

logger = logging.getLogger(__name__)

CAPTION_LIMIT = 1024
MESSAGE_TEXT_LIMIT = 4096


@dataclass(slots=True)
class Publisher:
    bot: Bot
    config: PublishingConfig

    async def publish_text(self, target_chat_id: int, text: CleanedText) -> None:
        logger.info("publish started: target=%s type=text", target_chat_id)
        await self.bot.send_message(
            chat_id=target_chat_id,
            text=text.text[:MESSAGE_TEXT_LIMIT],
            entities=domain_entities_to_aiogram(text.entities),
            parse_mode=None,
            disable_notification=self.config.disable_notification,
        )
        logger.info("publish success: target=%s type=text", target_chat_id)

    async def publish_single_media(
        self,
        target_chat_id: int,
        media: PublishMedia,
        text: CleanedText,
    ) -> None:
        logger.info("publish started: target=%s type=%s", target_chat_id, media.kind)
        caption, caption_entities, followup = self._caption_or_followup(text)
        input_file = self._media_input(media)
        self._log_media_source(media)

        if media.kind == MediaKind.PHOTO:
            await self.bot.send_photo(
                chat_id=target_chat_id,
                photo=input_file,
                caption=caption,
                caption_entities=caption_entities,
                parse_mode=None,
                disable_notification=self.config.disable_notification,
            )
        elif media.kind == MediaKind.VIDEO:
            await self.bot.send_video(
                chat_id=target_chat_id,
                video=input_file,
                caption=caption,
                caption_entities=caption_entities,
                parse_mode=None,
                disable_notification=self.config.disable_notification,
            )
        elif media.kind == MediaKind.ANIMATION:
            await self.bot.send_animation(
                chat_id=target_chat_id,
                animation=input_file,
                caption=caption,
                caption_entities=caption_entities,
                parse_mode=None,
                disable_notification=self.config.disable_notification,
            )
        else:
            raise ValueError(f"Unsupported media kind: {media.kind}")

        if followup:
            await self.publish_text(target_chat_id, followup)
        logger.info("publish success: target=%s type=%s", target_chat_id, media.kind)

    async def publish_media_group(
        self,
        target_chat_id: int,
        media_items: list[PublishMedia],
        text: CleanedText,
    ) -> None:
        logger.info("publish started: target=%s type=media_group items=%s", target_chat_id, len(media_items))
        if not media_items:
            await self.publish_text(target_chat_id, text)
            return

        groupable = [item for item in media_items if item.kind in {MediaKind.PHOTO, MediaKind.VIDEO}]
        non_groupable = [item for item in media_items if item.kind not in {MediaKind.PHOTO, MediaKind.VIDEO}]
        caption, caption_entities, followup = self._caption_or_followup(text)

        chunks = self._chunks(groupable, self.config.max_media_per_album)
        for chunk_index, chunk in enumerate(chunks):
            media_group = []
            for item_index, item in enumerate(chunk):
                item_caption = caption if chunk_index == 0 and item_index == 0 else None
                item_entities = caption_entities if chunk_index == 0 and item_index == 0 else None
                self._log_media_source(item)
                media_group.append(self._to_input_media(item, item_caption, item_entities))
            await self.bot.send_media_group(
                chat_id=target_chat_id,
                media=media_group,
                disable_notification=self.config.disable_notification,
            )

        for item_index, item in enumerate(non_groupable):
            non_group_text = text if not groupable and item_index == 0 else CleanedText("")
            await self.publish_single_media(target_chat_id, item, non_group_text)

        if followup and groupable:
            await self.publish_text(target_chat_id, followup)
        logger.info("publish success: target=%s type=media_group", target_chat_id)

    def _caption_or_followup(self, text: CleanedText) -> tuple[str | None, list | None, CleanedText | None]:
        if not text.text:
            return None, None, None
        if len(text.text) <= CAPTION_LIMIT:
            return text.text, domain_entities_to_aiogram(text.entities), None
        return None, None, text

    def _media_input(self, media: PublishMedia):
        if media.source_type == MediaSourceType.LOCAL:
            return FSInputFile(media.path)
        return media.file_id

    def _log_media_source(self, media: PublishMedia) -> None:
        if media.source_type == MediaSourceType.LOCAL:
            logger.info("publish via local file: kind=%s path=%s", media.kind, media.path)
        else:
            logger.info("publish via telegram file_id: kind=%s file_id=%s", media.kind, media.file_id)

    def _to_input_media(self, media: PublishMedia, caption: str | None, caption_entities: list | None):
        media_input = self._media_input(media)
        if media.kind == MediaKind.PHOTO:
            return InputMediaPhoto(
                media=media_input,
                caption=caption,
                caption_entities=caption_entities,
                parse_mode=None,
            )
        if media.kind == MediaKind.VIDEO:
            return InputMediaVideo(
                media=media_input,
                caption=caption,
                caption_entities=caption_entities,
                parse_mode=None,
            )
        if media.kind == MediaKind.ANIMATION:
            return InputMediaAnimation(
                media=media_input,
                caption=caption,
                caption_entities=caption_entities,
                parse_mode=None,
            )
        raise ValueError(f"Unsupported media kind: {media.kind}")

    def _chunks(self, items: list[PublishMedia], size: int) -> list[list[PublishMedia]]:
        return [items[index : index + size] for index in range(0, len(items), size)]
