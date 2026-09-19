"""Explicit immutable registry for quality checks."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from dataclasses import dataclass

from haralens.quality.contracts import QualityCheck
from haralens.quality.errors import DuplicateCheckIdError, UnknownCheckIdError
from haralens.quality.models import CheckScope, QualityCheckDefinition, QualityDimension


@dataclass(frozen=True, slots=True)
class RegisteredQualityCheck:
    definition: QualityCheckDefinition
    check: QualityCheck


class QualityCheckRegistry:
    """A deterministic definition snapshot with no import-time registration."""

    def __init__(self, checks: Iterable[QualityCheck] = ()) -> None:
        entries: list[RegisteredQualityCheck] = []
        seen: set[str] = set()
        for check in checks:
            definition = QualityCheckDefinition.model_validate(check.definition.model_dump())
            if definition.check_id in seen:
                raise DuplicateCheckIdError(definition.check_id)
            seen.add(definition.check_id)
            entries.append(RegisteredQualityCheck(definition=definition, check=check))
        self._entries = tuple(sorted(entries, key=lambda item: item.definition.check_id))

    def __len__(self) -> int:
        return len(self._entries)

    @property
    def entries(self) -> tuple[RegisteredQualityCheck, ...]:
        return self._entries

    def definitions(
        self,
        *,
        dimension: QualityDimension | None = None,
        scope: CheckScope | None = None,
    ) -> tuple[QualityCheckDefinition, ...]:
        return tuple(
            entry.definition
            for entry in self._entries
            if (dimension is None or entry.definition.dimension is dimension)
            and (scope is None or entry.definition.scope is scope)
        )

    def get(self, check_id: str) -> RegisteredQualityCheck:
        for entry in self._entries:
            if entry.definition.check_id == check_id:
                return entry
        raise UnknownCheckIdError(check_id)

    @property
    def fingerprint(self) -> str:
        payload = [item.model_dump(mode="json") for item in self.definitions()]
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()
