

Deep Analysis Integration Proposal and Action Plan

### 1) Proposal with Detailed Explanation

- **Central driver**: `.cursor/rules/deep_analysis.mdc` is the authoritative specification for the new Deep Analysis workflow. All rules and scripts must comply with its required output shape and gating semantics.

- **Strategy (mode-aware, dual SOT, hard gate)**:
  - Make core scripts mode-aware via `--mode execution|analysis` for read/list/show/done operations, while keeping `exec` tied to execution only.
  - Establish two sources of truth (SOTs):
    - **Execution SOT**: `memory-bank/queue-system/tasks_active.json` (existing)
    - **Analysis SOT**: `memory-bank/queue-system/analysis_active.json` (new)
  - Introduce a centralized, uniform "Deep Analysis Gate" enforced before any execution side-effect:
    - Gate checks for the execution task:
      - A matching analysis task exists in `analysis_active.json` with `source_task_id` equal to the execution task id.
      - All analysis todos are present and marked `done: true`.
      - Each analysis todo contains both "Decision Gate" and "IMPORTANT NOTE:" sections.
      - No analysis Findings entries with `Type: Conflict` or `Type: Duplicate`.
    - If any check fails, execution is blocked with a precise reason.

- **Why this approach**:
  - **Maintainability**: Minimal churn; reuse existing data structures and flows, adding a small mode switch and one gate function.
  - **Clarity**: Clean separation of analysis vs execution SOTs; explicit gate at the only places that cause side effects (`exec --run`, `done`).
  - **Extensibility**: Future analyzers/rules can enrich analysis todos or summaries without altering the gate contract.

- **Hard Gate definition (linking Analysis → Execution)**:
  - Execution remains locked until Analysis passes. Concretely, attempts to run `python3 todo_manager.py exec <TASK_ID> <K.N> --run` or `python3 todo_manager.py done <TASK_ID> <K>` must be preceded by an implicit/explicit gate pass.
  - Read-only previews are always allowed: `exec` without `--run` remains a safe dry-run.
  - Gate evaluates the analysis task linked by `source_task_id`, verifies structural sections and completion, and rejects if there are blocking Findings.

### 2) Step-by-Step Action Plan

#### A. Finalize SOTs and the Hard Gate

- **Paths**
  - **Execution SOT**: `memory-bank/queue-system/tasks_active.json`
  - **Analysis SOT**: `memory-bank/queue-system/analysis_active.json`

- **`analysis_active.json` schema (derived from deep_analysis.mdc)**
  - Top-level: array of analysis task objects
  - Task object fields:
    - `id`: string, recommended format `<original_execution_task_id>_analysis_<YYYYMMDD>`
    - `description`: string
    - `status`: `in_progress` | `done`
    - `created`: ISO8601 with `+08:00`
    - `updated`: ISO8601 with `+08:00`
    - `source_task_id`: string (execution task id this analysis mirrors)
    - `todos`: array of objects `{ text: string, done: boolean }`
      - Each `text` must contain the mirrored analysis content: Purpose, Scope, Checks, LOGIC PARITY CHECK, Decision Gate, Findings, IMPORTANT NOTE.
    - Optional: `findings_summary`: { `conflicts`: number, `duplicates`: number, `overlaps`: number, `notes`: string }

```json
[
  {
    "id": "mytask_actionable_20250811_analysis_20250812",
    "description": "Pre-execution analysis for My Task (derived from tasks_active.json).",
    "status": "in_progress",
    "created": "2025-08-12T10:00:00+08:00",
    "updated": "2025-08-12T10:00:00+08:00",
    "source_task_id": "mytask_actionable_20250811",
    "todos": [
      { "text": "PHASE 0: SETUP & PROTOCOL ANALYSIS (READ FIRST)\n...\nIMPORTANT NOTE: ...", "done": true },
      { "text": "PHASE 1: <Title> — ANALYSIS\n...\nFindings:\n- Concern: ...\n  Type: Overlap\n...\nIMPORTANT NOTE: ...", "done": true }
    ]
  }
]
```

- **Hard Gate function (to be used by scripts before execution)**

