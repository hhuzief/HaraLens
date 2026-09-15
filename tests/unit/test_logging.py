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
