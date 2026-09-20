"""HaraLens application foundations."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("haralens") or "0.1.0"
except PackageNotFoundError:
    __version__ = "0.1.0"
