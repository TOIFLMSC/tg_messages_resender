from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from app.models.domain import IncomingPost, RouteMatch
from app.services.telegram_file_downloader import TelegramFileDownloader
from app.services.publisher import Publisher
from app.services.text_cleaner import TextCleaner
from app.utils.tempfiles import temporary_media_dir

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class PostProcessor:
    temp_dir: Path
    downloader: TelegramFileDownloader
    publisher: Publisher

    async def process_single(self, post: IncomingPost, route: RouteMatch) -> None:
        await self.process_many([post], route)

    async def process_many(self, posts: list[IncomingPost], route: RouteMatch) -> None:
        try:
            cleaner = TextCleaner(route.cleaner_config)
            source_text_post = next((post for post in posts if post.text), posts[0])
            cleaned = cleaner.clean(source_text_post.text, source_text_post.entities)
            final_text = cleaner.with_footer(cleaned, route.footer_text)

            async with temporary_media_dir(self.temp_dir) as media_dir:
                media_items = []
                for post in posts:
                    if post.media is None:
                        continue
                    media_items.append(await self.downloader.download(post.media, media_dir))

                if not media_items:
                    await self.publisher.publish_text(route.target_channel_id, final_text)
                elif len(media_items) == 1:
                    await self.publisher.publish_single_media(route.target_channel_id, media_items[0], final_text)
                else:
                    await self.publisher.publish_media_group(route.target_channel_id, media_items, final_text)
        except Exception:
            ids = [post.message_id for post in posts]
            logger.exception("publish failed: target=%s message_ids=%s", route.target_channel_id, ids)
