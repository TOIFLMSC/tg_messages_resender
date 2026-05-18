from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any


class MediaKind(StrEnum):
    PHOTO = "photo"
    VIDEO = "video"
    ANIMATION = "animation"


class MediaSourceType(StrEnum):
    LOCAL = "local"
    TELEGRAM_FILE_ID = "telegram_file_id"


@dataclass(frozen=True)
class TextEntity:
    type: str
    offset: int
    length: int
    url: str | None = None
    user: Any | None = None
    language: str | None = None
    custom_emoji_id: str | None = None


@dataclass(frozen=True)
class CleanedText:
    text: str
    entities: list[TextEntity] = field(default_factory=list)


@dataclass(frozen=True)
class PublishMedia:
    kind: MediaKind
    source_type: MediaSourceType
    path: Path | None = None
    file_id: str | None = None

    @classmethod
    def local(cls, kind: MediaKind, path: Path) -> "PublishMedia":
        return cls(kind=kind, source_type=MediaSourceType.LOCAL, path=path)

    @classmethod
    def telegram_file_id(cls, kind: MediaKind, file_id: str) -> "PublishMedia":
        return cls(kind=kind, source_type=MediaSourceType.TELEGRAM_FILE_ID, file_id=file_id)

    def __post_init__(self) -> None:
        if self.source_type == MediaSourceType.LOCAL and self.path is None:
            raise ValueError("local media source requires path")
        if self.source_type == MediaSourceType.TELEGRAM_FILE_ID and not self.file_id:
            raise ValueError("telegram_file_id media source requires file_id")


@dataclass(frozen=True)
class IncomingMedia:
    kind: MediaKind
    file_id: str


@dataclass
class IncomingPost:
    message_id: int
    chat_id: int
    media_group_id: str | None
    text: str
    entities: list[TextEntity]
    media: IncomingMedia | None


@dataclass(frozen=True)
class RouteMatch:
    source_channel_id: int
    target_channel_id: int
    footer_text: str
    cleaner_config: Any
