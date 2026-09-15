import pytest
from pydantic import ValidationError

from haralens.common.config import Settings


def test_environment_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HARALENS_ENVIRONMENT", "test")
    monkeypatch.setenv("HARALENS_LOG_LEVEL", "WARNING")
    settings = Settings(_env_file=None)
    assert settings.environment == "test"
    assert settings.log_level == "WARNING"


def test_invalid_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HARALENS_LOG_LEVEL", "INVALID")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)
