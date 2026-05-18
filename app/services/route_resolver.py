from __future__ import annotations

import logging
from dataclasses import dataclass

from app.models.config_models import AppConfig
from app.models.domain import RouteMatch

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RouteResolver:
    config: AppConfig

    def match(self, chat_id: int) -> RouteMatch | None:
        for route in self.config.routes:
            if route.source_channel_id == chat_id:
                logger.info("route matched: source=%s target=%s", route.source_channel_id, route.target_channel_id)
                return RouteMatch(
                    source_channel_id=route.source_channel_id,
                    target_channel_id=route.target_channel_id,
                    footer_text=route.footer_text,
                    cleaner_config=route.cleaner,
                )
        return None
