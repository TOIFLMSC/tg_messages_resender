from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from app.models.config_models import AppConfig


class ConfigError(RuntimeError):
    """Raised when config loading or validation fails."""


def load_config(path: str | Path) -> AppConfig:
    config_path = Path(path)
    if not config_path.exists():
        raise ConfigError(f"Config file not found: {config_path}")

    try:
        raw: Any = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigError(f"Invalid YAML in {config_path}: {exc}") from exc

    if not isinstance(raw, dict):
        raise ConfigError("Config root must be a YAML mapping")

    try:
        return AppConfig.model_validate(raw)
    except ValidationError as exc:
        raise ConfigError(str(exc)) from exc
