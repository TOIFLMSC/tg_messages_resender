from __future__ import annotations

import logging
from dataclasses import dataclass

from aiogram import Router
from aiogram.types import Message

from app.models.domain import IncomingMedia, IncomingPost, MediaKind
from app.services.dedupe import RuntimeDedupe
from app.services.media_group_aggregator import MediaGroupAggregator
from app.services.post_processor import PostProcessor
from app.services.route_resolver import RouteResolver
from app.utils.entities import aiogram_entities_to_domain

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ChannelPostHandler:
    route_resolver: RouteResolver
    dedupe: RuntimeDedupe
    media_group_aggregator: MediaGroupAggregator
    post_processor: PostProcessor

    def router(self) -> Router:
        router = Router(name="channel_posts")
        router.channel_post.register(self.handle)
        return router

    async def handle(self, message: Message) -> None:
        chat_id = message.chat.id
        logger.info("message received: chat_id=%s message_id=%s", chat_id, message.message_id)

        route = self.route_resolver.match(chat_id)
        if route is None:
            return

        if self.dedupe.seen_message(chat_id, message.message_id):
            return

        post = self._to_incoming_post(message)
        if post is None:
            logger.info("unsupported post skipped: chat_id=%s message_id=%s", chat_id, message.message_id)
            return

        if post.media_group_id:
            await self.media_group_aggregator.add(post, route)
            return

        await self.post_processor.process_single(post, route)

    def _to_incoming_post(self, message: Message) -> IncomingPost | None:
        text = message.text or message.caption or ""
        entities = aiogram_entities_to_domain(message.entities or message.caption_entities)
        media = self._extract_media(message)

        if not text and media is None:
            return None

        return IncomingPost(
            message_id=message.message_id,
            chat_id=message.chat.id,
            media_group_id=message.media_group_id,
            text=text,
            entities=entities,
            media=media,
        )

    def _extract_media(self, message: Message) -> IncomingMedia | None:
        if message.photo:
            return IncomingMedia(kind=MediaKind.PHOTO, file_id=message.photo[-1].file_id)
        if message.video:
            return IncomingMedia(kind=MediaKind.VIDEO, file_id=message.video.file_id)
        if message.animation:
            return IncomingMedia(kind=MediaKind.ANIMATION, file_id=message.animation.file_id)
        return None
