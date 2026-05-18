# AI Agent Notes

## Project Summary

This is a Python 3.12 aiogram 3 Telegram Bot API MVP that repacks posts from a source channel into a target channel. It downloads supported media, cleans link-related text lines, appends a configured footer, and publishes a new post instead of forwarding.

## Architecture Principles

- Keep business logic in services, not handlers.
- Keep Telegram-specific objects at the edges.
- Preserve async flow end to end.
- Prefer readable, predictable MVP behavior over broad abstractions.
- Do not add persistent storage unless the user explicitly asks for it.

## Files That Define Public Behavior

Update `README.md` and `config.yaml.example` when changing:

- YAML schema;
- supported content types;
- cleaner rules;
- footer behavior;
- media group behavior;
- dedupe/storage semantics.

## YAML Schema Rules

- Config lives in `app/models/config_models.py`.
- Validate early on startup through `app/config.py`.
- Keep new fields explicit and documented.
- Avoid environment-variable magic unless documented and tested.

## TextCleaner Rules

- `TextCleaner` removes whole lines only.
- Do not remove ordinary text or hashtags.
- Preserve Telegram entities where practical.
- If an entity intersects removed text, drop that entity instead of risking invalid offsets.
- Keep tests in `tests/test_text_cleaner.py` updated for every cleaner behavior change.

## Entity Offset Rules

- Telegram Bot API offsets are UTF-16 code units.
- Python string indexes are not UTF-16 offsets.
- Use helpers from `app/utils/entities.py`.
- Add tests when touching offset logic, especially around emoji and Cyrillic text.

## Storage Rules

- Runtime dedupe and media group buffers are in-memory only.
- Temp files are allowed only for downloaded media and must be removed after publication.
- Do not add Redis, SQL, files, or other persistent state without explicit scope change.

## Async Rules

- Do not block the event loop with long synchronous operations.
- Keep Telegram calls awaited.
- Aggregator finalization must not double-publish a `media_group_id`.

## Pre-Commit Checklist

- `pytest`
- `python -m compileall app tests`
- Config example still matches pydantic models.
- README still reflects actual behavior.
- No token, `config.yaml`, temp files, or local artifacts are committed.

## Overengineering Guardrail

This repository is an MVP. Avoid adding queues, dependency injection frameworks, storage layers, plugin systems, or generic parser frameworks unless the user asks for that complexity.
