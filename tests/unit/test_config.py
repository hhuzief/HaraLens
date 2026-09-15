import pytest
from pydantic import ValidationError

from haralens.common.config import Settings


def test_environment_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HARALENS_ENVIRONMENT", "test")
    monkeypatch.setenv("HARALENS_LOG_LEVEL", "WARNING")
    settings = Settings(_env_file=None)
    assert settings.environment == "test"
    assert settings.log_level == "WARNING"
    assert settings.ingestion_limits.max_source_bytes == 10 * 1024 * 1024
    assert settings.ingestion_limits.max_rows == 100_000
    assert settings.ingestion_limits.max_columns == 1_000


def test_invalid_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HARALENS_LOG_LEVEL", "INVALID")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


@pytest.mark.parametrize(
    "field",
    [
        "HARALENS_INGESTION_MAX_SOURCE_BYTES",
        "HARALENS_INGESTION_MAX_ROWS",
        "HARALENS_INGESTION_MAX_COLUMNS",
    ],
)
def test_invalid_ingestion_limit_configuration(monkeypatch: pytest.MonkeyPatch, field: str) -> None:
    monkeypatch.setenv(field, "0")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)
