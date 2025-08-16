This workflow performs a smart DRY RUN over the active plan — validating gates and simulating progression from the next unfinished phase through the last phase — without writing docs, marking phases done, committing, or pushing. It stops on the first failure (missing IMPORTANT NOTE, structural error) or when MAX_LOOPS is reached.

Defaults
- TASK_ID: auto-detected from `memory-bank/queue-system/tasks_active.json`
- Repo root: /home/haymayndz/MatalinongWorkflow
- MAX_LOOPS: auto (remaining phases) — override by exporting env var MAX_LOOPS

1) Ensure rules are enabled (send as chat message)
[cursor-rules:on]

// turbo
2) DRY RUN all remaining phases (read-only, no writes)
```bash
set -euo pipefail

# Detect task id and load plan
TASK_ID=$(python3 - <<'PY'
import json,sys,os
p='memory-bank/queue-system/tasks_active.json'
assert os.path.exists(p), f'{p} not found'
data=json.load(open(p))
assert isinstance(data,list) and len(data)==1, 'tasks_active.json must contain exactly one task'
print(data[0]['id'])
PY
)

echo "[DRY-RUN] TASK_ID=$TASK_ID"

# Required gate (lint) to verify global integrity
PLAN_OUT=$(python3 plan_next.py | tee /tmp/plan_next.out)
echo "$PLAN_OUT" | grep -q "Lint: ok" || { echo "[DRY-RUN] ERROR: Lint failed. Stopping." >&2; exit 2; }

# Recommended gate: show hierarchy (read-only)
python3 plain_hier.py "$TASK_ID" || true

# Enumerate phases and simulate progression from first undone to last
python3 - <<'PY'
import json, sys, os, re

root='memory-bank/queue-system/tasks_active.json'
task=json.load(open(root))[0]
tid=task['id']
todos=task['todos']
n=len(todos)

# Find first not-done index (start phase)
start_idx=next((i for i,t in enumerate(todos) if not t.get('done', False)), n)
if start_idx>=n:
    print('[DRY-RUN] Plan complete; nothing to simulate.')
    sys.exit(0)

# Determine loop cap: remaining phases or MAX_LOOPS env override
remaining=n-start_idx
try:
    max_loops_env=os.environ.get('MAX_LOOPS')
    max_loops=int(max_loops_env) if max_loops_env else remaining
    if max_loops<=0: max_loops=remaining
except Exception:
    max_loops=remaining

end_idx=min(n-1, start_idx+max_loops-1)

print(f"[DRY-RUN] Simulating phases {start_idx}..{end_idx} of total {n}")

def require(cond,msg):
    if not cond:
        sys.stderr.write('[DRY-RUN] ERROR: '+msg+'\n')
        sys.exit(2)

for i in range(start_idx, end_idx+1):
    text=todos[i]['text']
    # Header must match PHASE i
    require(text.startswith(f'PHASE {i}:'), f'Phase header mismatch at index {i}')
    # IMPORTANT NOTE must exist
    pos=text.find('IMPORTANT NOTE:')
    require(pos>=0, f'IMPORTANT NOTE missing in phase {i}')
    # Concluding commands must reference correct TASK_ID and index
    require(f"python3 todo_manager.py show {tid}" in text, f'show command missing/mismatched in phase {i}')
    require(f"python3 todo_manager.py done {tid} {i}" in text, f'done command missing/mismatched in phase {i}')

    title=text.split('\n',1)[0].strip()
    print(f"\n=== [DRY-RUN] Phase {i}: {title} ===")
    print(f"[DRY-RUN] Would extract IMPORTANT NOTE for phase {i} to /tmp/{tid}_phase_{i}_important_note.txt")
    post=f"memory-bank/DOCUMENTS/{tid}_phase{i}_postreview.md"
    pre=f"memory-bank/DOCUMENTS/{tid}_phase{i+1}_preanalysis.md"
    print(f"[DRY-RUN] Would write: {post}")
    print(f"[DRY-RUN] Would write: {pre}")
    print(f"[DRY-RUN] Would run: python3 todo_manager.py done '{tid}' '{i}'")

print('\n[DRY-RUN] Completed successfully (no writes performed).')
PY
```

Notes
- Read-only: no file writes, no DONE actions, no commits/pushes.
- Stops on first failure with a precise error message to fix before a real run.
- To limit scope: export `MAX_LOOPS=2` to simulate only two phases from the next unfinished phase.

