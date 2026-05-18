from app.models.config_models import CleanerConfig
from app.models.domain import TextEntity
from app.services.text_cleaner import TextCleaner
from app.utils.entities import py_index_to_utf16_offset, utf16_len


def test_removes_only_link_lines_and_preserves_hashtags() -> None:
    cleaner = TextCleaner(CleanerConfig())
    text = "Обычный текст\nhttps://example.com/post\n#tag stays\nПодписаться @some_channel"

    result = cleaner.clean(text, [])

    assert result.text == "Обычный текст\n#tag stays"


def test_removes_markdown_and_html_link_lines() -> None:
    cleaner = TextCleaner(CleanerConfig())
    text = "keep me\n[link](https://example.com)\n<a href=\"https://example.com\">x</a>\nfinal"

    result = cleaner.clean(text, [])

    assert result.text == "keep me\nfinal"


def test_recalculates_entities_after_removed_line_with_emoji() -> None:
    cleaner = TextCleaner(CleanerConfig())
    text = "🔥 Заголовок\nhttps://t.me/source\nВажный текст"
    start = text.index("Важный")
    entity = TextEntity(
        type="bold",
        offset=py_index_to_utf16_offset(text, start),
        length=utf16_len("Важный"),
    )

    result = cleaner.clean(text, [entity])

    assert result.text == "🔥 Заголовок\nВажный текст"
    assert len(result.entities) == 1
    new_start = result.text.index("Важный")
    assert result.entities[0].offset == py_index_to_utf16_offset(result.text, new_start)


def test_footer_added_after_blank_line_when_text_exists() -> None:
    cleaner = TextCleaner(CleanerConfig())
    cleaned = cleaner.clean("Текст", [])

    result = cleaner.with_footer(cleaned, "🖤 [Channel](https://t.me/channellink) 🖤")

    assert result.text == "Текст\n\n🖤 Channel 🖤"
    assert result.entities[0].type == "text_link"
    assert result.entities[0].url == "https://t.me/channellink"
    assert result.entities[0].offset == py_index_to_utf16_offset(result.text, result.text.index("Channel"))
    assert result.entities[0].length == utf16_len("Channel")


def test_footer_without_blank_line_when_text_empty() -> None:
    cleaner = TextCleaner(CleanerConfig())

    result = cleaner.with_footer(
        cleaner.clean("https://example.com", []),
        "🖤 [Channel](https://t.me/channellink) 🖤",
    )

    assert result.text == "🖤 Channel 🖤"
    assert result.entities[0].type == "text_link"
    assert result.entities[0].url == "https://t.me/channellink"
    assert result.entities[0].offset == py_index_to_utf16_offset(result.text, result.text.index("Channel"))
    assert result.entities[0].length == utf16_len("Channel")
