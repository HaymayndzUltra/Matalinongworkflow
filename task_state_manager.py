from __future__ import annotations

"""Minimal task state manager with optional Cursor session awareness.

This module *replaces* the absent legacy implementation referenced in the prompt.
For broader projects already shipping a task_state_manager module you can safely
import the `save_task_state` and `load_task_state` helpers below – the public API
is intentionally tiny so integration is painless.
"""

import json
import os
from datetime import datetime
from typing import Dict, Any

from cursor_session_manager import session_manager

STATE_FILE = os.path.join(os.getcwd(), "task-state.json")


# ------------------------------------------------------------------
# Core helpers ------------------------------------------------------
# ------------------------------------------------------------------

def load_task_state() -> Dict[str, Any]:
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as fp:
                return json.load(fp)
        except (OSError, json.JSONDecodeError):
            pass
    return {}


def save_task_state(extra_state: Dict[str, Any] | None = None) -> None:
    """Merge *extra_state* with the current session state and persist it."""
    state: Dict[str, Any] = load_task_state()
    state.update(extra_state or {})
    # Inject cursor session so everything is centralised.
    state["cursor_session"] = session_manager.get_state().get("cursor_session", {})
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as fp:
            json.dump(state, fp, indent=2, ensure_ascii=False)
    except OSError:
        pass


# ------------------------------------------------------------------
# Convenience API ---------------------------------------------------
# ------------------------------------------------------------------

def add_completed_task(description: str) -> None:
    """Append a completed task entry with timestamp into task history."""
    state = load_task_state()
    history = state.setdefault("task_history", [])
    history.append({"task": description, "completed": datetime.utcnow().isoformat()})
    save_task_state(state)


if __name__ == "__main__":
    import argparse
    import pprint

    parser = argparse.ArgumentParser(description="Task state helper")
    parser.add_argument("--complete", dest="done_task", help="mark a task as completed")
    parser.add_argument("--show", action="store_true", help="display saved task state")
    args = parser.parse_args()

    if args.done_task:
        add_completed_task(args.done_task)
    if args.show or not any(vars(args).values()):
        pprint.pprint(load_task_state())