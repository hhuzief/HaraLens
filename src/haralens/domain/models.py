"""Initial identity and dataset metadata; no persistence or analytics behavior."""

from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import UUID, uuid4

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class Entity(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: UUID = Field(default_factory=uuid4)
    created_at: AwareDatetime = Field(default_factory=lambda: datetime.now(UTC))


class User(Entity):
    display_name: Name


class Organization(Entity):
    name: Name


class Workspace(Entity):
    organization_id: UUID
    name: Name


class Project(Entity):
    organization_id: UUID
    workspace_id: UUID
    name: Name
    retention_mode: Literal["temporary", "persistent"] = "temporary"


class Dataset(Entity):
    organization_id: UUID
    project_id: UUID
    name: Name


class DatasetVersion(Entity):
    organization_id: UUID
    dataset_id: UUID
    version: int = Field(ge=1)
    content_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    storage_key: Name


class AccessContext(BaseModel):
    """Trusted server-side identity, never constructed from unverified client IDs."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    user_id: UUID
    organization_id: UUID
