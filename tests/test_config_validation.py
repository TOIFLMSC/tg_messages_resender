from pathlib import Path

import pytest

from app.config import ConfigError, load_config


def test_loads_valid_config(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
bot:
  token: "123:abc"
  log_level: "INFO"
  temp_dir: "./tmp"
  media_group_collect_timeout_seconds: 1.5
routes:
  - source_channel_id: -1001
    target_channel_id: -1002
    footer_text: "footer"
    cleaner:
      remove_lines_with_urls: true
      remove_markdown_links: true
      remove_html_links: true
      remove_tg_channel_mentions: true
      preserve_hashtags: true
      preserve_formatting: true
      trim_extra_blank_lines: true
publishing:
  split_media_groups_over_10: true
  max_media_per_album: 10
  caption_overflow_strategy: "send_followup_message"
  disable_notification: false
""",
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.bot.token == "123:abc"
    assert config.routes[0].source_channel_id == -1001


def test_rejects_placeholder_token(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
bot:
  token: "PUT_BOT_TOKEN_HERE"
routes:
  - source_channel_id: -1001
    target_channel_id: -1002
    footer_text: "footer"
""",
        encoding="utf-8",
    )

    with pytest.raises(ConfigError):
        load_config(config_path)


def test_rejects_same_source_and_target(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
bot:
  token: "123:abc"
routes:
  - source_channel_id: -1001
    target_channel_id: -1001
    footer_text: "footer"
""",
        encoding="utf-8",
    )

    with pytest.raises(ConfigError):
        load_config(config_path)
