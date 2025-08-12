"""Adapter for legacy `task_interruption_manager`."""
from importlib import import_module as _import_module
import sys as _sys

_mod = _import_module("task_interruption_manager")
globals().update(_mod.__dict__)
_sys.modules[__name__] = _mod