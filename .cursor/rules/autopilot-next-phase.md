-description: Execute the next unfinished phase with Phase Gates + required docs (post-review & pre-analysis)

This workflow advances the active task strictly following the rules in memory-bank/queue-system/tasks_active.json, Phase Gates, and Exec Policy.

Defaults
 - TASK_ID: auto-detected from memory-bank/queue-system/tasks_active.json
- Repo root: /home/haymayndz/MatalinongWorkflow

1) Ensure rules are enabled (send as chat message)
[cursor-rules:on]

// turbo
2) Validate plan (required gate)
```bash
python3 plan_next.py
```

// turbo
3) Show hierarchy (recommended gate)
```bash
TASK_ID=$(python3 - <<'PY'
import json
print(json.load(open('memory-bank/queue-system/tasks_active.json'))[0]['id'])
PY
)
python3 plain_hier.py "$TASK_ID"
```

// turbo
4) Capture NEXT phase index (k)
```bash
k=$(python3 plan_next.py | grep -m1 "Next phase index:" | sed -E 's/.*index: //') && echo "Next phase: $k"
```

5) Create post-review doc for phase k
```bash
TASK_ID=$(python3 - <<'PY'
import json
print(json.load(open('memory-bank/queue-system/tasks_active.json'))[0]['id'])
PY
)
k=$(python3 plan_next.py | grep -m1 "Next phase index:" | sed -E 's/.*index: //')
NOW=$(date +"%Y-%m-%dT%H:%M:%S%z")
post="memory-bank/DOCUMENTS/${TASK_ID}_phase${k}_postreview.md"
mkdir -p "$(dirname "$post")"
cat > "$post" << EOF
# Post-Review — Phase ${k}

- Task: ${TASK_ID}
- Phase Index: ${k}
- Timestamp: ${NOW}

## IMPORTANT NOTE (Restated)
- (Copy the phase’s IMPORTANT NOTE here and confirm how each constraint was satisfied.)

## What was done
- 

## Evidence / Outputs
- 

## Checks
- Plan gates passed (plan_next, plain_hier)
- SLO/constraints satisfied

EOF
echo "Wrote $post"
```

6) Create pre-analysis doc for phase k+1
```bash
TASK_ID=$(python3 - <<'PY'
import json
print(json.load(open('memory-bank/queue-system/tasks_active.json'))[0]['id'])
PY
)
k=$(python3 plan_next.py | grep -m1 "Next phase index:" | sed -E 's/.*index: //')
NEXT=$((k+1))
NOW=$(date +"%Y-%m-%dT%H:%M:%S%z")
pre="memory-bank/DOCUMENTS/${TASK_ID}_phase${NEXT}_preanalysis.md"
mkdir -p "$(dirname "$pre")"
cat > "$pre" << EOF
# Pre-Analysis — Phase ${NEXT}

- Task: ${TASK_ID}
- Next Phase Index: ${NEXT}
- Timestamp: ${NOW}

## IMPORTANT NOTE (To satisfy)
- (Paste the next phase’s IMPORTANT NOTE and list prerequisites/risks.)

## Plan
- 

## Risks & Rollback
- 

EOF
echo "Wrote $pre"
```

// turbo
7) Mark the phase done (monotonic completion only)
```bash
TASK_ID=$(python3 - <<'PY'
import json
print(json.load(open('memory-bank/queue-system/tasks_active.json'))[0]['id'])
PY
)
k=$(python3 plan_next.py | grep -m1 "Next phase index:" | sed -E 's/.*index: //')
python3 todo_manager.py done "$TASK_ID" "$k"
```

8) Verify status after
```bash
TASK_ID=$(python3 - <<'PY'
import json
print(json.load(open('memory-bank/queue-system/tasks_active.json'))[0]['id'])
PY
)
python3 plain_hier.py "$TASK_ID"
```

9) (Optional) Commit and push docs/state changes
```bash
set -euo pipefail
TASK_ID=$(python3 - <<'PY'
import json
print(json.load(open('memory-bank/queue-system/tasks_active.json'))[0]['id'])
PY
)
k=$(python3 plan_next.py | grep -m1 "Next phase index:" | sed -E 's/.*index: //')
GitTime=$(date +"%Y-%m-%dT%H:%M:%S%z")
git add -A
if ! git diff --staged --quiet; then
  git commit -m "chore(phase): docs for ${TASK_ID} phase ${k} [${GitTime}]"
  git pull --rebase origin master
  git push origin HEAD:master
else
  echo "No changes to commit."
fi
```

Notes
- Do not edit queue/state files directly; rely on todo_manager.py.
- Stop if any gate fails (missing IMPORTANT NOTE / non-monotonic completion).
- Repeat the workflow to advance subsequent phases.
