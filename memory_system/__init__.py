"""Memory System package (skeleton).

This namespace package will gradually absorb existing modules from the monorepo, providing
clean separation between Domain, Services, and Interface layers.

Phase-1 deliverable created automatically by the blueprint executor.
"""
from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("memory_system")
except PackageNotFoundError:
    # Package not yet installed, default to dev tag
    __version__ = "0.0.0-dev"

__all__ = ["__version__"]