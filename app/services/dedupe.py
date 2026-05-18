from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class RuntimeDedupe:
    max_message_keys: int = 5000
    _message_keys: set[tuple[int, int]] = field(default_factory=set)
    _message_order: deque[tuple[int, int]] = field(default_factory=deque)
    _finalized_media_groups: set[tuple[int, str]] = field(default_factory=set)

    def seen_message(self, chat_id: int, message_id: int) -> bool:
        key = (chat_id, message_id)
        if key in self._message_keys:
            logger.info("publish skipped as duplicate: chat_id=%s message_id=%s", chat_id, message_id)
            return True
        self._message_keys.add(key)
        self._message_order.append(key)
        while len(self._message_order) > self.max_message_keys:
            old = self._message_order.popleft()
            self._message_keys.discard(old)
        return False

    def mark_media_group_finalized(self, chat_id: int, media_group_id: str) -> bool:
        key = (chat_id, media_group_id)
        if key in self._finalized_media_groups:
            logger.info("publish skipped as duplicate: chat_id=%s media_group_id=%s", chat_id, media_group_id)
            return False
        self._finalized_media_groups.add(key)
        return True

    def is_media_group_finalized(self, chat_id: int, media_group_id: str) -> bool:
        return (chat_id, media_group_id) in self._finalized_media_groups