```python
from pathlib import Path
import json, re

def _analysis_file() -> Path:
    return Path.cwd() / "memory-bank" / "queue-system" / "analysis_active.json"

def _load_json_list(path: Path) -> list:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and "tasks" in data:
        data = data["tasks"]
    return data if isinstance(data, list) else []

def _find_analysis_for_task(execution_task_id: str) -> dict | None:
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
        re.search(r"Type:\s*Conflict", txt, re.I) is not None or
        re.search(r"Type:\s*Duplicate", txt, re.I) is not None
    )

def enforce_deep_analysis_gate(execution_task_id: str) -> tuple[bool, str]:
    analysis = _find_analysis_for_task(execution_task_id)
    if analysis is None:
        return False, "No analysis found in analysis_active.json for this execution task (missing source_task_id link)."
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
```

#### B. Required Script Modifications

- **`todo_manager.py`**
  - Add `--mode execution|analysis` to CRUD-like commands (`new`, `add`, `done`, `delete`, `list`, `show`, `hard_delete`, `cleanup`).
  - Select `DATA_FILE` by mode: `tasks_active.json` (execution) or `analysis_active.json` (analysis).
  - Enforce gate:
    - Before `exec --run`: call `enforce_deep_analysis_gate(<TASK_ID>)`; block if not PASS. Allow preview without gate.
    - Before `done` (execution mode): call the same gate; block if not PASS.

- **`plan_next.py`**
  - Add `--mode execution|analysis` to choose SOT.
  - Add `--gate --task-id <TASK_ID>` to evaluate and print gate status; exit non-zero on BLOCK.

- **`plain_hier.py`**
  - Add `--mode execution|analysis` for read-only hierarchy views of each SOT.

#### C. Required Rule Modifications (Compliance Analysis)

- **`.cursor/rules/exec_policy.mdc`**
  - Require gate pass before `exec --run` and before `done` (execution mode):
    - `python3 plan_next.py --gate --task-id <TASK_ID>` → must print PASS and exit 0.
  - Document new flags: `--mode`, `--gate`, `--task-id`.

- **`.cursor/rules/phase_gates.mdc`**
  - Add Gate 0 (Required): Deep Analysis Gate.
    - Run: `python3 plan_next.py --gate --task-id <TASK_ID>`
    - If BLOCK → stop; If PASS → continue to Gate 1/2.

- **`.cursor/rules/trigger_phrases.mdc`**
  - Add triggers for deep analysis mode and gate validation:
    - `[deep-analysis:only]`, "Deep analysis", "Validate deep analysis", "Check analysis gate <TASK_ID>".
  - Map gate check to the `plan_next.py --gate` command.

- **`.cursor/rules/analysis_tools.mdc`**
  - Document `plan_next.py --mode analysis`, `plain_hier.py --mode analysis`, and `plan_next.py --gate`.

- **`.cursor/rules/tasks_active_schema.mdc`**
  - Add a sibling schema section for `analysis_active.json` including `source_task_id` and the required analysis content sections.

- **`.cursor/rules/todo_manager_flow.mdc`**
  - Insert a Hard Gate step before `exec --run` and `done` in execution flow.

- (Optional) **`.cursor/rules/tool_usage_guarantee.mdc`** and **`.cursor/rules/done_enforcement.mdc`**
  - Note the Deep Analysis Gate as a prerequisite for execution.

#### D. Verification Strategy

1) With only execution plan present (no analysis or incomplete analysis):
```bash
python3 plan_next.py --gate --task-id MY_TASK_ID           # Expect: BLOCK
python3 todo_manager.py exec MY_TASK_ID 1.1 --run          # Expect: BLOCK with reason
python3 todo_manager.py done MY_TASK_ID 1                  # Expect: BLOCK with reason
```

2) After preparing `analysis_active.json` with a task whose `source_task_id` equals `MY_TASK_ID`, all analysis todos done, sections present, and no Conflict/Duplicate findings:
```bash
python3 plan_next.py --mode analysis                        # Shows analysis state (all done)
python3 plain_hier.py --mode analysis MY_TASK_ANALYSIS_ID   # Hierarchy preview
python3 plan_next.py --gate --task-id MY_TASK_ID            # PASS

# Execution now unlocked
python3 todo_manager.py exec MY_TASK_ID 1.1 --run           # Allowed
python3 todo_manager.py done MY_TASK_ID 1                   # Allowed
```

3) Negative checks covered by the gate (should BLOCK): missing `analysis_active.json`, no linked `source_task_id`, any analysis phase not done, missing "Decision Gate"/"IMPORTANT NOTE", or Findings contain `Type: Conflict`/`Type: Duplicate`.

---

Confidence: 92%