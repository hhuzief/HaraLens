import json
import logging

import pytest

from haralens.common.logging import configure_logging


def test_json_logging_is_idempotent(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging("INFO")
    configure_logging("INFO")
    logging.getLogger("haralens.test").info("test_event")
    lines = capsys.readouterr().err.splitlines()
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["event"] == "test_event"
    assert payload["level"] == "INFO"
    assert payload["timestamp"].endswith("+00:00")


def test_json_logging_includes_structured_event_data(
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_logging("INFO")
    logging.getLogger("haralens.test").info(
        "test_event", extra={"event_data": {"source_type": "csv", "source_bytes": 12}}
    )
    payload = json.loads(capsys.readouterr().err)
    assert payload["source_type"] == "csv"
    assert payload["source_bytes"] == 12
