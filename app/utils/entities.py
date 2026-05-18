from __future__ import annotations

from typing import Iterable

from aiogram.types import MessageEntity

from app.models.domain import TextEntity


def utf16_len(text: str) -> int:
    return len(text.encode("utf-16-le")) // 2


def utf16_offset_to_py_index(text: str, offset: int) -> int | None:
    units = 0
    for index, char in enumerate(text):
        if units == offset:
            return index
        units += utf16_len(char)
        if units > offset:
            return None
    return len(text) if units == offset else None


def py_index_to_utf16_offset(text: str, index: int) -> int:
    return utf16_len(text[:index])


def aiogram_entities_to_domain(entities: Iterable[MessageEntity] | None) -> list[TextEntity]:
    if not entities:
        return []
    return [
        TextEntity(
            type=entity.type,
            offset=entity.offset,
            length=entity.length,
            url=entity.url,
            user=entity.user,
            language=entity.language,
            custom_emoji_id=entity.custom_emoji_id,
        )
        for entity in entities
    ]


def domain_entities_to_aiogram(entities: Iterable[TextEntity]) -> list[MessageEntity]:
    return [
        MessageEntity(
            type=entity.type,
            offset=entity.offset,
            length=entity.length,
            url=entity.url,
            user=entity.user,
            language=entity.language,
            custom_emoji_id=entity.custom_emoji_id,
        )
        for entity in entities
    ]
