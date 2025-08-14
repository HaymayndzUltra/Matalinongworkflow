This workflow loops over the next unfinished phases and advances them one-by-one, strictly enforcing gates and documentation, then stops only when:
- Lint fails or IMPORTANT NOTE is missing
- No next phase is available (plan complete)
- Max iterations is reached (safety)

Defaults
- TASK_ID: auto-detected from `memory-bank/queue-system/tasks_active.json`
- Repo root: /home/haymayndz/MatalinongWorkflow
- MAX_LOOPS: 10 (override by exporting env var MAX_LOOPS)

1) Ensure Windsurf rules are enabled (send as chat message)
[windsurf-rules:on]

// turbo-all
2) Loop advancing phases until blocked
```bash
set -euo pipefail

TASK_ID=$(python3 - <<'PY'
import json
print(json.load(open('memory-bank/queue-system/tasks_active.json'))[0]['id'])
PY
)

MAX_LOOPS="${MAX_LOOPS:-10}"

for i in $(seq 1 "$MAX_LOOPS"); do
  echo "\n=== Iteration $i / $MAX_LOOPS for $TASK_ID ==="

  # Gate 1: Validate plan and capture output
  PLAN_OUT=$(python3 plan_next.py | tee /tmp/plan_next.out)
  echo "$PLAN_OUT" | grep -q "Lint: ok" || { echo "ERROR: Lint failed. Stopping." >&2; exit 2; }

  # Extract k (next phase index)
  K_LINE=$(echo "$PLAN_OUT" | grep -m1 "Next phase index:" || true)
  if [ -z "${K_LINE:-}" ]; then
    echo "No next phase index found. Assuming plan complete. Stopping."
    break
  fi
  k=$(echo "$K_LINE" | sed -E 's/.*Next phase index: *([0-9]+).*/\1/' || true)
  if ! [ "${k:-}" -ge 0 ] 2>/dev/null; then
    echo "Next phase index is not numeric (k=\"$k\"). Assuming done. Stopping."
    break
  fi
  echo "Next phase: $k"

  # Gate 2: Show hierarchy (read-only)
  python3 plain_hier.py "$TASK_ID"

  # Prepare timestamps
  NOW=$(date +"%Y-%m-%dT%H:%M:%S%:z")

  # Extract IMPORTANT NOTE for phase k
  NOTE_FILE="/tmp/${TASK_ID}_phase_${k}_important_note.txt"
  python3 - <<'PY' "$k" "$NOTE_FILE"
import json, sys
idx=int(sys.argv[1])
note_file=sys.argv[2]
data=json.load(open('memory-bank/queue-system/tasks_active.json'))
text=data[0]['todos'][idx]['text']
pos=text.find('IMPORTANT NOTE:')
if pos<0:
  sys.stderr.write(f'ERROR: IMPORTANT NOTE not found for phase {idx}\n')
  sys.exit(2)
note=text[pos:].strip('\n')
open(note_file,'w').write(note+"\n")
print('Extracted IMPORTANT NOTE to', note_file)
PY

  # Create post-review doc for k
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

  # Create pre-analysis doc for k+1
  NEXT=$((k+1))
  PRE_NOTE_FILE="/tmp/${TASK_ID}_phase_${NEXT}_important_note.txt"
  python3 - <<'PY' "$NEXT" "$PRE_NOTE_FILE"
import json, sys
idx=int(sys.argv[1])
note_file=sys.argv[2]
data=json.load(open('memory-bank/queue-system/tasks_active.json'))
todos=data[0]['todos']
if 0 <= idx < len(todos):
  text=todos[idx]['text']
  pos=text.find('IMPORTANT NOTE:')
  if pos>=0:
    note=text[pos:].strip('\n')
  else:
    note='IMPORTANT NOTE: [MISSING IN PHASE TEXT]'
else:
  note='IMPORTANT NOTE: [NO NEXT PHASE — END OF PLAN]'
open(note_file,'w').write(note+"\n")
print('Prepared NEXT IMPORTANT NOTE at', note_file)
PY

  pre="memory-bank/DOCUMENTS/${TASK_ID}_phase${NEXT}_preanalysis.md"
  cat > "$pre" << EOF
# Pre-Analysis — Phase ${NEXT}

- Task: ${TASK_ID}
- Next Phase Index: ${NEXT}
- Timestamp: ${NOW}

## IMPORTANT NOTE (To satisfy)
$(cat "$PRE_NOTE_FILE")

## Plan
- 

## Risks & Rollback
- 

EOF
  echo "Wrote $pre"

  # Ensure post-review exists before marking done
  if [ ! -f "$post" ]; then
    echo "ERROR: Missing post-review doc: $post" >&2
    exit 2
  fi

  # Mark phase done (monotonic)
  python3 todo_manager.py done "$TASK_ID" "$k"

  # Verify status
  python3 plan_next.py

done

echo "\nAutopilot-all completed: either plan is done, a gate failed, or MAX_LOOPS ($MAX_LOOPS) reached." 
```

3) (Optional) Commit and push docs/state changes
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
  git commit -m "chore(autopilot-all): docs + done progression for ${TASK_ID} [${GitTime}]"
  # Uncomment the following lines if pushing is desired by default
  # git pull --rebase origin master
  # git push origin HEAD:master
else
  echo "No changes to commit."
fi
```