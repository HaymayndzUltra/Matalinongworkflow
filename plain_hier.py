#!/usr/bin/env python3
"""Read-only hierarchical plan viewer (environment-independent path auto-detection)."""
import json, sys, re, os, subprocess, argparse
from pathlib import Path

def _find_root_with_tasks(start: Path):
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
    # 4) Fallback to cwd
    return cwd

REPO_ROOT = _detect_repo_root()
ACTIVE = REPO_ROOT / "memory-bank" / "queue-system" / "tasks_active.json"

def blocks(md: str):
    return re.findall(r"```(?:[\w+-]+)?\n([\s\S]*?)\n```", md or "", re.M)

def head(line: str) -> str:
    return (line or "").strip().splitlines()[0] if line else ""

def main():
    ap = argparse.ArgumentParser(description="Plain hierarchy viewer")
    ap.add_argument("task_id")
    ap.add_argument("--mode", choices=["execution","analysis"], default="execution")
    args = ap.parse_args()

    global ACTIVE
    ACTIVE = REPO_ROOT / "memory-bank" / "queue-system" / ("analysis_active.json" if args.mode=="analysis" else "tasks_active.json")
    task_id = args.task_id
    data = json.loads(ACTIVE.read_text(encoding="utf-8"))
    if isinstance(data, dict) and "tasks" in data:
        data = data["tasks"]
    task = next((t for t in data if t.get("id")==task_id), None)
    if not task:
        print(f"❌ Task not found: {task_id}"); sys.exit(2)

    todos = task.get("todos", [])
    done_count = sum(1 for td in todos if td.get("done"))
    print(f"🗒️ {task_id} — {done_count}/{len(todos)} done")
    for i, td in enumerate(todos):
        mark = "✔" if td.get("done") else "✗"
        title = head(td.get("text",""))
        print(f"  [{mark}] {i}. {title}")
        note_idx = td.get("text","").find("IMPORTANT NOTE:")
        if note_idx >= 0:
            snippet = td["text"][note_idx:note_idx+220].replace("\n"," ")
            print(f"     NOTE: {snippet}{'…' if len(td['text'])-note_idx>220 else ''}")
        code = blocks(td.get("text",""))
        if code:
            prev = "\n".join(code[0].splitlines()[:4])
            print("     cmds:")
            for ln in prev.splitlines():
                print(f"       {ln}")
    print("✅ read-only view complete")

if __name__ == "__main__":
    main()
