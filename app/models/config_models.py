from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class BotConfig(BaseModel):
    token: str = Field(min_length=1)
    log_level: str = "INFO"
    temp_dir: Path = Path("./tmp")
    media_group_collect_timeout_seconds: float = Field(default=1.5, gt=0)

    @field_validator("token")
    @classmethod
    def token_must_not_be_placeholder(cls, value: str) -> str:
        if value == "PUT_BOT_TOKEN_HERE":
            raise ValueError("bot.token must be replaced with a real token")
        return value


class CleanerConfig(BaseModel):
    remove_lines_with_urls: bool = True
    remove_markdown_links: bool = True
    remove_html_links: bool = True
    remove_tg_channel_mentions: bool = True
    preserve_hashtags: bool = True
    preserve_formatting: bool = True
    trim_extra_blank_lines: bool = True


class RouteConfig(BaseModel):
    source_channel_id: int
    target_channel_id: int
    footer_text: str = Field(min_length=1)
    cleaner: CleanerConfig = Field(default_factory=CleanerConfig)

    @model_validator(mode="after")
    def channels_must_differ(self) -> "RouteConfig":
        if self.source_channel_id == self.target_channel_id:
            raise ValueError("source_channel_id and target_channel_id must differ")
        return self


class PublishingConfig(BaseModel):
    split_media_groups_over_10: bool = True
    max_media_per_album: int = Field(default=10, ge=2, le=10)
    caption_overflow_strategy: Literal["send_followup_message"] = "send_followup_message"
    disable_notification: bool = False


class AppConfig(BaseModel):
    bot: BotConfig
    routes: list[RouteConfig] = Field(min_length=1)
    publishing: PublishingConfig = Field(default_factory=PublishingConfig)
