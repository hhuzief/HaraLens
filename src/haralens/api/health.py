"""Process liveness, not database readiness."""

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from haralens import __version__

router = APIRouter(prefix="/api/v1", tags=["health"])


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    service: Literal["HaraLens"] = "HaraLens"
    version: str = __version__


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse()
