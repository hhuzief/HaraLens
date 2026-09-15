"""Deterministic, explainable column semantic inference."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any
from uuid import UUID

import pandas as pd

from haralens.semantic.config import SemanticInferenceConfig
from haralens.semantic.models import (
    AlternativeSemanticCandidate,
    ColumnSemanticInference,
    EvidenceCode,
    InferenceConfidence,
    InferenceEvidence,
    InferenceWarning,
    InferenceWarningCode,
    SemanticType,
)

_UUID_PATTERN = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
_ISO_DATE_PATTERN = re.compile(
    r"^\d{4}-\d{1,2}-\d{1,2}(?:[T ]\d{1,2}:\d{2}"
    r"(?::\d{2}(?:\.\d{1,6})?)?(?:Z|[+-]\d{2}:?\d{2})?)?$"
)
_SLASH_DATE_PATTERN = re.compile(r"^(?:\d{1,2}/\d{1,2}/\d{4}|\d{4}/\d{1,2}/\d{1,2})$")
_STRUCTURED_CODE_PATTERN = re.compile(r"^(?=.*[A-Za-z])(?=.*\d)[A-Za-z0-9]+(?:[-_][A-Za-z0-9]+)*$")
_PUNCTUATION_PATTERN = re.compile(r"[^\w\s]", re.UNICODE)

_STRONG_IDENTIFIER_TOKENS = frozenset({"id", "uuid"})
_CONTEXTUAL_IDENTIFIER_TOKENS = frozenset({"account", "code", "key", "no", "number", "reference"})
_IDENTIFIER_TOKENS = _STRONG_IDENTIFIER_TOKENS | _CONTEXTUAL_IDENTIFIER_TOKENS
_IDENTIFIER_ENTITY_TOKENS = frozenset(
    {
        "account",
        "asset",
        "customer",
        "device",
        "employee",
        "invoice",
        "loan",
        "member",
        "order",
        "phone",
        "product",
        "record",
        "reference",
        "transaction",
        "user",
        "vendor",
    }
)
_MEASUREMENT_TOKENS = frozenset(
    {
        "age",
        "amount",
        "balance",
        "cost",
        "children",
        "count",
        "income",
        "measure",
        "measurement",
        "percent",
        "percentage",
        "price",
        "quantity",
        "rate",
        "revenue",
        "salary",
        "score",
        "total",
        "value",
    }
)
_CATEGORICAL_TOKENS = frozenset(
    {
        "area",
        "category",
        "class",
        "grade",
        "group",
        "label",
        "level",
        "postal",
        "region",
        "segment",
        "status",
        "type",
        "zip",
    }
)
_CONTINUOUS_MEASUREMENT_TOKENS = frozenset(
    {
        "amount",
        "balance",
        "cost",
        "income",
        "measure",
        "measurement",
        "percent",
        "percentage",
        "price",
        "rate",
        "revenue",
        "salary",
        "score",
        "total",
        "value",
    }
)
_BOOLEAN_TOKENS = frozenset({"active", "can", "enabled", "flag", "has", "is", "should", "valid"})
_DATETIME_TOKENS = frozenset({"date", "datetime", "day", "month", "time", "timestamp", "year"})
_FREE_TEXT_TOKENS = frozenset(
    {"comment", "comments", "description", "message", "note", "notes", "review", "text"}
)

_MESSAGES: dict[EvidenceCode, str] = {
    EvidenceCode.ALL_NULL: "Every row is null.",
    EvidenceCode.CONSTANT_VALUE: "All non-null observations contain one distinct value.",
    EvidenceCode.NATIVE_BOOLEAN_DTYPE: "The physical dtype is boolean.",
    EvidenceCode.BOOLEAN_VALUE_SET: "Normalized values match a supported boolean pair.",
    EvidenceCode.BOOLEAN_NAME_HINT: "The column name contains a token associated with flags.",
    EvidenceCode.BINARY_NUMERIC_SET: "The non-null numeric value set is exactly 0 and 1.",
    EvidenceCode.BINARY_TEXT_SET: "The normalized text value set is exactly 0 and 1.",
    EvidenceCode.NATIVE_DATETIME_DTYPE: "The physical dtype is datetime-like.",
    EvidenceCode.PYTHON_DATE_VALUES: "Inspected values are Python date or datetime objects.",
    EvidenceCode.DATE_LIKE_PATTERN: "Inspected strings use supported date-like syntax.",
    EvidenceCode.DATE_PARSE_RATE: "The deterministic date parse rate met the configured threshold.",
    EvidenceCode.AMBIGUOUS_DATE_FORMAT: "Slash dates permit more than one calendar ordering.",
    EvidenceCode.UUID_PATTERN: "All inspected strings are canonical UUID values.",
    EvidenceCode.NAME_HINT_IDENTIFIER: "The column name contains an identifier token.",
    EvidenceCode.HIGH_UNIQUENESS: "The non-null uniqueness ratio met the identifier threshold.",
    EvidenceCode.IDENTIFIER_CANDIDATE_UNIQUENESS: (
        "Uniqueness met the candidate threshold but not the strong identifier threshold."
    ),
    EvidenceCode.MONOTONIC_INTEGER_SEQUENCE: (
        "Inspected integer-like values increase monotonically."
    ),
    EvidenceCode.STRUCTURED_CODE_PATTERN: "Inspected strings share an alphanumeric code structure.",
    EvidenceCode.NATIVE_NUMERIC_DTYPE: "The physical dtype is numeric.",
    EvidenceCode.NUMERIC_INTEGER_ONLY: "All inspected numeric values are integer-like.",
    EvidenceCode.NUMERIC_FRACTIONAL_VALUES: "Inspected numeric values include fractions.",
    EvidenceCode.NATIVE_CATEGORICAL_DTYPE: "The physical dtype is pandas categorical.",
    EvidenceCode.NAME_HINT_CATEGORICAL: (
        "The column name contains a token associated with categorical values."
    ),
    EvidenceCode.LOW_CARDINALITY: "Repeated values meet the configured categorical boundary.",
    EvidenceCode.HIGH_CARDINALITY: "The column has high cardinality among non-null observations.",
    EvidenceCode.LONG_TEXT: "Average inspected text length met the free-text threshold.",
    EvidenceCode.NAME_HINT_FREE_TEXT: "The column name contains a descriptive-text token.",
    EvidenceCode.HIGH_TEXT_UNIQUENESS: "Text uniqueness met the free-text threshold.",
    EvidenceCode.TEXT_WHITESPACE: "The configured proportion of text contains whitespace.",
    EvidenceCode.NULL_VALUES_PRESENT: "The column contains null values.",
    EvidenceCode.DETERMINISTIC_SAMPLE: "Content rules used an evenly spaced deterministic sample.",
    EvidenceCode.MIXED_VALUE_TYPES: "Inspected values contain incompatible Python value types.",
    EvidenceCode.UNSUPPORTED_PHYSICAL_DTYPE: (
        "The physical dtype has no supported analytical interpretation."
    ),
    EvidenceCode.INFERENCE_ERROR: "The column could not be compared safely for inference.",
}


@dataclass(frozen=True, slots=True)
class _ColumnStats:
    total_count: int
    null_count: int
    non_null_count: int
    unique_count: int | None
    unique_ratio: float | None
    values: list[Any]
    sampled: bool


@dataclass(frozen=True, slots=True)
class _DateAnalysis:
    parse_rate: float
    date_like_count: int
    ambiguous: bool


class SemanticInferenceEngine:
    """Infer one column using explicit, ordered heuristics and no data mutation."""

    def __init__(self, config: SemanticInferenceConfig | None = None) -> None:
        self.config = config or SemanticInferenceConfig()

    def infer_column(
        self, column_name: str, column_position: int, series: pd.Series[Any]
    ) -> ColumnSemanticInference:
        physical_dtype = str(series.dtype)
        stats = self._statistics(series)
        common_evidence = self._common_evidence(stats)

        if stats.non_null_count == 0:
            return self._result(
                column_name,
                column_position,
                physical_dtype,
                SemanticType.EMPTY,
                InferenceConfidence.HIGH,
                stats,
                [self._evidence(EvidenceCode.ALL_NULL), *common_evidence],
            )

        if stats.unique_count is None:
            return self._result(
                column_name,
                column_position,
                physical_dtype,
                SemanticType.UNKNOWN,
                InferenceConfidence.LOW,
                stats,
                [self._evidence(EvidenceCode.INFERENCE_ERROR), *common_evidence],
                warnings=(
                    self._warning(
                        InferenceWarningCode.UNSUPPORTED_VALUES,
                        "Values are not safely hashable or comparable; inference was isolated.",
                        column_position,
                    ),
                ),
            )

        if stats.unique_count == 1:
            return self._result(
                column_name,
                column_position,
                physical_dtype,
                SemanticType.CONSTANT,
                InferenceConfidence.HIGH,
                stats,
                [self._evidence(EvidenceCode.CONSTANT_VALUE), *common_evidence],
            )

        tokens = _name_tokens(column_name)
        dtype = series.dtype
        values = stats.values

        if pd.api.types.is_bool_dtype(dtype) or all(isinstance(value, bool) for value in values):
            return self._result(
                column_name,
                column_position,
                physical_dtype,
                SemanticType.BOOLEAN,
                self._confidence(InferenceConfidence.HIGH, stats.non_null_count),
                stats,
                [self._evidence(EvidenceCode.NATIVE_BOOLEAN_DTYPE), *common_evidence],
            )

        text_values = _text_values(values)
        if text_values is not None:
            normalized = {value.strip().casefold() for value in text_values}
            exact_binary_set = stats.unique_count == 2
            if exact_binary_set and normalized in ({"true", "false"}, {"yes", "no"}, {"y", "n"}):
                evidence = [self._evidence(EvidenceCode.BOOLEAN_VALUE_SET)]
                if tokens & _BOOLEAN_TOKENS:
                    evidence.append(self._evidence(EvidenceCode.BOOLEAN_NAME_HINT))
                confidence = (
                    InferenceConfidence.HIGH
                    if normalized == {"true", "false"} and not stats.sampled
                    else InferenceConfidence.MEDIUM
                )
                return self._result(
                    column_name,
                    column_position,
                    physical_dtype,
                    SemanticType.BOOLEAN,
                    self._confidence(confidence, stats.non_null_count),
                    stats,
                    [*evidence, *common_evidence],
                )
            if exact_binary_set and normalized == {"0", "1"}:
                if tokens & _BOOLEAN_TOKENS:
                    return self._result(
                        column_name,
                        column_position,
                        physical_dtype,
                        SemanticType.BOOLEAN,
                        self._confidence(InferenceConfidence.HIGH, stats.non_null_count),
                        stats,
                        [
                            self._evidence(EvidenceCode.BINARY_TEXT_SET),
                            self._evidence(EvidenceCode.BOOLEAN_NAME_HINT),
                            *common_evidence,
                        ],
                        alternatives=(
                            AlternativeSemanticCandidate(
                                semantic_type=SemanticType.CATEGORICAL,
                                confidence=InferenceConfidence.LOW,
                                evidence_codes=(EvidenceCode.LOW_CARDINALITY,),
                            ),
                        ),
                    )
                return self._result(
                    column_name,
                    column_position,
                    physical_dtype,
                    SemanticType.CATEGORICAL,
                    self._confidence(InferenceConfidence.MEDIUM, stats.non_null_count),
                    stats,
                    [
                        self._evidence(EvidenceCode.BINARY_TEXT_SET),
                        self._evidence(
                            EvidenceCode.LOW_CARDINALITY,
                            observed=stats.unique_count,
                            threshold=self.config.categorical_max_unique_count,
                        ),
                        *common_evidence,
                    ],
                    warnings=(
                        self._warning(
                            InferenceWarningCode.BINARY_TEXT_AMBIGUITY,
                            "Text values 0 and 1 may encode a flag or category; no boolean "
                            "name evidence was present.",
                            column_position,
                        ),
                    ),
                    alternatives=(
                        AlternativeSemanticCandidate(
                            semantic_type=SemanticType.BOOLEAN,
                            confidence=InferenceConfidence.LOW,
                            evidence_codes=(EvidenceCode.BINARY_TEXT_SET,),
                        ),
                    ),
                )

        if pd.api.types.is_datetime64_any_dtype(dtype):
            return self._result(
                column_name,
                column_position,
                physical_dtype,
                SemanticType.DATETIME,
                self._confidence(InferenceConfidence.HIGH, stats.non_null_count),
                stats,
                [self._evidence(EvidenceCode.NATIVE_DATETIME_DTYPE), *common_evidence],
            )

        if values and all(isinstance(value, date) for value in values):
            return self._result(
                column_name,
                column_position,
                physical_dtype,
                SemanticType.DATETIME,
                self._confidence(
                    InferenceConfidence.MEDIUM if stats.sampled else InferenceConfidence.HIGH,
                    stats.non_null_count,
                ),
                stats,
                [self._evidence(EvidenceCode.PYTHON_DATE_VALUES), *common_evidence],
            )

        uuid_values = text_values is not None and _all_canonical_uuids(text_values)
        if uuid_values:
            uuid_evidence = [self._evidence(EvidenceCode.UUID_PATTERN)]
            uuid_warnings: tuple[InferenceWarning, ...] = ()
            uuid_alternatives: tuple[AlternativeSemanticCandidate, ...] = ()
            confidence = self._confidence(
                InferenceConfidence.MEDIUM if stats.sampled else InferenceConfidence.HIGH,
                stats.non_null_count,
            )
            if (
                stats.unique_ratio is not None
                and stats.unique_ratio >= self.config.identifier_min_unique_ratio
            ):
                uuid_evidence.append(
                    self._evidence(
                        EvidenceCode.HIGH_UNIQUENESS,
                        observed=stats.unique_ratio,
                        threshold=self.config.identifier_min_unique_ratio,
                    )
                )
            else:
                confidence = InferenceConfidence.MEDIUM
                uuid_warnings = (
                    self._warning(
                        InferenceWarningCode.DUPLICATE_IDENTIFIER_VALUES,
                        "UUID structure indicates identifiers, but non-null values repeat.",
                        column_position,
                    ),
                )
                uuid_alternatives = (
                    AlternativeSemanticCandidate(
                        semantic_type=SemanticType.CATEGORICAL,
                        confidence=InferenceConfidence.LOW,
                        evidence_codes=(EvidenceCode.LOW_CARDINALITY,),
                    ),
                )
            return self._result(
                column_name,
                column_position,
                physical_dtype,
                SemanticType.IDENTIFIER,
                confidence,
                stats,
                [*uuid_evidence, *common_evidence],
                warnings=uuid_warnings,
                alternatives=uuid_alternatives,
            )

        date_analysis = _analyze_dates(text_values) if text_values is not None else None
        has_identifier_hint = bool(tokens & _IDENTIFIER_TOKENS)
        if (
            date_analysis is not None
            and date_analysis.date_like_count > 0
            and date_analysis.parse_rate >= self.config.datetime_min_parse_ratio
            and (not has_identifier_hint or bool(tokens & _DATETIME_TOKENS))
        ):
            evidence = [
                self._evidence(EvidenceCode.DATE_LIKE_PATTERN),
                self._evidence(
                    EvidenceCode.DATE_PARSE_RATE,
                    observed=date_analysis.parse_rate,
                    threshold=self.config.datetime_min_parse_ratio,
                ),
            ]
            date_warnings: list[InferenceWarning] = []
            confidence = self._confidence(
                InferenceConfidence.MEDIUM if stats.sampled else InferenceConfidence.HIGH,
                stats.non_null_count,
            )
            if date_analysis.ambiguous:
                evidence.append(self._evidence(EvidenceCode.AMBIGUOUS_DATE_FORMAT))
                date_warnings.append(
                    self._warning(
                        InferenceWarningCode.AMBIGUOUS_DATE_ORDER,
                        "Date-like values are valid under multiple locale orderings; "
                        "no ordering was chosen.",
                        column_position,
                    )
                )
                confidence = InferenceConfidence.LOW
            elif date_analysis.parse_rate < 1.0:
                date_warnings.append(
                    self._warning(
                        InferenceWarningCode.PARTIAL_DATE_PARSE,
                        "Some inspected non-null values did not parse as dates.",
                        column_position,
                    )
                )
                confidence = InferenceConfidence.MEDIUM
            return self._result(
                column_name,
                column_position,
                physical_dtype,
                SemanticType.DATETIME,
                confidence,
                stats,
                [*evidence, *common_evidence],
                warnings=tuple(date_warnings),
                alternatives=(
                    AlternativeSemanticCandidate(
                        semantic_type=SemanticType.CATEGORICAL,
                        confidence=InferenceConfidence.LOW,
                        evidence_codes=(EvidenceCode.AMBIGUOUS_DATE_FORMAT,),
                    ),
                )
                if date_analysis.ambiguous
                else (),
            )

        numeric = pd.api.types.is_numeric_dtype(dtype) and not pd.api.types.is_bool_dtype(dtype)
        if numeric and pd.api.types.is_complex_dtype(dtype):
            return self._result(
                column_name,
                column_position,
                physical_dtype,
                SemanticType.UNKNOWN,
                InferenceConfidence.LOW,
                stats,
                [self._evidence(EvidenceCode.UNSUPPORTED_PHYSICAL_DTYPE), *common_evidence],
                warnings=(
                    self._warning(
                        InferenceWarningCode.UNSUPPORTED_VALUES,
                        "Complex numeric values have no supported Phase 1C semantic type.",
                        column_position,
                    ),
                ),
            )
        integer_only = numeric and _integer_only(values)
        numeric_binary = (
            integer_only and stats.unique_count == 2 and {int(value) for value in values} == {0, 1}
        )
        if numeric_binary and tokens & _BOOLEAN_TOKENS:
            return self._result(
                column_name,
                column_position,
                physical_dtype,
                SemanticType.BOOLEAN,
                self._confidence(InferenceConfidence.HIGH, stats.non_null_count),
                stats,
                [
                    self._evidence(EvidenceCode.BINARY_NUMERIC_SET),
                    self._evidence(EvidenceCode.BOOLEAN_NAME_HINT),
                    *common_evidence,
                ],
                alternatives=(
                    AlternativeSemanticCandidate(
                        semantic_type=SemanticType.NUMERIC_DISCRETE,
                        confidence=InferenceConfidence.LOW,
                        evidence_codes=(EvidenceCode.NUMERIC_INTEGER_ONLY,),
                    ),
                ),
            )

        identifier_analysis = self._identifier_evidence(
            tokens, stats, values, text_values, integer_only
        )
        if identifier_analysis is not None:
            identifier_evidence, repeated_identifier = identifier_analysis
            alternative_type = (
                self._numeric_type(stats, integer_only, tokens)
                if numeric
                else SemanticType.CATEGORICAL
            )
            structured = any(
                item.code
                in {EvidenceCode.STRUCTURED_CODE_PATTERN, EvidenceCode.MONOTONIC_INTEGER_SEQUENCE}
                for item in identifier_evidence
            )
            base_confidence = (
                InferenceConfidence.HIGH
                if structured and not repeated_identifier and not stats.sampled
                else InferenceConfidence.MEDIUM
            )
            if repeated_identifier and not structured:
                base_confidence = InferenceConfidence.LOW
            confidence = self._confidence(base_confidence, stats.non_null_count)
            identifier_warnings = [
                self._warning(
                    InferenceWarningCode.MULTIPLE_PLAUSIBLE_TYPES,
                    "Identifier evidence wins, but the physical values also support another "
                    "analytical type.",
                    column_position,
                )
            ]
            if repeated_identifier:
                identifier_warnings.append(
                    self._warning(
                        InferenceWarningCode.DUPLICATE_IDENTIFIER_VALUES,
                        "Identifier evidence is present, but some non-null values repeat.",
                        column_position,
                    )
                )
            return self._result(
                column_name,
                column_position,
                physical_dtype,
                SemanticType.IDENTIFIER,
                confidence,
                stats,
                [*identifier_evidence, *common_evidence],
                warnings=tuple(identifier_warnings),
                alternatives=(
                    AlternativeSemanticCandidate(
                        semantic_type=alternative_type,
                        confidence=InferenceConfidence.MEDIUM,
                        evidence_codes=(
                            EvidenceCode.NATIVE_NUMERIC_DTYPE
                            if numeric
                            else EvidenceCode.HIGH_CARDINALITY,
                        ),
                    ),
                ),
            )

        if numeric:
            semantic_type = self._numeric_type(stats, integer_only, tokens)
            evidence = [self._evidence(EvidenceCode.NATIVE_NUMERIC_DTYPE)]
            evidence.append(
                self._evidence(
                    EvidenceCode.NUMERIC_INTEGER_ONLY
                    if integer_only
                    else EvidenceCode.NUMERIC_FRACTIONAL_VALUES
                )
            )
            if semantic_type is SemanticType.NUMERIC_DISCRETE:
                if (
                    stats.unique_count is not None
                    and stats.unique_count <= self.config.numeric_discrete_max_unique_count
                ):
                    evidence.append(
                        self._evidence(
                            EvidenceCode.LOW_CARDINALITY,
                            observed=stats.unique_count,
                            threshold=self.config.numeric_discrete_max_unique_count,
                        )
                    )
                else:
                    evidence.extend(
                        [
                            self._evidence(
                                EvidenceCode.LOW_CARDINALITY,
                                observed=stats.unique_ratio,
                                threshold=self.config.numeric_discrete_max_unique_ratio,
                            ),
                            self._evidence(EvidenceCode.NAME_HINT_CATEGORICAL),
                        ]
                    )
            numeric_warnings: tuple[InferenceWarning, ...] = ()
            alternatives: tuple[AlternativeSemanticCandidate, ...] = ()
            confidence = self._confidence(
                InferenceConfidence.MEDIUM
                if integer_only or stats.sampled
                else InferenceConfidence.HIGH,
                stats.non_null_count,
            )
            if numeric_binary:
                numeric_warnings = (
                    self._warning(
                        InferenceWarningCode.BINARY_NUMERIC_AMBIGUITY,
                        "Values 0 and 1 may represent a flag; no boolean name evidence was "
                        "present.",
                        column_position,
                    ),
                )
                alternatives = (
                    AlternativeSemanticCandidate(
                        semantic_type=SemanticType.BOOLEAN,
                        confidence=InferenceConfidence.LOW,
                        evidence_codes=(EvidenceCode.BINARY_NUMERIC_SET,),
                    ),
                )
                evidence.append(self._evidence(EvidenceCode.BINARY_NUMERIC_SET))
                confidence = InferenceConfidence.MEDIUM
            return self._result(
                column_name,
                column_position,
                physical_dtype,
                semantic_type,
                confidence,
                stats,
                [*evidence, *common_evidence],
                warnings=numeric_warnings,
                alternatives=alternatives,
            )

        if isinstance(dtype, pd.CategoricalDtype):
            return self._result(
                column_name,
                column_position,
                physical_dtype,
                SemanticType.CATEGORICAL,
                self._confidence(InferenceConfidence.HIGH, stats.non_null_count),
                stats,
                [self._evidence(EvidenceCode.NATIVE_CATEGORICAL_DTYPE), *common_evidence],
            )

        if text_values is not None:
            return self._infer_text(
                column_name,
                column_position,
                physical_dtype,
                tokens,
                stats,
                text_values,
                common_evidence,
            )

        return self._result(
            column_name,
            column_position,
            physical_dtype,
            SemanticType.UNKNOWN,
            InferenceConfidence.LOW,
            stats,
            [self._evidence(EvidenceCode.MIXED_VALUE_TYPES), *common_evidence],
            warnings=(
                self._warning(
                    InferenceWarningCode.UNSUPPORTED_VALUES,
                    "The non-null values do not share a supported scalar representation.",
                    column_position,
                ),
            ),
        )

    def failure_result(
        self, column_name: str, column_position: int, series: pd.Series[Any]
    ) -> ColumnSemanticInference:
        """Build a safe unknown result when a pathological column raises unexpectedly."""

        total = len(series)
        stats = _ColumnStats(total, 0, total, None, None, [], False)
        return self._result(
            column_name,
            column_position,
            str(series.dtype),
            SemanticType.UNKNOWN,
            InferenceConfidence.LOW,
            stats,
            [self._evidence(EvidenceCode.INFERENCE_ERROR)],
            warnings=(
                self._warning(
                    InferenceWarningCode.COLUMN_INFERENCE_FAILED,
                    "Column inference failed safely; no raw value or exception detail was "
                    "retained.",
                    column_position,
                ),
            ),
        )

    def _statistics(self, series: pd.Series[Any]) -> _ColumnStats:
        total = len(series)
        try:
            null_mask = series.isna()
            non_null = series.loc[~null_mask]
        except (TypeError, ValueError):
            return _ColumnStats(total, 0, total, None, None, [], False)
        non_null_count = len(non_null)
        null_count = total - non_null_count
        try:
            unique_count: int | None = int(non_null.nunique(dropna=True))
        except (TypeError, ValueError):
            unique_count = None
        unique_ratio = (
            unique_count / non_null_count if unique_count is not None and non_null_count else None
        )
        sampled = non_null_count > self.config.max_inspection_values
        if sampled:
            size = self.config.max_inspection_values
            positions = [index * (non_null_count - 1) // (size - 1) for index in range(size)]
            values = non_null.take(positions).tolist()
        else:
            values = non_null.tolist()
        return _ColumnStats(
            total,
            null_count,
            non_null_count,
            unique_count,
            unique_ratio,
            values,
            sampled,
        )

    def _identifier_evidence(
        self,
        tokens: frozenset[str],
        stats: _ColumnStats,
        values: list[Any],
        text_values: list[str] | None,
        integer_only: bool,
    ) -> tuple[list[InferenceEvidence], bool] | None:
        strong_hint = bool(tokens & _STRONG_IDENTIFIER_TOKENS)
        contextual_hint = bool(tokens & _CONTEXTUAL_IDENTIFIER_TOKENS)
        if (
            not (strong_hint or contextual_hint)
            or stats.non_null_count < self.config.identifier_min_non_null
            or stats.unique_ratio is None
            or stats.unique_ratio < self.config.identifier_candidate_min_unique_ratio
        ):
            return None
        monotonic = integer_only and _strictly_increasing(values)
        structured_code = text_values is not None and all(
            _STRUCTURED_CODE_PATTERN.fullmatch(value.strip()) for value in text_values
        )
        supporting_structure = monotonic or structured_code
        if not strong_hint:
            if tokens & (_MEASUREMENT_TOKENS | _CATEGORICAL_TOKENS):
                return None
            entity_tokens = tokens & _IDENTIFIER_ENTITY_TOKENS
            if not entity_tokens:
                return None
            if entity_tokens == {"reference"} and not supporting_structure:
                return None

        repeated_identifier = stats.unique_ratio < self.config.identifier_min_unique_ratio
        evidence = [self._evidence(EvidenceCode.NAME_HINT_IDENTIFIER)]
        if repeated_identifier:
            evidence.append(
                self._evidence(
                    EvidenceCode.IDENTIFIER_CANDIDATE_UNIQUENESS,
                    observed=stats.unique_ratio,
                    threshold=self.config.identifier_candidate_min_unique_ratio,
                )
            )
        else:
            evidence.append(
                self._evidence(
                    EvidenceCode.HIGH_UNIQUENESS,
                    observed=stats.unique_ratio,
                    threshold=self.config.identifier_min_unique_ratio,
                )
            )
        if monotonic:
            evidence.append(self._evidence(EvidenceCode.MONOTONIC_INTEGER_SEQUENCE))
        if structured_code:
            evidence.append(self._evidence(EvidenceCode.STRUCTURED_CODE_PATTERN))
        return evidence, repeated_identifier

    def _numeric_type(
        self, stats: _ColumnStats, integer_only: bool, tokens: frozenset[str]
    ) -> SemanticType:
        if tokens & _CONTINUOUS_MEASUREMENT_TOKENS:
            return SemanticType.NUMERIC_CONTINUOUS
        if (
            integer_only
            and stats.unique_count is not None
            and stats.unique_ratio is not None
            and (
                stats.unique_count <= self.config.numeric_discrete_max_unique_count
                or (
                    stats.unique_ratio <= self.config.numeric_discrete_max_unique_ratio
                    and bool(tokens & _CATEGORICAL_TOKENS)
                )
            )
        ):
            return SemanticType.NUMERIC_DISCRETE
        return SemanticType.NUMERIC_CONTINUOUS

    def _infer_text(
        self,
        column_name: str,
        column_position: int,
        physical_dtype: str,
        tokens: frozenset[str],
        stats: _ColumnStats,
        values: list[str],
        common_evidence: list[InferenceEvidence],
    ) -> ColumnSemanticInference:
        lengths = [len(value) for value in values]
        average_length = sum(lengths) / len(lengths)
        whitespace_ratio = sum(any(char.isspace() for char in value) for value in values) / len(
            values
        )
        punctuation_ratio = sum(bool(_PUNCTUATION_PATTERN.search(value)) for value in values) / len(
            values
        )
        unique_ratio = stats.unique_ratio or 0.0
        text_hint = bool(tokens & _FREE_TEXT_TOKENS)
        long_text = average_length >= self.config.free_text_min_average_length
        descriptive_structure = (
            whitespace_ratio >= self.config.free_text_min_whitespace_ratio
            or punctuation_ratio >= self.config.free_text_min_whitespace_ratio
        )
        if (
            long_text
            and (unique_ratio >= self.config.free_text_min_unique_ratio or descriptive_structure)
        ) or (
            text_hint
            and average_length >= self.config.free_text_min_average_length / 2
            and descriptive_structure
        ):
            evidence: list[InferenceEvidence] = []
            if long_text:
                evidence.append(
                    self._evidence(
                        EvidenceCode.LONG_TEXT,
                        observed=average_length,
                        threshold=self.config.free_text_min_average_length,
                    )
                )
            if text_hint:
                evidence.append(self._evidence(EvidenceCode.NAME_HINT_FREE_TEXT))
            if unique_ratio >= self.config.free_text_min_unique_ratio:
                evidence.append(
                    self._evidence(
                        EvidenceCode.HIGH_TEXT_UNIQUENESS,
                        observed=unique_ratio,
                        threshold=self.config.free_text_min_unique_ratio,
                    )
                )
            if whitespace_ratio >= self.config.free_text_min_whitespace_ratio:
                evidence.append(
                    self._evidence(
                        EvidenceCode.TEXT_WHITESPACE,
                        observed=whitespace_ratio,
                        threshold=self.config.free_text_min_whitespace_ratio,
                    )
                )
            return self._result(
                column_name,
                column_position,
                physical_dtype,
                SemanticType.FREE_TEXT,
                self._confidence(InferenceConfidence.MEDIUM, stats.non_null_count),
                stats,
                [*evidence, *common_evidence],
            )

        repeated = stats.unique_count is not None and stats.unique_count < stats.non_null_count
        categorical_by_count = (
            repeated
            and stats.unique_count is not None
            and stats.unique_count <= self.config.categorical_max_unique_count
        )
        categorical_by_ratio_and_name = (
            repeated
            and stats.unique_ratio is not None
            and stats.unique_ratio <= self.config.categorical_max_unique_ratio
            and bool(tokens & _CATEGORICAL_TOKENS)
        )
        categorical = categorical_by_count or categorical_by_ratio_and_name
        if categorical:
            categorical_evidence = []
            if categorical_by_count:
                categorical_evidence.append(
                    self._evidence(
                        EvidenceCode.LOW_CARDINALITY,
                        observed=stats.unique_count,
                        threshold=self.config.categorical_max_unique_count,
                    )
                )
            else:
                categorical_evidence.extend(
                    [
                        self._evidence(
                            EvidenceCode.LOW_CARDINALITY,
                            observed=stats.unique_ratio,
                            threshold=self.config.categorical_max_unique_ratio,
                        ),
                        self._evidence(EvidenceCode.NAME_HINT_CATEGORICAL),
                    ]
                )
            return self._result(
                column_name,
                column_position,
                physical_dtype,
                SemanticType.CATEGORICAL,
                self._confidence(InferenceConfidence.MEDIUM, stats.non_null_count),
                stats,
                [*categorical_evidence, *common_evidence],
            )

        return self._result(
            column_name,
            column_position,
            physical_dtype,
            SemanticType.UNKNOWN,
            InferenceConfidence.LOW,
            stats,
            [
                self._evidence(
                    EvidenceCode.HIGH_CARDINALITY,
                    observed=stats.unique_ratio,
                    threshold=self.config.categorical_max_unique_ratio,
                ),
                *common_evidence,
            ],
            alternatives=(
                AlternativeSemanticCandidate(
                    semantic_type=SemanticType.CATEGORICAL,
                    confidence=InferenceConfidence.LOW,
                    evidence_codes=(EvidenceCode.HIGH_CARDINALITY,),
                ),
            ),
        )

    def _common_evidence(self, stats: _ColumnStats) -> list[InferenceEvidence]:
        evidence: list[InferenceEvidence] = []
        if stats.null_count:
            evidence.append(
                self._evidence(EvidenceCode.NULL_VALUES_PRESENT, observed=stats.null_count)
            )
        if stats.sampled:
            evidence.append(
                self._evidence(
                    EvidenceCode.DETERMINISTIC_SAMPLE,
                    observed=len(stats.values),
                    threshold=self.config.max_inspection_values,
                )
            )
        return evidence

    def _confidence(
        self, confidence: InferenceConfidence, non_null_count: int
    ) -> InferenceConfidence:
        if non_null_count >= self.config.minimum_confident_non_null:
            return confidence
        if confidence is InferenceConfidence.HIGH:
            return InferenceConfidence.MEDIUM
        return InferenceConfidence.LOW

    def _result(
        self,
        column_name: str,
        column_position: int,
        physical_dtype: str,
        semantic_type: SemanticType,
        confidence: InferenceConfidence,
        stats: _ColumnStats,
        evidence: list[InferenceEvidence],
        *,
        warnings: tuple[InferenceWarning, ...] = (),
        alternatives: tuple[AlternativeSemanticCandidate, ...] = (),
    ) -> ColumnSemanticInference:
        if (
            stats.non_null_count
            and stats.non_null_count < self.config.minimum_confident_non_null
            and semantic_type not in {SemanticType.EMPTY, SemanticType.CONSTANT}
            and not any(
                item.code is InferenceWarningCode.INSUFFICIENT_OBSERVATIONS for item in warnings
            )
        ):
            warnings = (
                *warnings,
                self._warning(
                    InferenceWarningCode.INSUFFICIENT_OBSERVATIONS,
                    "The non-null count is below the configured confident-inference minimum.",
                    column_position,
                ),
            )
        return ColumnSemanticInference(
            column_name=column_name,
            column_position=column_position,
            physical_dtype=physical_dtype,
            semantic_type=semantic_type,
            confidence=confidence,
            evidence=tuple(evidence),
            nullable=stats.null_count > 0,
            total_count=stats.total_count,
            null_count=stats.null_count,
            non_null_count=stats.non_null_count,
            unique_count=stats.unique_count,
            unique_ratio=stats.unique_ratio,
            sample_count=len(stats.values),
            sampled=stats.sampled,
            warnings=warnings,
            alternative_candidates=alternatives,
        )

    @staticmethod
    def _evidence(
        code: EvidenceCode,
        *,
        observed: int | float | None = None,
        threshold: int | float | None = None,
    ) -> InferenceEvidence:
        return InferenceEvidence(
            code=code, message=_MESSAGES[code], observed=observed, threshold=threshold
        )

    @staticmethod
    def _warning(
        code: InferenceWarningCode, message: str, column_position: int
    ) -> InferenceWarning:
        return InferenceWarning(code=code, message=message, column_position=column_position)


def _name_tokens(name: str) -> frozenset[str]:
    separated = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", name)
    return frozenset(token.casefold() for token in re.findall(r"[A-Za-z0-9]+", separated))


def _text_values(values: list[Any]) -> list[str] | None:
    if all(isinstance(value, str) for value in values):
        return [value for value in values if isinstance(value, str)]
    return None


def _all_canonical_uuids(values: list[str]) -> bool:
    return all(
        _UUID_PATTERN.fullmatch(stripped := value.strip()) is not None
        and str(UUID(stripped)) == stripped.casefold()
        for value in values
    )


def _analyze_dates(values: list[str]) -> _DateAnalysis:
    successes = 0
    date_like_count = 0
    ambiguous = False
    for raw_value in values:
        value = raw_value.strip()
        if _ISO_DATE_PATTERN.fullmatch(value):
            date_like_count += 1
            try:
                datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                try:
                    date.fromisoformat(value)
                except ValueError:
                    continue
            successes += 1
        elif _SLASH_DATE_PATTERN.fullmatch(value):
            date_like_count += 1
            parsed_orders = 0
            for date_format in ("%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d"):
                try:
                    datetime.strptime(value, date_format)
                except ValueError:
                    continue
                parsed_orders += 1
            if parsed_orders:
                successes += 1
            if parsed_orders > 1:
                ambiguous = True
    return _DateAnalysis(successes / len(values), date_like_count, ambiguous)


def _integer_only(values: list[Any]) -> bool:
    return all(math.isfinite(float(value)) and float(value).is_integer() for value in values)


def _strictly_increasing(values: list[Any]) -> bool:
    integers = [int(value) for value in values]
    return all(
        current > previous for previous, current in zip(integers, integers[1:], strict=False)
    )
