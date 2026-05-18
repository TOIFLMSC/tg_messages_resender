from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from app.models.domain import IncomingPost, RouteMatch
from app.services.dedupe import RuntimeDedupe

logger = logging.getLogger(__name__)

FinalizeCallback = Callable[[list[IncomingPost], RouteMatch], Awaitable[None]]


@dataclass
class _BufferedGroup:
    route: RouteMatch
    posts: list[IncomingPost] = field(default_factory=list)
    task: asyncio.Task[None] | None = None


class MediaGroupAggregator:
    def __init__(
        self,
        collect_timeout_seconds: float,
        dedupe: RuntimeDedupe,
        on_finalize: FinalizeCallback,
    ) -> None:
        self._timeout = collect_timeout_seconds
        self._dedupe = dedupe
        self._on_finalize = on_finalize
        self._groups: dict[tuple[int, str], _BufferedGroup] = {}
        self._lock = asyncio.Lock()

    async def add(self, post: IncomingPost, route: RouteMatch) -> None:
        if not post.media_group_id:
            raise ValueError("post has no media_group_id")

        key = (post.chat_id, post.media_group_id)
        async with self._lock:
            if self._dedupe.is_media_group_finalized(*key):
                logger.info("publish skipped as duplicate: chat_id=%s media_group_id=%s", *key)
                return

            group = self._groups.get(key)
            if group is None:
                group = _BufferedGroup(route=route)
                self._groups[key] = group
                group.task = asyncio.create_task(self._finalize_later(key))
                logger.info("media group collecting: chat_id=%s media_group_id=%s", *key)

            group.posts.append(post)

    async def shutdown(self) -> None:
        async with self._lock:
            tasks = [group.task for group in self._groups.values() if group.task]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _finalize_later(self, key: tuple[int, str]) -> None:
        await asyncio.sleep(self._timeout)
        await self._finalize(key)

    async def _finalize(self, key: tuple[int, str]) -> None:
        async with self._lock:
            group = self._groups.pop(key, None)
            if group is None:
                return
            if not self._dedupe.mark_media_group_finalized(*key):
                return
            posts = sorted(group.posts, key=lambda item: item.message_id)

        logger.info("media group finalized: chat_id=%s media_group_id=%s items=%s", key[0], key[1], len(posts))
        await self._on_finalize(posts, group.route)
