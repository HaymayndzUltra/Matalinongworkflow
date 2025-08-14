#!/usr/bin/env python3
"""
Proceed an active task through up to N phases with documentation and state updates.

- Identifies the next unfinished phase for the given task (or auto-selects the first incomplete active task if not specified)
- Extracts and restates the IMPORTANT NOTE
- Writes Post-Review (current phase) and Pre-Analysis (next phase) documents
- Marks the current phase done via todo_manager.py CLI
- Repeats up to --max-loops times or until the task is complete

Usage:
  python3 scripts/proceed_task.py --task-id <ID> --max-loops 5
  python3 scripts/proceed_task.py --max-loops 3  # auto-detect task
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# ---------------------- Helpers ----------------------

def detect_repo_root() -> Path:
    cwd = Path.cwd()
    if (cwd / "memory-bank" / "queue-system" / "tasks_active.json").exists():
        return cwd
    for env_name in ("VOICE_ASSISTANT_PROD_ROOT", "AI_SYSTEM_MONOREPO"):
        env_val = os.getenv(env_name)
        if env_val:
            root = Path(env_val)
            if (root / "memory-bank" / "queue-system" / "tasks_active.json").exists():
                return root
    default_root = Path("/workspace")
    if (default_root / "memory-bank" / "queue-system" / "tasks_active.json").exists():
        return default_root
    fallback = Path("/home/haymayndz/MatalinongWorkflow")
    if (fallback / "memory-bank" / "queue-system" / "tasks_active.json").exists():
        return fallback
    return cwd


REPO_ROOT = detect_repo_root()
QUEUE_DIR = REPO_ROOT / "memory-bank" / "queue-system"
ACTIVE_PATH = QUEUE_DIR / "tasks_active.json"
DOC_DIR = REPO_ROOT / "memory-bank" / "DOCUMENTS"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []


def write_text(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def now_ph_iso() -> str:
    ph_tz = timezone(timedelta(hours=8))
    return datetime.utcnow().astimezone(ph_tz).isoformat()


@dataclass
class ActiveTask:
    id: str
    todos: List[Dict[str, Any]]
    status: str


def load_active_tasks() -> List[ActiveTask]:
    data = read_json(ACTIVE_PATH)
    if isinstance(data, dict) and "tasks" in data:
        data = data["tasks"]
    result: List[ActiveTask] = []
    for t in data:
        result.append(ActiveTask(id=t.get("id", ""), todos=t.get("todos", []), status=t.get("status", "")))
    return result


def find_task(tasks: List[ActiveTask], task_id: Optional[str]) -> Optional[ActiveTask]:
    if task_id:
        return next((t for t in tasks if t.id == task_id), None)
    # pick first task that is not completed and has unfinished todos
    for t in tasks:
        if t.status != "completed":
            idx, _ = first_unfinished(t.todos)
            if idx >= 0:
                return t
    return None


def first_unfinished(todos: List[Dict[str, Any]]) -> Tuple[int, Optional[Dict[str, Any]]]:
    for i, td in enumerate(todos):
        if not bool(td.get("done", False)):
            return i, td
    return -1, None


def extract_important_note(markdown: str) -> str:
    if not markdown:
        return ""
    pos = markdown.find("IMPORTANT NOTE:")
    if pos < 0:
        return "IMPORTANT NOTE: [MISSING IN PHASE TEXT]"
    return markdown[pos:].strip()


def write_docs(task_id: str, phase_index: int, note_current: str, note_next: str) -> None:
    DOC_DIR.mkdir(parents=True, exist_ok=True)
    now = now_ph_iso()
    post = DOC_DIR / f"{task_id}_phase{phase_index}_postreview.md"
    pre = DOC_DIR / f"{task_id}_phase{phase_index+1}_preanalysis.md"

    post_md = f"""# Post-Review — Phase {phase_index}

- Task: {task_id}
- Phase Index: {phase_index}
- Timestamp: {now}

## IMPORTANT NOTE (Restated)
{note_current}

### How constraints were satisfied
- [ ] Describe evidence per constraint

## What was done
- 

## Evidence / Outputs
- 

## Checks
- Plan gates passed (plan_next, plain_hier)
- SLO/constraints satisfied
"""
    pre_md = f"""# Pre-Analysis — Phase {phase_index+1}

- Task: {task_id}
- Next Phase Index: {phase_index+1}
- Timestamp: {now}

## IMPORTANT NOTE (To satisfy)
{note_next}

## Plan
- 

## Risks & Rollback
- 
"""
    write_text(post, post_md)
    write_text(pre, pre_md)
    print(f"Wrote {post}")
    print(f"Wrote {pre}")


def mark_done(task_id: str, index: int) -> None:
    print(f"Marking phase {index} done via todo_manager.py …")
    subprocess.run([
        "python3", str(REPO_ROOT / "todo_manager.py"), "done", task_id, str(index)
    ], cwd=str(REPO_ROOT), check=True)


def show_plan() -> None:
    try:
        subprocess.run(["python3", str(REPO_ROOT / "plan_next.py")], cwd=str(REPO_ROOT), check=False)
    except Exception:
        pass


# ---------------------- Main ----------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Proceed active task by up to N phases")
    parser.add_argument("--task-id", dest="task_id", default=None)
    parser.add_argument("--max-loops", dest="max_loops", type=int, default=int(os.getenv("MAX_LOOPS", "5")))
    args = parser.parse_args()

    tasks = load_active_tasks()
    task = find_task(tasks, args.task_id)
    if not task:
        print("No active task found to proceed.")
        return

    print(f"Proceeding task: {task.id}")

    for i in range(args.max_loops):
        idx, td = first_unfinished(task.todos)
        if idx < 0 or td is None:
            print("No next phase. Stopping.")
            break
        print(f"\n=== Iteration {i+1} / {args.max_loops} for {task.id} ===")
        note_current = extract_important_note(td.get("text", ""))
        # next note if exists
        if idx + 1 < len(task.todos):
            note_next = extract_important_note(task.todos[idx+1].get("text", ""))
        else:
            note_next = "IMPORTANT NOTE: [NO NEXT PHASE — END OF PLAN]"
        write_docs(task.id, idx, note_current, note_next)
        # mark done
        mark_done(task.id, idx)
        # refresh active tasks in memory for next iteration
        tasks = load_active_tasks()
        task = find_task(tasks, task.id)
        if not task:
            print("Task no longer active. Stopping.")
            break
        show_plan()

    print(f"\nProceed completed for {task.id} or max loops reached.")


if __name__ == "__main__":
    main()