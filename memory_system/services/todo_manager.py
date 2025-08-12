"""Adapter module for legacy `todo_manager`.

This file re-exports the original implementation to the new namespace
`memory_system.services.todo_manager` so that new code can import from the
package while legacy imports continue to work.
"""
from importlib import import_module as _import_module
from types import ModuleType as _ModuleType
import sys as _sys

_legacy_module: _ModuleType = _import_module("todo_manager")

# Re-export everything
globals().update(_legacy_module.__dict__)

# Ensure that submodules referring to the new path resolve to the same object
_sys.modules[__name__] = _legacy_module