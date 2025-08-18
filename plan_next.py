#!/usr/bin/env python3
"""Plan next-phase helper (environment-independent path auto-detection)."""
import json, re, sys, os, subprocess, argparse
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

def _find_root_with_tasks(start: Path) -> Optional[Path]:
    """Walk upwards from 'start' to locate a directory containing the plan file."""
    cur = start.resolve()
    while True:
        if (cur / "memory-bank" / "queue-system" / "tasks_active.json").exists():
            return cur
        if cur.parent == cur:
            break
        cur = cur.parent
    return None

def _detect_repo_root() -> Path:
    cwd = Path.cwd()
    # 1) Search upwards from current working directory
    root = _find_root_with_tasks(cwd)
    if root:
        return root
    # 2) Search upwards from this script's directory
    here = Path(__file__).resolve().parent
    root = _find_root_with_tasks(here)
    if root:
        return root
    # 3) Try git repository top-level
    try:
        top = subprocess.check_output([
            "git", "rev-parse", "--show-toplevel"
        ], stderr=subprocess.DEVNULL).decode().strip()
        root = _find_root_with_tasks(Path(top))
        if root:
            return root
    except Exception:
        pass
    # 4) Fallback to cwd (may error later if file truly absent)
    return cwd

REPO_ROOT = _detect_repo_root()
ACTIVE = REPO_ROOT / "memory-bank" / "queue-system" / "tasks_active.json"

def load_tasks() -> List[Dict[str, Any]]:
    if not ACTIVE.exists():
        print("❌ tasks_active.json not found"); sys.exit(2)
    data = json.loads(ACTIVE.read_text(encoding="utf-8"))
    if isinstance(data, dict) and "tasks" in data:
        data = data["tasks"]
    if not isinstance(data, list):
        print("❌ tasks_active.json must be a list of task objects"); sys.exit(2)
    return data

def first_unfinished(todos: List[Dict[str, Any]]) -> Tuple[int, Optional[Dict[str, Any]]]:
    for i, t in enumerate(todos):
        if not bool(t.get("done", False)):
            return i, t
    return -1, None

def title_line(markdown: str) -> str:
    return (markdown or "").strip().splitlines()[0] if markdown else ""

def extract_important_note(markdown: str) -> str:
    if not markdown: return ""
    idx = markdown.find("IMPORTANT NOTE:")
    return markdown[idx:].strip() if idx >= 0 else ""

def extract_code_blocks(markdown: str) -> List[str]:
    if not markdown: return []
    # capture fenced code blocks; language tag optional
    p = re.compile(r"```(?:[a-zA-Z0-9_+-]+)?\n([\s\S]*?)\n```", re.MULTILINE)
    return [m.group(1).strip() for m in p.finditer(markdown)]

def lint_plan(task: Dict[str, Any]) -> Dict[str, Any]:
    todos = task.get("todos", [])
    issues = []
    # Phase 0 position
    if todos:
        if not title_line(todos[0].get("text","")).startswith("PHASE 0: SETUP & PROTOCOL"):
            issues.append("Phase 0 is not first")
    # IMPORTANT NOTE presence
    missing_note = [i for i, td in enumerate(todos) if "IMPORTANT NOTE:" not in td.get("text","")]
    # Monotonicity: once a done=True appears, no later done=False
    seen_done, mono_ok = False, True
    for td in todos:
        d = bool(td.get("done", False))
        if d and not seen_done: seen_done = True
        if not d and seen_done: mono_ok = False; break
    if not mono_ok: issues.append("Completion is non-monotonic (undone after done)")
    return {"issues": issues, "missing_important_note_indices": missing_note}

def main():
    parser = argparse.ArgumentParser(description="Next-phase analyzer")
    parser.add_argument("--mode", choices=["execution","analysis"], default="execution")
    parser.add_argument("--gate", action="store_true", help="Check Deep Analysis Gate for a task and exit 0/3")
    parser.add_argument("--task-id", help="Execution task id for --gate")
    args = parser.parse_args()

    global ACTIVE
    ACTIVE = REPO_ROOT / "memory-bank" / "queue-system" / ("analysis_active.json" if args.mode=="analysis" else "tasks_active.json")

    if args.gate:
        if not args.task_id:
            print("❌ --gate requires --task-id"); sys.exit(2)
        try:
            from todo_manager import enforce_deep_analysis_gate  # type: ignore
        except Exception as e:
            print(f"❌ Cannot import gate: {e}"); sys.exit(2)
        ok, msg = enforce_deep_analysis_gate(args.task_id)
        print(f"DEEP ANALYSIS: {'PASS' if ok else 'BLOCK'} — {msg}")
        sys.exit(0 if ok else 3)

    tasks = load_tasks()
    if not tasks: print("ℹ️ No active tasks."); return
    for t in tasks:
        task_id = t.get("id","")
        todos = t.get("todos", [])
        idx, todo = first_unfinished(todos)
        print(f"\n🗒️ PLAN: {task_id}")
        print(f"   Progress: {sum(1 for x in todos if x.get('done'))} / {len(todos)}")
        if todo is None:
            print("   ✅ All phases complete.")
        else:
            txt = todo.get("text","")
            print(f"   Next phase index: {idx}")
            print(f"   Title: {title_line(txt)}")
            note = extract_important_note(txt)
            print(f"   IMPORTANT NOTE: {(note[:300] + '…') if len(note) > 300 else (note or '(missing)')}")
            blocks = extract_code_blocks(txt)
            if blocks:
                preview = "\n".join(blocks[0].splitlines()[:12])
                print("   Extracted commands/code (preview):")
                print("   ---")
                for line in preview.splitlines():
                    print(f"   {line}")
                print("   ---")
            else:
                print("   No fenced commands/code found in this phase.")
        rep = lint_plan(t)
        if rep["issues"] or rep["missing_important_note_indices"]:
            print(f"   Lint: {', '.join(rep['issues']) or 'ok'}")
            if rep["missing_important_note_indices"]:
                print(f"   Missing IMPORTANT NOTE in phases: {rep['missing_important_note_indices']}")
        else:
            print("   Lint: ok")
    print("\n✅ Read-only analysis complete.")

if __name__ == "__main__":
    main()
