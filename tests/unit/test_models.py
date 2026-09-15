from datetime import datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from haralens.domain.models import DatasetVersion, Project


def test_project_round_trip() -> None:
    project = Project(organization_id=uuid4(), workspace_id=uuid4(), name=" Example ")
    assert project.name == "Example"
    assert project.created_at.tzinfo is not None
    assert Project.model_validate_json(project.model_dump_json()) == project
    with pytest.raises(ValidationError):
        project.name = "Changed"


@pytest.mark.parametrize("name", ["", "   ", "a" * 201])
def test_invalid_project_name(name: str) -> None:
    with pytest.raises(ValidationError):
        Project(organization_id=uuid4(), workspace_id=uuid4(), name=name)


def test_reject_naive_timestamp() -> None:
    with pytest.raises(ValidationError):
        Project(
            organization_id=uuid4(),
            workspace_id=uuid4(),
            name="Example",
            created_at=datetime(2026, 1, 1),
        )


@pytest.mark.parametrize("version,digest", [(0, "a" * 64), (1, "invalid")])
def test_invalid_dataset_version(version: int, digest: str) -> None:
    with pytest.raises(ValidationError):
        DatasetVersion(
            organization_id=uuid4(),
            dataset_id=uuid4(),
            version=version,
            content_sha256=digest,
            storage_key="object-key",
        )
