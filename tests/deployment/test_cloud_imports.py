"""Deployment-oriented import smoke checks for a clean Linux-style package install."""

import importlib


def test_runtime_modules_are_importable_from_installable_package() -> None:
    assert importlib.import_module("haralens")
    assert importlib.import_module("haralens.application")
    assert importlib.import_module("haralens.analytics")
    assert importlib.import_module("haralens.readiness")
    assert importlib.import_module("haralens.insights")
    assert importlib.import_module("haralens.reporting")
