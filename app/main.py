from __future__ import annotations

import argparse
import asyncio
import logging

from aiogram import Bot, Dispatcher

from app.config import load_config
from app.handlers.channel_posts import ChannelPostHandler
from app.logging_setup import setup_logging
from app.services.dedupe import RuntimeDedupe
from app.services.media_group_aggregator import MediaGroupAggregator
from app.services.post_processor import PostProcessor
from app.services.publisher import Publisher
from app.services.route_resolver import RouteResolver
from app.services.telegram_file_downloader import TelegramFileDownloader

logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Telegram channel post repacker bot")
    parser.add_argument("--config", default="config.yaml", help="Path to YAML config")
    return parser.parse_args()


async def run() -> None:
    args = parse_args()
    config = load_config(args.config)
    setup_logging(config.bot.log_level)
    logger.info("config loaded: %s", args.config)

    bot = Bot(token=config.bot.token)
    dispatcher = Dispatcher()
    dedupe = RuntimeDedupe()
    downloader = TelegramFileDownloader(bot)
    publisher = Publisher(bot, config.publishing)
    processor = PostProcessor(config.bot.temp_dir, downloader, publisher)
    resolver = RouteResolver(config)
    aggregator = MediaGroupAggregator(
        collect_timeout_seconds=config.bot.media_group_collect_timeout_seconds,
        dedupe=dedupe,
        on_finalize=processor.process_many,
    )

    channel_handler = ChannelPostHandler(
        route_resolver=resolver,
        dedupe=dedupe,
        media_group_aggregator=aggregator,
        post_processor=processor,
    )
    dispatcher.include_router(channel_handler.router())

    try:
        logger.info("bot started")
        await dispatcher.start_polling(bot, allowed_updates=["channel_post"])
    finally:
        await aggregator.shutdown()
        await bot.session.close()


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
