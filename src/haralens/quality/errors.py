"""Safe typed errors for registry, context, configuration, and check execution."""

from __future__ import annotations


class QualityFrameworkError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message

    def __str__(self) -> str:
        return self.message


class DuplicateCheckIdError(QualityFrameworkError):
    def __init__(self, check_id: str) -> None:
        super().__init__("DUPLICATE_CHECK_ID", f"Duplicate quality check ID: {check_id}")


class UnknownCheckIdError(QualityFrameworkError):
    def __init__(self, check_id: str) -> None:
        super().__init__("UNKNOWN_CHECK_ID", f"Unknown quality check ID: {check_id}")


class QualityConfigurationError(QualityFrameworkError):
    pass


class QualityContextError(QualityFrameworkError):
    pass


class QualityResourceError(QualityFrameworkError):
    pass


class ExpectedCheckError(QualityFrameworkError):
    """A declared data, prerequisite, or resource limitation."""


class CheckPrerequisiteError(ExpectedCheckError):
    pass


class CheckResourceLimitError(ExpectedCheckError):
    pass


class CheckDataUnsupportedError(ExpectedCheckError):
    pass


class UnexpectedCheckError(QualityFrameworkError):
    """A safely redacted unexpected check implementation failure."""
