#!/usr/bin/env python3
"""
Promote the next queued task into active tasks and normalize its TODOs.

Normalization steps:
- Insert PHASE 0: SETUP & PROTOCOL (READ FIRST) stub at the beginning
- Ensure each TODO contains an 'IMPORTANT NOTE:' section
- Convert leading 'STAGE ' to 'PHASE '
- Append a concluding step code block with todo_manager commands if missing
- Set status to in_progress and update timestamps (UTC+8)

This helps the read-only gates and linter pass on first run.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List


def detect_repo_root() -> Path:
	cwd = Path.cwd()
	candidate = cwd / "memory-bank" / "queue-system" / "tasks_active.json"
	if candidate.exists():
		return cwd
	# Fallbacks (align with plan_next.py)
	for env_name in ("VOICE_ASSISTANT_PROD_ROOT", "AI_SYSTEM_MONOREPO"):
		env_val = os.getenv(env_name)
		if env_val:
			root = Path(env_val)
			if (root / "memory-bank" / "queue-system" / "tasks_active.json").exists():
				return root
	default_root = Path("/home/haymayndz/MatalinongWorkflow")
	if (default_root / "memory-bank" / "queue-system" / "tasks_active.json").exists():
		return default_root
	return cwd


# Avoid importing os at top just to keep a tight namespace
import os  # noqa: E402  (import after function definition intentionally)

REPO_ROOT = Path("/workspace") if (Path("/workspace") / "memory-bank" / "queue-system" / "tasks_active.json").exists() else detect_repo_root()
QUEUE_DIR = REPO_ROOT / "memory-bank" / "queue-system"
ACTIVE_PATH = QUEUE_DIR / "tasks_active.json"
QUEUE_PATH = QUEUE_DIR / "tasks_queue.json"


def read_json(path: Path) -> Any:
	if not path.exists():
		return []
	return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
	path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def now_ph_iso() -> str:
	ph_tz = timezone(timedelta(hours=8))
	return datetime.utcnow().astimezone(ph_tz).isoformat()


def ensure_concluding_block(text: str, task_id_placeholder: str, index: int) -> str:
	if "Concluding Step: Phase Completion Protocol" in text:
		return text
	block = (
		"\n\n**Concluding Step: Phase Completion Protocol**\n" \
		"```\n" \
		f"python3 todo_manager.py show <TASK_ID>\n" \
		f"python3 todo_manager.py done <TASK_ID> {index}\n" \
		"```\n"
	)
	return text.rstrip() + "\n\n" + block


def normalize_todo_text(raw: str, index: int) -> str:
	text = raw or ""
	# Convert leading STAGE -> PHASE (only if it appears at the start)
	text = re.sub(r"^STAGE\\s+", "PHASE ", text, count=1, flags=re.IGNORECASE)
	# Ensure IMPORTANT NOTE presence (convert local-language tag if present)
	if "IMPORTANT NOTE:" not in text:
		text = text.replace("MAHALAGANG PAALALA:", "IMPORTANT NOTE:")
		if "IMPORTANT NOTE:" not in text:
			text = text.rstrip() + "\n\nIMPORTANT NOTE: [FILL IN] Provide constraints, SLOs, and validation evidence."
	# Ensure concluding block
	text = ensure_concluding_block(text, "<TASK_ID>", index)
	return text


def make_phase0_stub() -> Dict[str, Any]:
	stub = (
		"PHASE 0: SETUP & PROTOCOL (READ FIRST)\n\n"
		"**Explanations:**\n"
		"- This queued task was promoted and normalized to the standard phase format.\n"
		"- Protocol: Use only the todo_manager CLI for state changes; redact PII; use +08:00 timestamps; reproducible runs.\n\n"
		"**Concluding Step: Phase Completion Protocol**\n"
		"```\n"
		"python3 todo_manager.py show <TASK_ID>\n"
		"python3 todo_manager.py done <TASK_ID> 0\n"
		"```\n\n"
		"IMPORTANT NOTE: Ensure linter passes (Phase 0 first, IMPORTANT NOTE present, monotonic completion)."
	)
	return {"text": stub, "done": False}


def transform_task_for_active(task: Dict[str, Any]) -> Dict[str, Any]:
	new_task = dict(task)  # shallow copy
	new_todos: List[Dict[str, Any]] = []
	# Phase 0 first
	new_todos.append(make_phase0_stub())
	# Normalize existing todos as PHASE 1..N
	for idx, todo in enumerate(task.get("todos", []), start=1):
		nt: Dict[str, Any] = {
			"text": normalize_todo_text(str(todo.get("text", "")), idx),
			"done": bool(todo.get("done", False)),
		}
		new_todos.append(nt)
	new_task["todos"] = new_todos
	new_task["status"] = "in_progress"
	new_task["updated"] = now_ph_iso()
	return new_task


def promote_first_in_queue() -> None:
	queue = read_json(QUEUE_PATH)
	active = read_json(ACTIVE_PATH)
	if isinstance(active, dict) and "tasks" in active:
		active = active["tasks"]
	if not isinstance(active, list):
		active = []
	if not queue:
		print("No queued tasks to promote.")
		return
	# Pop first (FIFO)
	task: Dict[str, Any] = queue.pop(0)
	# Transform
	promoted = transform_task_for_active(task)
	# Append to active
	active.append(promoted)
	# Persist
	write_json(ACTIVE_PATH, active)
	write_json(QUEUE_PATH, queue)
	print(f"✅ Promoted task to active: {promoted.get('id', '<unknown>')}")
	print(f"   Active file: {ACTIVE_PATH}")
	print(f"   Remaining in queue: {len(queue)}")


if __name__ == "__main__":
	promote_first_in_queue()