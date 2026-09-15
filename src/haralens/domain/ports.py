"""Replaceable infrastructure contracts. No concrete adapters exist in Phase 0."""

from typing import Protocol
from uuid import UUID

from haralens.domain.models import AccessContext, Project


class AuthenticationProvider(Protocol):
    def authenticate(self, token: str) -> AccessContext:
        """Verify token and membership or raise an authentication failure."""
        ...


class ProjectRepository(Protocol):
    def get(self, context: AccessContext, project_id: UUID) -> Project | None:
        """Return an authorized project; deny cross-organization access."""
        ...


class ObjectStorage(Protocol):
    def read(self, context: AccessContext, key: str) -> bytes:
        """Read only an authorized object; enforce ownership in the adapter."""
        ...

    def write(self, context: AccessContext, key: str, content: bytes) -> None:
        """Create an authorized object without overwriting dataset versions."""
        ...
