import asyncio

import pytest

from app.models.config_models import CleanerConfig
from app.models.domain import IncomingPost, RouteMatch
from app.services.dedupe import RuntimeDedupe
from app.services.media_group_aggregator import MediaGroupAggregator


@pytest.mark.asyncio
async def test_aggregator_finalizes_once_and_sorts_by_message_id() -> None:
    finalized: list[list[IncomingPost]] = []
    route = RouteMatch(-1001, -1002, "footer", CleanerConfig())

    async def on_finalize(posts: list[IncomingPost], _: RouteMatch) -> None:
        finalized.append(posts)

    aggregator = MediaGroupAggregator(0.01, RuntimeDedupe(), on_finalize)
    await aggregator.add(IncomingPost(3, -1001, "group", "third", [], None), route)
    await aggregator.add(IncomingPost(1, -1001, "group", "first", [], None), route)
    await asyncio.sleep(0.05)
    await aggregator.shutdown()

    assert len(finalized) == 1
    assert [post.message_id for post in finalized[0]] == [1, 3]
