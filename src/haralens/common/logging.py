"""JSON application logs. Callers must use fixed events, never sensitive payloads."""

import json
import logging
from datetime import UTC, datetime
from typing import cast


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
        }
        event_data = getattr(record, "event_data", None)
        if isinstance(event_data, dict):
            payload.update(cast(dict[str, object], event_data))
        return json.dumps(payload)


def configure_logging(level: str) -> None:
    """Configure only our logger; repeated startup does not duplicate handlers."""
    logger = logging.getLogger("haralens")
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
        handler.close()
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
    logger.setLevel(level)
    logger.propagate = False
