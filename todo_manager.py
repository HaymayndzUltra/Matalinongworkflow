from __future__ import annotations

"""Task & TODO manager that persists to a single JSON file.

The intention is to complement Cursor's session memory by giving you a quick
CLI for creating tasks, adding TODO items, marking them done, and listing
anything still pending.  The data structure purposefully mirrors the session
state design so they can be merged later if needed.
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
import re
import subprocess

DATA_FILE = Path(os.getcwd()) / "memory-bank" / "queue-system" / "tasks_active.json"

# ------------------------------------------------------------------
# Configuration -----------------------------------------------------
# ------------------------------------------------------------------
# How many days a *completed* task should be retained before it is
# automatically purged from the JSON storage.  This can be overridden
# at runtime via the TODO_CLEANUP_DAYS environment variable so teams
# can easily adjust retention without touching code.
DEFAULT_CLEANUP_DAYS = int(os.getenv("TODO_CLEANUP_DAYS", "7"))


def _load() -> List[Dict[str, Any]]:
    if DATA_FILE.exists():
        try:
            data = json.loads(DATA_FILE.read_text("utf-8"))
            # Handle both old format {"tasks": [...]} and new format [...]
            if isinstance(data, dict):
                # Legacy formats: either {'tasks': [...]} OR mapping of id->task
                if "tasks" in data:
                    data = data["tasks"]
                else:
                    # assume dict of id->task objects
                    data = list(data.values())
            # Opportunistically clean up outdated tasks on every load
            if _cleanup_outdated_tasks(data):
                _save(data)
            return data
        except json.JSONDecodeError:
            pass
    return []


# ------------------------------------------------------------------
# House-keeping helpers --------------------------------------------
# ------------------------------------------------------------------


def _cleanup_outdated_tasks(data: List[Dict[str, Any]]) -> bool:
    """Auto-purge completed tasks older than *DEFAULT_CLEANUP_DAYS*.

    Returns True if the dataset was modified (i.e. tasks removed).
    """

    now = datetime.utcnow()

    def _is_stale(task: Dict[str, Any]) -> bool:
        if task.get("status") != "completed":
            return False

        try:
            # Prefer the last *updated* timestamp so we keep recently reopened
            # tasks even if originally created long ago.
            last = datetime.fromisoformat(task.get("updated", task.get("created")))
            return (now - last).days >= DEFAULT_CLEANUP_DAYS
        except Exception:
            # If parsing fails for whatever reason, be conservative and keep
            # the task – we don't want to delete user data accidentally.
            return False

    before = len(data)
    data[:] = [t for t in data if not _is_stale(t)]  # In-place modification
    return len(data) < before


def _save(data: List[Dict[str, Any]]) -> None:
    DATA_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False))

    # Update Markdown session dump for visibility.
    try:
        from cursor_memory_bridge import dump_markdown  # type: ignore

        dump_markdown()
    except Exception:
        pass
    
    # 🔄 Auto-sync state files after any data change
    try:
        from auto_sync_manager import auto_sync
        auto_sync()
    except Exception:
        pass  # Don't fail if auto-sync is not available


def _timestamp() -> str:
    """Get current Philippines time in ISO format"""
    from datetime import timezone, timedelta
    utc_now = datetime.utcnow()
    philippines_tz = timezone(timedelta(hours=8))
    ph_time = utc_now.astimezone(philippines_tz)
    return ph_time.isoformat()


# ------------------------------------------------------------------
# CRUD helpers ------------------------------------------------------
# ------------------------------------------------------------------

def new_task(description: str) -> str:
    data = _load()
    # Create a more descriptive task ID that's not truncated
    from datetime import timezone, timedelta
    utc_now = datetime.utcnow()
    philippines_tz = timezone(timedelta(hours=8))
    ph_time = utc_now.astimezone(philippines_tz)
    timestamp = ph_time.strftime('%Y%m%dT%H%M%S')
    # Use first 50 characters of description for better readability
    desc_part = description.replace(' ', '_')[:50]
    task_id = f"{timestamp}_{desc_part}"
    
    data.append(
        {
            "id": task_id,
            "description": description,
            "todos": [],
            "status": "in_progress",
            "created": _timestamp(),
            "updated": _timestamp(),
        }
    )
    _save(data)
    print(f"✅ Created task: {task_id}")
    print(f"   Description: {description}")
    return task_id


def add_todo(task_id: str, text: str) -> None:
    data = _load()
    task = next((t for t in data if t["id"] == task_id), None)
    if task is None:
        print(f"❌ Task '{task_id}' not found.")
        return
    task["todos"].append({"text": text, "done": False})
    task["updated"] = _timestamp()
    _save(data)
    print(f"✅ Added TODO: {text}")


def mark_done(task_id: str, index: int) -> None:
    data = _load()
    task = next((t for t in data if t["id"] == task_id), None)
    if task is None:
        print(f"❌ Task '{task_id}' not found.")
        return
    
    if not task["todos"]:
        print(f"❌ Task '{task_id}' has no TODO items to mark as done.")
        print(f"   Use 'python3 todo_manager.py add {task_id} <todo_text>' to add TODO items first.")
        return
    
    try:
        if index < 0 or index >= len(task["todos"]):
            print(f"❌ Invalid index {index}. Valid range is 0 to {len(task['todos']) - 1}")
            print(f"   Available TODO items:")
            for i, todo in enumerate(task["todos"]):
                mark = "✔" if todo["done"] else "✗"
                print(f"   [{mark}] {i}. {todo['text']}")
            return
        
        task["todos"][index]["done"] = True
        task["updated"] = _timestamp()

        # ------------------------------------------------------------------
        # Auto-completion logic: if *all* TODO items are now done we will mark
        # the parent task as completed so downstream tooling (e.g. UI lists,
        # cleanup) can react accordingly without relying on manual commands.
        # ------------------------------------------------------------------
        if all(t["done"] for t in task["todos"]):
            task["status"] = "completed"

        _save(data)
        print(f"✅ Marked TODO {index} as done: {task['todos'][index]['text']}")
    except (IndexError, ValueError) as e:
        print(f"❌ Error marking TODO {index} as done: {e}")
        print(f"   Available TODO items:")
        for i, todo in enumerate(task["todos"]):
            mark = "✔" if todo["done"] else "✗"
            print(f"   [{mark}] {i}. {todo['text']}")


def delete_todo(task_id: str, index: int) -> None:
    """Delete a TODO item completely from the task"""
    data = _load()
    task = next((t for t in data if t["id"] == task_id), None)
    if task is None:
        print(f"❌ Task '{task_id}' not found.")
        return
    
    if not task["todos"]:
        print(f"❌ Task '{task_id}' has no TODO items to delete.")
        return
    
    try:
        if index < 0 or index >= len(task["todos"]):
            print(f"❌ Invalid index {index}. Valid range is 0 to {len(task['todos']) - 1}")
            print(f"   Available TODO items:")
            for i, todo in enumerate(task["todos"]):
                mark = "✔" if todo["done"] else "✗"
                print(f"   [{mark}] {i}. {todo['text']}")
            return
        
        # Get the TODO text before deleting
        todo_text = task["todos"][index]["text"]
        
        # Remove the TODO item
        deleted_todo = task["todos"].pop(index)
        task["updated"] = _timestamp()
        _save(data)
        
        print(f"🗑️  Deleted TODO {index}: {todo_text}")
        
        # Show remaining TODO items
        if task["todos"]:
            print(f"   Remaining TODO items:")
            for i, todo in enumerate(task["todos"]):
                mark = "✔" if todo["done"] else "✗"
                print(f"   [{mark}] {i}. {todo['text']}")
        else:
            print(f"   No TODO items remaining.")
            
    except (IndexError, ValueError) as e:
        print(f"❌ Error deleting TODO {index}: {e}")
        print(f"   Available TODO items:")
        for i, todo in enumerate(task["todos"]):
            mark = "✔" if todo["done"] else "✗"
            print(f"   [{mark}] {i}. {todo['text']}")


def list_open_tasks() -> List[Dict[str, Any]]:
    data = _load()

    # Return newest tasks first so fresh items always grab the user's
    # attention at the top of interactive menus.
    open_tasks = [t for t in data if t.get("status") != "completed"]
    try:
        open_tasks.sort(key=lambda t: t.get("created", ""), reverse=True)
    except Exception:
        # Fallback – if timestamps are malformed we still return unsorted list.
        pass

    return open_tasks


def set_task_status(task_id: str, status: str) -> None:
    data = _load()
    for t in data:
        if t["id"] == task_id:
            t["status"] = status
            t["updated"] = _timestamp()
            _save(data)
            print(f"✅ Updated task '{task_id}' status to '{status}'")
            return
    print(f"❌ Task '{task_id}' not found.")


def hard_delete_task(task_id: str) -> None:
    """Completely remove task from memory (hard delete)"""
    data = _load()
    original_count = len(data)
    
    # Remove task completely  
    data[:] = [t for t in data if t["id"] != task_id]  # In-place modification
    
    if len(data) < original_count:
        _save(data)
        print(f"🗑️  Completely deleted task '{task_id}' from memory")
        
        # Also clean up from interruption manager if exists
        try:
            from task_interruption_manager import interruption_manager
            # Remove from current task if it matches
            if interruption_manager.current_task and interruption_manager.current_task['task_id'] == task_id:
                interruption_manager.current_task = None
                interruption_manager.save_state()
                print(f"   Also removed from active task")
            
            # Remove from interrupted tasks if it matches
            interruption_manager.interrupted_tasks = [
                t for t in interruption_manager.interrupted_tasks 
                if t['task_id'] != task_id
            ]
            interruption_manager.save_state()
            print(f"   Also removed from interrupted tasks")
            
        except Exception as e:
            print(f"   Note: Could not clean up interruption state: {e}")
        
        # Clean up memory-bank files
        try:
            import os
            from pathlib import Path
            
            # Clean up current-session.md if it contains the deleted task
            session_file = Path("memory-bank/current-session.md")
            if session_file.exists():
                content = session_file.read_text(encoding='utf-8')
                if task_id in content:
                    # Remove the task reference from the session file
                    lines = content.split('\n')
                    cleaned_lines = []
                    skip_next = False
                    
                    for line in lines:
                        if task_id in line:
                            skip_next = True
                            continue
                        if skip_next and line.strip() == "":
                            skip_next = False
                            continue
                        if not skip_next:
                            cleaned_lines.append(line)
                    
                    session_file.write_text('\n'.join(cleaned_lines), encoding='utf-8')
                    print(f"   Also cleaned up memory-bank/current-session.md")
            
            # Clean up cursor_state.json if it contains the deleted task
            cursor_file = Path("cursor_state.json")
            if cursor_file.exists():
                import json
                try:
                    with open(cursor_file, 'r') as f:
                        cursor_data = json.load(f)
                    
                    # Check if current_task contains the deleted task description
                    current_task = cursor_data.get('cursor_session', {}).get('current_task', '')
                    if task_id in current_task:
                        # Clear the current task
                        cursor_data['cursor_session']['current_task'] = ""
                        cursor_data['cursor_session']['progress'] = 0.0
                        
                        with open(cursor_file, 'w') as f:
                            json.dump(cursor_data, f, indent=2)
                        print(f"   Also cleaned up cursor_state.json")
                except Exception as e:
                    print(f"   Note: Could not clean up cursor state: {e}")
                    
        except Exception as e:
            print(f"   Note: Could not clean up memory-bank files: {e}")
    else:
        print(f"❌ Task '{task_id}' not found.")


def cleanup_completed_tasks() -> None:
    """Remove all completed tasks from memory"""
    data = _load()
    original_count = len(data)
    
    # Keep only non-completed tasks
    data[:] = [t for t in data if t.get("status") != "completed"]  # In-place modification
    
    removed_count = original_count - len(data)
    
    if removed_count > 0:
        _save(data)
        print(f"🧹 Cleaned up {removed_count} completed task(s) from memory")
    else:
        print("ℹ️  No completed tasks to clean up")


def show_task_details(task_id: str) -> None:
    """Show detailed information about a specific task"""
    data = _load()
    task = next((t for t in data if t["id"] == task_id), None)
    if task is None:
        print(f"❌ Task '{task_id}' not found.")
        return
    
    print(f"\n📋 Task Details:")
    print(f"   ID: {task['id']}")
    print(f"   Description: {task['description']}")
    print(f"   Status: {task['status']}")
    print(f"   Created: {task['created']}")
    print(f"   Updated: {task['updated']}")
    
    if task["todos"]:
        print(f"   TODO Items ({len(task['todos'])}):")
        for i, todo in enumerate(task["todos"]):
            mark = "✔" if todo["done"] else "✗"
            status = "DONE" if todo["done"] else "PENDING"
            print(f"     [{mark}] {i}. {todo['text']} ({status})")
    else:
        print(f"   TODO Items: None (use 'add' command to add TODO items)")


# ------------------------------------------------------------------
# CLI ----------------------------------------------------------------
# ------------------------------------------------------------------

def _print_task(task: Dict[str, Any]) -> None:
    print(f"🗒️  {task['id']}")
    print(f"   Description: {task['description']}")
    print(f"   Status: {task['status']}")
    if task["todos"]:
        print(f"   TODO Items ({len(task['todos'])}):")
        for i, todo in enumerate(task["todos"]):
            mark = "✔" if todo["done"] else "✗"
            print(f"     [{mark}] {i}. {todo['text']}")
    else:
        print(f"   📝 No TODO items (use 'add' command to add TODO items)")
    print()  # Add spacing for better readability


# ------------------------------------------------------------------
# Execution helpers -------------------------------------------------
# ------------------------------------------------------------------

def _extract_fenced_code_blocks(markdown: str) -> List[str]:
    """Return contents of fenced code blocks from markdown text (no backticks)."""
    if not markdown:
        return []
    pattern = re.compile(r"```(?:[a-zA-Z0-9_+-]+)?\n([\s\S]*?)\n```", re.MULTILINE)
    return [m.group(1).strip() for m in pattern.finditer(markdown)]


def _parse_sub_index(sub_index: str) -> (int, Optional[int]):
    """Parse sub-index like '4.1' → (4, 0). If '4' → (4, None)."""
    try:
        if "." in sub_index:
            phase_str, cmd_str = sub_index.split(".", 1)
            phase_idx = int(phase_str)
            cmd_idx = int(cmd_str) - 1
            if cmd_idx < 0:
                raise ValueError("Command index must be >= 1")
            return phase_idx, cmd_idx
        return int(sub_index), None
    except Exception:
        raise ValueError("Invalid sub-index format. Use 'K' or 'K.N' (e.g., 4 or 4.1)")


def _replace_placeholders_in_command(command: str, task_id: str, phase_index: int, command_index_one_based: Optional[int]) -> str:
    """Replace common placeholders in a command string with concrete values.

    Supported placeholders:
      - <task_id ReplaceAll>, <task_id Replace All>, <task_id>, <TASK_ID>
      - <PHASE_INDEX>, <phase_index>
      - <SUB_INDEX>, <sub_index> (uses 1-based index when available)
    """
    replacements = {
        "<task_id ReplaceAll>": task_id,
        "<task_id Replace All>": task_id,
        "<task_id>": task_id,
        "<TASK_ID>": task_id,
        "<PHASE_INDEX>": str(phase_index),
        "<phase_index>": str(phase_index),
    }

    if command_index_one_based is not None:
        replacements.update(
            {
                "<SUB_INDEX>": str(command_index_one_based),
                "<sub_index>": str(command_index_one_based),
            }
        )

    for needle, value in replacements.items():
        command = command.replace(needle, value)
    return command


# ------------------------------------------------------------------
# Deep Analysis Gate helpers ---------------------------------------
# ------------------------------------------------------------------

def _analysis_file() -> Path:
    return Path(os.getcwd()) / "memory-bank" / "queue-system" / "analysis_active.json"


def _load_json_list(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and "tasks" in data:
            data = data["tasks"]
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _find_analysis_for_task(execution_task_id: str) -> Optional[Dict[str, Any]]:
    """Find analysis task linked to the execution task via source_task_id or id prefix."""
    analyses = _load_json_list(_analysis_file())
    for a in analyses:
        if a.get("source_task_id") == execution_task_id:
            return a
    for a in analyses:
        if str(a.get("id", "")).startswith(f"{execution_task_id}_analysis_"):
            return a
    return None


def _analysis_phase_has_required_sections(text: str) -> bool:
    return ("IMPORTANT NOTE:" in (text or "")) and ("Decision Gate" in (text or ""))


def _analysis_phase_has_blocking_findings(text: str) -> bool:
    txt = text or ""
    return (
        re.search(r"Type:\s*Conflict", txt, re.I) is not None
        or re.search(r"Type:\s*Duplicate", txt, re.I) is not None
    )


def enforce_deep_analysis_gate(execution_task_id: str) -> (bool, str):
    """Return (ok, message). ok=False blocks execution side-effects for this task."""
    analysis = _find_analysis_for_task(execution_task_id)
    if analysis is None:
        return (
            False,
            "No analysis found in analysis_active.json for this execution task (missing source_task_id link).",
        )
    todos = analysis.get("todos", [])
    if not todos:
        return False, "Analysis task has no phases."
    for idx, td in enumerate(todos):
        txt = td.get("text", "")
        if not td.get("done"):
            return False, f"Analysis phase {idx} not done."
        if not _analysis_phase_has_required_sections(txt):
            return False, f"Analysis phase {idx} missing 'Decision Gate' or 'IMPORTANT NOTE:'."
        if _analysis_phase_has_blocking_findings(txt):
            return False, f"Analysis phase {idx} contains blocking Findings (Conflict/Duplicate)."
    return True, "Deep Analysis Gate passed."


# ------------------------------------------------------------------
# Mode selection for data file -------------------------------------
# ------------------------------------------------------------------

def _set_data_file_for_mode(mode: str) -> None:
    """Switch DATA_FILE to execution or analysis SOT for CRUD/show flows."""
    global DATA_FILE
    base = Path(os.getcwd()) / "memory-bank" / "queue-system"
    if mode == "analysis":
        DATA_FILE = base / "analysis_active.json"
    else:
        DATA_FILE = base / "tasks_active.json"


def exec_substep(task_id: str, sub_index: str, run: bool = False) -> None:
    """Preview (default) or run command(s) for a specific phase sub-step.

    - sub_index format:
      - 'K' → select phase K and preview all commands in its first fenced block
      - 'K.N' → select the Nth command (1-based) inside the first fenced block of phase K
    - run=False: print the command(s) to be executed (dry run)
    - run=True: actually execute the command(s)
    """
    data = _load()
    task = next((t for t in data if t.get("id") == task_id), None)
    if task is None:
        print(f"❌ Task '{task_id}' not found.")
        return

    try:
        phase_idx, cmd_idx = _parse_sub_index(sub_index)
    except ValueError as e:
        print(f"❌ {e}")
        return

    todos = task.get("todos", [])
    if phase_idx < 0 or phase_idx >= len(todos):
        print(f"❌ Invalid phase index {phase_idx}. Valid range is 0 to {len(todos) - 1}")
        return

    phase = todos[phase_idx]
    text = phase.get("text", "")
    blocks = _extract_fenced_code_blocks(text)
    if not blocks:
        print("❌ No fenced code block found in this phase.")
        return

    lines = [ln for ln in blocks[0].splitlines() if ln.strip() and not ln.strip().startswith("#")]
    # Resolve placeholders before preview/execution to avoid shell redirection issues
    resolved_lines = [
        _replace_placeholders_in_command(
            ln, task_id=task_id, phase_index=phase_idx, command_index_one_based=(cmd_idx + 1) if cmd_idx is not None else None
        )
        for ln in lines
    ]
    if not lines:
        print("❌ No executable lines found in the first fenced code block.")
        return

    selected: List[str]
    if cmd_idx is None:
        selected = resolved_lines
        print("🔎 Selected all commands in phase block (dry-run by default):")
    else:
        if cmd_idx >= len(lines):
            print(f"❌ Command index {cmd_idx + 1} out of range (1..{len(lines)})")
            return
        selected = [resolved_lines[cmd_idx]]
        print(f"🔎 Selected command #{cmd_idx + 1} (dry-run by default):")

    for cmd in selected:
        print(f"   $ {cmd}")

    if not run:
        print("💡 Use '--run' to actually execute. Keeping it safe (preview only).")
        return

    print("🚀 Executing...")
    for cmd in selected:
        try:
            # Use shell to allow pipelines; execution is explicit via --run flag
            result = subprocess.run(cmd, shell=True, text=True, capture_output=True)
            print(f"$ {cmd}")
            print(f"↳ exit={result.returncode}")
            if result.stdout:
                print(result.stdout.rstrip())
            if result.stderr:
                print(result.stderr.rstrip())
            if result.returncode != 0:
                print("⚠️ Command returned non-zero status. Stopping further execution.")
                break
        except Exception as e:
            print(f"❌ Execution failed: {e}")
            break


def main(argv: Optional[List[str]] = None) -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Todo manager")
    sub = parser.add_subparsers(dest="cmd")

    sub_new = sub.add_parser("new", help="create a new task")
    sub_new.add_argument("description")
    sub_new.add_argument("--mode", choices=["execution", "analysis"], default="execution")

    sub_add = sub.add_parser("add", help="add todo to task")
    sub_add.add_argument("task_id")
    sub_add.add_argument("text")
    sub_add.add_argument("--mode", choices=["execution", "analysis"], default="execution")

    sub_done = sub.add_parser("done", help="mark todo item done")
    sub_done.add_argument("task_id")
    sub_done.add_argument("index", help="TODO item index (0-based)")
    sub_done.add_argument("--mode", choices=["execution", "analysis"], default="execution")

    sub_delete = sub.add_parser("delete", help="delete todo item completely")
    sub_delete.add_argument("task_id")
    sub_delete.add_argument("index", help="TODO item index (0-based)")
    sub_delete.add_argument("--mode", choices=["execution", "analysis"], default="execution")

    sub_list = sub.add_parser("list", help="list open tasks")
    sub_list.add_argument("--mode", choices=["execution", "analysis"], default="execution")
    
    sub_show = sub.add_parser("show", help="show detailed task information")
    sub_show.add_argument("task_id")
    sub_show.add_argument("--mode", choices=["execution", "analysis"], default="execution")

    sub_hard_delete = sub.add_parser("hard_delete", help="completely remove task from memory")
    sub_hard_delete.add_argument("task_id")
    sub_hard_delete.add_argument("--mode", choices=["execution", "analysis"], default="execution")

    sub_cleanup = sub.add_parser("cleanup", help="remove all completed tasks from memory")
    sub_cleanup.add_argument("--mode", choices=["execution", "analysis"], default="execution")

    # New: exec subcommand (safe preview by default; use --run to execute)
    sub_exec = sub.add_parser("exec", help="execute a specific sub-step command (preview by default)")
    sub_exec.add_argument("task_id")
    sub_exec.add_argument("sub_index", help="Format: K or K.N (e.g., 4 or 4.1)")
    sub_exec.add_argument("--run", action="store_true", help="Actually run the command(s)")

    args = parser.parse_args(argv)

    if args.cmd == "new":
        _set_data_file_for_mode(args.mode)
        new_task(args.description)
    elif args.cmd == "add":
        _set_data_file_for_mode(args.mode)
        add_todo(args.task_id, args.text)
    elif args.cmd == "done":
        _set_data_file_for_mode(args.mode)
        # Handle index parsing manually to support various formats
        try:
            # Try to parse as integer first
            index = int(args.index)
        except ValueError:
            # If it's not a number, check if it's a special format
            if args.index == "—" or args.index == "-":
                print("❌ Invalid index format. Please use a number (0, 1, 2, etc.)")
                print("   Example: python3 todo_manager.py done <task_id> 0")
                return
            else:
                print(f"❌ Invalid index '{args.index}'. Please use a number (0, 1, 2, etc.)")
                print("   Example: python3 todo_manager.py done <task_id> 0")
                return
        
        # Enforce deep analysis gate for execution mode marking done
        if args.mode == "execution":
            ok, msg = enforce_deep_analysis_gate(args.task_id)
            if not ok:
                print(f"⛔ Deep Analysis Gate BLOCK: {msg}")
                return
        mark_done(args.task_id, index)
    elif args.cmd == "delete":
        _set_data_file_for_mode(args.mode)
        # Handle index parsing manually to support various formats
        try:
            # Try to parse as integer first
            index = int(args.index)
        except ValueError:
            # If it's not a number, check if it's a special format
            if args.index == "—" or args.index == "-":
                print("❌ Invalid index format. Please use a number (0, 1, 2, etc.)")
                print("   Example: python3 todo_manager.py delete <task_id> 0")
                return
            else:
                print(f"❌ Invalid index '{args.index}'. Please use a number (0, 1, 2, etc.)")
                print("   Example: python3 todo_manager.py delete <task_id> 0")
                return
        
        delete_todo(args.task_id, index)
    elif args.cmd == "exec":
        # Allow preview without gate; enforce gate only when --run
        if args.run:
            ok, msg = enforce_deep_analysis_gate(args.task_id)
            if not ok:
                print(f"⛔ Deep Analysis Gate BLOCK: {msg}")
                return
        exec_substep(args.task_id, args.sub_index, args.run)
    elif args.cmd == "show":
        _set_data_file_for_mode(args.mode)
        show_task_details(args.task_id)
    elif args.cmd == "hard_delete":
        _set_data_file_for_mode(args.mode)
        hard_delete_task(args.task_id)
    elif args.cmd == "cleanup":
        _set_data_file_for_mode(args.mode)
        cleanup_completed_tasks()
    else:
        _set_data_file_for_mode("execution")
        tasks = list_open_tasks()
        if tasks:
            print(f"🔎 {len(tasks)} open tasks:")
            for t in tasks:
                _print_task(t)
                print()  # Add spacing between tasks
        else:
            print("🔎 No open tasks found.")
            print("   Use 'python3 todo_manager.py new <description>' to create a new task")


if __name__ == "__main__":
    main(sys.argv[1:])