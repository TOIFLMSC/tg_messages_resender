from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from app.models.config_models import CleanerConfig
from app.models.domain import CleanedText, TextEntity
from app.utils.entities import py_index_to_utf16_offset, utf16_offset_to_py_index, utf16_len

logger = logging.getLogger(__name__)

URL_RE = re.compile(r"(?i)\b(?:https?://|www\.)\S+")
TG_RE = re.compile(r"(?i)(?:https?://)?(?:t\.me|telegram\.me|telegram\.dog)/\S+|tg://\S+")
MARKDOWN_LINK_RE = re.compile(r"\[[^\]\n]+\]\((?:https?://|tg://|(?:https?://)?t\.me/)[^)]+\)")
HTML_LINK_RE = re.compile(r"(?is)<a\s+[^>]*href\s*=\s*['\"][^'\"]+['\"][^>]*>.*?</a>")
MENTION_RE = re.compile(r"(?<![\w.])@[A-Za-z0-9_]{4,32}\b")
PROMO_WORDS_RE = re.compile(
    r"(?i)\b(?:telegram|канал|подпис|источник|source|join|follow|читать|наш\s+чат)\b"
)

LINK_ENTITY_TYPES = {"url", "text_link", "text_mention", "mention"}


@dataclass(slots=True)
class TextCleaner:
    config: CleanerConfig

    def clean(self, text: str | None, entities: list[TextEntity] | None = None) -> CleanedText:
        if not text:
            return CleanedText("")

        entities = entities or []
        removed_ranges = self._line_ranges_to_remove(text, entities)
        if self.config.trim_extra_blank_lines:
            removed_ranges = self._merge_ranges(removed_ranges + self._blank_line_ranges_to_remove(text, removed_ranges))
        if not removed_ranges:
            logger.info("text cleaned: original_len=%s cleaned_len=%s", len(text), len(text))
            return CleanedText(text, self._drop_invalid_entities(text, entities))

        kept_chars: list[str] = []
        kept_old_indexes: list[int] = []
        remove_cursor = 0
        sorted_ranges = sorted(removed_ranges)

        for index, char in enumerate(text):
            while remove_cursor < len(sorted_ranges) and index >= sorted_ranges[remove_cursor][1]:
                remove_cursor += 1
            should_remove = (
                remove_cursor < len(sorted_ranges)
                and sorted_ranges[remove_cursor][0] <= index < sorted_ranges[remove_cursor][1]
            )
            if not should_remove:
                kept_chars.append(char)
                kept_old_indexes.append(index)

        cleaned_text = "".join(kept_chars)

        cleaned_entities = self._recalculate_entities(text, cleaned_text, entities, removed_ranges)
        logger.info("text cleaned: original_len=%s cleaned_len=%s", len(text), len(cleaned_text))
        return CleanedText(cleaned_text, cleaned_entities)

    def with_footer(self, cleaned: CleanedText, footer_markdown: str) -> CleanedText:
        footer = self._footer_to_text_and_entities(footer_markdown)
        if cleaned.text.strip():
            separator = "\n\n"
            text = cleaned.text.rstrip() + separator + footer.text
            shift = py_index_to_utf16_offset(text, len(cleaned.text.rstrip() + separator))
        else:
            text = footer.text
            shift = 0

        entities = list(cleaned.entities)
        entities.extend(
            TextEntity(
                type=entity.type,
                offset=entity.offset + shift,
                length=entity.length,
                url=entity.url,
                user=entity.user,
                language=entity.language,
                custom_emoji_id=entity.custom_emoji_id,
            )
            for entity in footer.entities
        )
        return CleanedText(text, entities)

    def _line_ranges_to_remove(self, text: str, entities: list[TextEntity]) -> list[tuple[int, int]]:
        entity_spans = self._entity_py_spans(text, entities)
        ranges: list[tuple[int, int]] = []
        start = 0
        for line in text.splitlines(keepends=True):
            end = start + len(line)
            content = line.rstrip("\r\n")
            content_end = start + len(content)
            if self._should_remove_line(content, start, content_end, entity_spans):
                remove_start = start
                if end == len(text) and start > 0:
                    remove_start = start - 1
                    if start > 1 and text[start - 2 : start] == "\r\n":
                        remove_start -= 1
                ranges.append((remove_start, end))
            start = end
        return self._merge_ranges(ranges)

    def _blank_line_ranges_to_remove(
        self,
        text: str,
        already_removed: list[tuple[int, int]],
    ) -> list[tuple[int, int]]:
        lines: list[tuple[int, int, bool]] = []
        start = 0
        for line in text.splitlines(keepends=True):
            end = start + len(line)
            if any(start >= rm_start and end <= rm_end for rm_start, rm_end in already_removed):
                start = end
                continue
            lines.append((start, end, not line.strip()))
            start = end

        ranges: list[tuple[int, int]] = []
        seen_content = False
        previous_blank = False
        last_content_index = -1
        for index, (start, end, is_blank) in enumerate(lines):
            if not is_blank:
                seen_content = True
                previous_blank = False
                last_content_index = index
                continue
            if not seen_content or previous_blank:
                ranges.append((start, end))
            previous_blank = True

        for start, end, is_blank in lines[last_content_index + 1 :]:
            if is_blank:
                ranges.append((start, end))
        return ranges

    def _should_remove_line(
        self,
        line: str,
        line_start: int,
        line_end: int,
        entity_spans: list[tuple[int, int, TextEntity]],
    ) -> bool:
        stripped = line.strip()
        if not stripped:
            return False

        if self.config.remove_lines_with_urls and (URL_RE.search(line) or TG_RE.search(line)):
            return True
        if self.config.remove_markdown_links and MARKDOWN_LINK_RE.search(line):
            return True
        if self.config.remove_html_links and HTML_LINK_RE.search(line):
            return True

        for start, end, entity in entity_spans:
            if start < line_end and end > line_start and entity.type in {"url", "text_link"}:
                return True

        if self.config.remove_tg_channel_mentions and self._looks_like_channel_noise(line):
            return True

        for start, end, entity in entity_spans:
            if (
                start < line_end
                and end > line_start
                and entity.type == "mention"
                and self.config.remove_tg_channel_mentions
                and self._looks_like_channel_noise(line)
            ):
                return True
        return False

    def _looks_like_channel_noise(self, line: str) -> bool:
        mentions = MENTION_RE.findall(line)
        if not mentions:
            return False
        if line.strip() in mentions:
            return True
        if PROMO_WORDS_RE.search(line):
            return True
        words_without_mentions = MENTION_RE.sub("", line).strip()
        return len(words_without_mentions) <= 12

    def _entity_py_spans(self, text: str, entities: list[TextEntity]) -> list[tuple[int, int, TextEntity]]:
        spans: list[tuple[int, int, TextEntity]] = []
        for entity in entities:
            start = utf16_offset_to_py_index(text, entity.offset)
            end = utf16_offset_to_py_index(text, entity.offset + entity.length)
            if start is None or end is None or start >= end:
                continue
            spans.append((start, end, entity))
        return spans

    def _recalculate_entities(
        self,
        old_text: str,
        new_text: str,
        entities: list[TextEntity],
        removed_ranges: list[tuple[int, int]],
    ) -> list[TextEntity]:
        if not self.config.preserve_formatting:
            return []

        if not removed_ranges:
            return self._drop_invalid_entities(new_text, entities)

        kept_before: list[int] = [0] * (len(old_text) + 1)
        kept_count = 0
        for index in range(len(old_text)):
            kept_before[index] = kept_count
            if not self._is_removed(index, removed_ranges):
                kept_count += 1
        kept_before[len(old_text)] = kept_count

        recalculated: list[TextEntity] = []
        for entity in entities:
            old_start = utf16_offset_to_py_index(old_text, entity.offset)
            old_end = utf16_offset_to_py_index(old_text, entity.offset + entity.length)
            if old_start is None or old_end is None or old_start >= old_end:
                continue
            if any(self._is_removed(index, removed_ranges) for index in range(old_start, old_end)):
                continue

            new_start = kept_before[old_start]
            new_end = kept_before[old_end]
            if new_start >= new_end or new_end > len(new_text):
                continue
            recalculated.append(
                TextEntity(
                    type=entity.type,
                    offset=py_index_to_utf16_offset(new_text, new_start),
                    length=utf16_len(new_text[new_start:new_end]),
                    url=entity.url,
                    user=entity.user,
                    language=entity.language,
                    custom_emoji_id=entity.custom_emoji_id,
                )
            )
        return self._drop_invalid_entities(new_text, recalculated)

    def _drop_invalid_entities(self, text: str, entities: list[TextEntity]) -> list[TextEntity]:
        valid: list[TextEntity] = []
        total_units = utf16_len(text)
        for entity in entities:
            if entity.offset < 0 or entity.length <= 0:
                continue
            if entity.offset + entity.length > total_units:
                continue
            valid.append(entity)
        return valid

    def _is_removed(self, index: int, ranges: list[tuple[int, int]]) -> bool:
        return any(start <= index < end for start, end in ranges)

    def _merge_ranges(self, ranges: list[tuple[int, int]]) -> list[tuple[int, int]]:
        if not ranges:
            return []
        ranges = sorted(ranges)
        merged = [ranges[0]]
        for start, end in ranges[1:]:
            last_start, last_end = merged[-1]
            if start <= last_end:
                merged[-1] = (last_start, max(last_end, end))
            else:
                merged.append((start, end))
        return merged

    def _footer_to_text_and_entities(self, footer_markdown: str) -> CleanedText:
        match = MARKDOWN_LINK_RE.search(footer_markdown)
        if not match:
            return CleanedText(footer_markdown)

        link_text_match = re.match(r"\[([^\]\n]+)\]\(([^)]+)\)", match.group(0))
        if not link_text_match:
            return CleanedText(footer_markdown)

        label, url = link_text_match.groups()
        visible = footer_markdown[: match.start()] + label + footer_markdown[match.end() :]
        start = match.start()
        entity = TextEntity(
            type="text_link",
            offset=py_index_to_utf16_offset(visible, start),
            length=utf16_len(label),
            url=url,
        )
        return CleanedText(visible, [entity])
