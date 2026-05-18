from __future__ import annotations

import logging
import shutil
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

logger = logging.getLogger(__name__)


@asynccontextmanager
async def temporary_media_dir(base_dir: Path) -> AsyncIterator[Path]:
    base_dir.mkdir(parents=True, exist_ok=True)
    path = Path(tempfile.mkdtemp(prefix="tg-media-", dir=base_dir))
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)
        logger.info("temp files removed: %s", path)
