import json
import os
import threading
import time
import atexit
from datetime import datetime
from typing import Any, Dict, Optional


class CursorSessionManager:
    """Light-weight utility that remembers the user's current Cursor context.

    The design principle is: *no dependencies, no network*, just drop-in and go.
    A single JSON file (``cursor_state.json`` at the project root) is used as the
    source-of-truth across sessions.  The manager keeps the file in sync every
    ``autosave_interval`` seconds and again on interpreter shutdown.
    """

    DEFAULT_STATE_FILE = os.path.join(os.getcwd(), "cursor_state.json")

    def __init__(self, state_file: str | None = None, autosave_interval: int = 30):
        self.state_file = state_file or self.DEFAULT_STATE_FILE
        self._state: Dict[str, Any] = {}
        # Use a *re-entrant* lock so that internal helpers that end up calling
        # other public methods (e.g. _save_state_to_disk -> dump_markdown ->
        # session_manager.get_state) do **not** dead-lock when they try to
        # acquire the same lock in the same thread.
        self._lock = threading.RLock()
        self.autosave_interval = autosave_interval
        self._stop_event = threading.Event()
        self._autosave_thread: Optional[threading.Thread] = None

        # Load persisted state (if any) so consumers can immediately resume.
        self._load_state_from_disk()

        # Start periodic persistence in a daemon thread.
        self._start_autosave()

        # Ensure graceful persistence on clean interpreter exit.
        atexit.register(self.end_session)

    # ---------------------------------------------------------------------
    # Public helper API ----------------------------------------------------
    # ---------------------------------------------------------------------
    def update(self,
               current_file: Optional[str] = None,
               cursor_line: Optional[int] = None,
               current_task: Optional[str] = None,
               progress: Optional[float] = None) -> None:
        """Update one or more fields in the in-memory state structure."""
        with self._lock:
            if current_file is not None:
                self._state.setdefault("cursor_session", {})["current_file"] = current_file
            if cursor_line is not None:
                self._state.setdefault("cursor_session", {})["cursor_line"] = cursor_line
            if current_task is not None:
                self._state.setdefault("cursor_session", {})["current_task"] = current_task
            if progress is not None:
                self._state.setdefault("cursor_session", {})["progress"] = float(progress)
            self._state.setdefault("cursor_session", {})["last_activity"] = (
                datetime.utcnow().isoformat()
            )

    def get_state(self) -> Dict[str, Any]:
        """Return a *copy* of the current session state."""
        with self._lock:
            return json.loads(json.dumps(self._state))  # deep-ish copy

    def resume_state(self) -> Dict[str, Any]:
        """Return the last persisted state (on disk). Useful at program boot."""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, "r", encoding="utf-8") as fp:
                    return json.load(fp)
            except (json.JSONDecodeError, OSError):
                pass
        return {}

    # ------------------------------------------------------------------
    # Internal helpers --------------------------------------------------
    # ------------------------------------------------------------------
    def _start_autosave(self) -> None:
        def _save_loop() -> None:
            while not self._stop_event.wait(self.autosave_interval):
                self._save_state_to_disk()
        self._autosave_thread = threading.Thread(
            target=_save_loop, name="CursorSessionAutosave", daemon=True
        )
        self._autosave_thread.start()

    def _load_state_from_disk(self) -> None:
        if os.path.isfile(self.state_file):
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    self._state = json.load(f)
            except (json.JSONDecodeError, OSError):
                # Corrupted or inaccessible state file – start fresh.
                self._state = {}
        else:
            self._state = {}

    def _save_state_to_disk(self) -> None:
        with self._lock:
            tmp_path = f"{self.state_file}.tmp"
            try:
                with open(tmp_path, "w", encoding="utf-8") as f:
                    json.dump(self._state, f, indent=2, ensure_ascii=False)
                os.replace(tmp_path, self.state_file)

                # ALSO refresh human-readable markdown snapshot so Cursor
                # background agent always has up-to-date context without
                # manual --dump calls.
                try:
                    from cursor_memory_bridge import dump_markdown  # local import to avoid circular

                    dump_markdown()
                except Exception:
                    # Silently ignore to avoid recursion / startup import issues
                    pass
            except OSError:
                # Best effort – swallow errors so we never crash the main app.
                pass

    # ------------------------------------------------------------------
    # Lifecycle ---------------------------------------------------------
    # ------------------------------------------------------------------
    def end_session(self) -> None:
        """Mark a *disconnect* event and flush state to disk."""
        with self._lock:
            self._state.setdefault("cursor_session", {})["disconnected_at"] = (
                datetime.utcnow().isoformat()
            )
        self._save_state_to_disk()
        self._stop_event.set()


# Singleton pattern for convenience – most scripts will simply import this
# file and interact with the global ``session_manager`` instance.
session_manager = CursorSessionManager()


# ----------------------------------------------------------------------
# Optional: tiny CLI for quick inspection --------------------------------
# ----------------------------------------------------------------------
if __name__ == "__main__":
    import argparse
    import pprint

    parser = argparse.ArgumentParser(description="Inspect or update cursor session state.")
    parser.add_argument("--file", dest="current_file", help="file you are currently editing")
    parser.add_argument("--line", dest="cursor_line", type=int, help="cursor line number")
    parser.add_argument("--task", dest="current_task", help="current task description")
    parser.add_argument("--progress", dest="progress", type=float, help="progress 0-1 range")
    parser.add_argument("--show", action="store_true", help="print the current state then exit")
    parser.add_argument("--summary", action="store_true", help="print short human summary then exit")

    args = parser.parse_args()

    if any([args.current_file, args.cursor_line, args.current_task, args.progress is not None]):
        session_manager.update(
            current_file=args.current_file,
            cursor_line=args.cursor_line,
            current_task=args.current_task,
            progress=args.progress,
        )
        # Give the autosave thread a brief moment to write to disk.
        time.sleep(0.1)
    if args.summary:
        state = session_manager.get_state().get("cursor_session", {})
        if state:
            print("📝 Cursor Session Summary:")
            print(f"   • File      : {state.get('current_file', '—')}")
            print(f"   • Line      : {state.get('cursor_line', '—')}")
            print(f"   • Task      : {state.get('current_task', '—')}")
            print(f"   • Progress  : {state.get('progress', '—')}")
        else:
            print("ℹ️  No session data recorded yet.")
    elif args.show or not any(vars(args).values()):
        pprint.pprint(session_manager.get_state())