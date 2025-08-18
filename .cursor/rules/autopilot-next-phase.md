---
description: Execute the next unfinished phase with Phase Gates + required docs (post-review & pre-analysis)
---

> OPERATOR-ONLY PLAYBOOK (outside agent exec-policy). Contains VCS operations (git add/commit/pull/push). Agents must not execute these; use `auto_phase_runner.mdc` + `exec_policy.mdc` instead.

This workflow advances the active task strictly following the rules in memory-bank/queue-system/tasks_active.json, Phase Gates, and Exec Policy.

Defaults
 - task_id Replace All: auto-detected from memory-bank/queue-system/tasks_active.json
- Repo root: /home/haymayndz/MatalinongWorkflow

1) Ensure rules are enabled (send as chat message)
[cursor-rules:on]

// turbo
2) Validate plan (required gate)
```bash
set -euo pipefail
python3 plan_next.py | tee /tmp/plan_next.out
grep -q "Lint: ok" /tmp/plan_next.out
```

// turbo
3) Show hierarchy (recommended gate)
```bash
set -euo pipefail
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
set -euo pipefail
k=$(python3 plan_next.py | grep -m1 "Next phase index:" | sed -E 's/.*index: //') && echo "Next phase: $k"
```

5) Create post-review doc for phase k
```bash
set -euo pipefail
TASK_ID=$(python3 - <<'PY'
import json
print(json.load(open('memory-bank/queue-system/tasks_active.json'))[0]['id'])
PY
)
k=$(python3 plan_next.py | grep -m1 "Next phase index:" | sed -E 's/.*index: //')
NOW=$(date +"%Y-%m-%dT%H:%M:%S%:z")

# Extract IMPORTANT NOTE for phase k from tasks_active.json into a temp file
NOTE_FILE="/tmp/${TASK_ID}_phase_${k}_important_note.txt"
python3 - <<'PY'
import json, sys, re
data=json.load(open('memory-bank/queue-system/tasks_active.json'))
task=data[0]
todos=task['todos']
idx=int(sys.argv[1])
text=todos[idx]['text']
pos=text.find('IMPORTANT NOTE:')
if pos<0:
  sys.stderr.write('ERROR: IMPORTANT NOTE not found for phase %d\n' % idx)
  sys.exit(2)
note=text[pos:].strip('\n')
open(sys.argv[2],'w').write(note+"\n")
print('Extracted IMPORTANT NOTE to', sys.argv[2])
PY
"$k" "$NOTE_FILE"

post="memory-bank/DOCUMENTS/${TASK_ID}_phase${k}_postreview.md"
mkdir -p "$(dirname "$post")"
cat > "$post" << EOF
# Post-Review — Phase ${k}

- Task: ${TASK_ID}
- Phase Index: ${k}
- Timestamp: ${NOW}

## IMPORTANT NOTE (Restated)
$(cat "$NOTE_FILE")

### How constraints were satisfied
- [ ] Describe evidence per constraint

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
set -euo pipefail
TASK_ID=$(python3 - <<'PY'
import json
print(json.load(open('memory-bank/queue-system/tasks_active.json'))[0]['id'])
PY
)
k=$(python3 plan_next.py | grep -m1 "Next phase index:" | sed -E 's/.*index: //')
NEXT=$((k+1))
NOW=$(date +"%Y-%m-%dT%H:%M:%S%:z")
pre="memory-bank/DOCUMENTS/${TASK_ID}_phase${NEXT}_preanalysis.md"
mkdir -p "$(dirname "$pre")"

# Try to extract IMPORTANT NOTE of next phase if it exists
NEXT_NOTE_FILE="/tmp/${TASK_ID}_phase_${NEXT}_important_note.txt"
python3 - <<'PY'
import json, sys
data=json.load(open('memory-bank/queue-system/tasks_active.json'))
task=data[0]
todos=task['todos']
idx=int(sys.argv[1])
if 0 <= idx < len(todos):
  text=todos[idx]['text']
  pos=text.find('IMPORTANT NOTE:')
  if pos>=0:
    note=text[pos:].strip('\n')
  else:
    note='IMPORTANT NOTE: [MISSING IN PHASE TEXT]'
else:
  note='IMPORTANT NOTE: [NO NEXT PHASE — END OF PLAN]'
open(sys.argv[2],'w').write(note+"\n")
print('Prepared NEXT IMPORTANT NOTE at', sys.argv[2])
PY
"$NEXT" "$NEXT_NOTE_FILE"

cat > "$pre" << EOF
# Pre-Analysis — Phase ${NEXT}

- Task: ${TASK_ID}
- Next Phase Index: ${NEXT}
- Timestamp: ${NOW}

## IMPORTANT NOTE (To satisfy)
$(cat "$NEXT_NOTE_FILE")

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
set -euo pipefail
TASK_ID=$(python3 - <<'PY'
import json
print(json.load(open('memory-bank/queue-system/tasks_active.json'))[0]['id'])
PY
)
k=$(python3 plan_next.py | grep -m1 "Next phase index:" | sed -E 's/.*index: //')
# Ensure docs exist before marking done
post="memory-bank/DOCUMENTS/${TASK_ID}_phase${k}_postreview.md"
if [ ! -f "$post" ]; then
  echo "ERROR: Missing post-review doc: $post" >&2
  exit 2
fi
python3 todo_manager.py done "$TASK_ID" "$k"
```

8) Verify status after
```bash
set -euo pipefail
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
GitTime=$(date +"%Y-%m-%dT%H:%M:%S%:z")
git add -A
if ! git diff --staged --quiet; then
  git commit -m "chore(phase): postreview+preanalysis docs for ${TASK_ID} [${GitTime}]"
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
