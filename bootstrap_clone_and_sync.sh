#!/usr/bin/env bash
# push_minimal_todo_bundle.sh
# Creates/pushes branch 'minimal-todo-bundle' with ONLY the specific files + exact rules.
# Requirements: /workspace has the source files; /workspace/token.md has a valid PAT on line 1.

set -euo pipefail

REPO_URL="https://github.com/HaymayndzUltra/MatalinongWorkflow.git"
DEST_DIR="/workspace/MatalinongWorkflow"
SRC="/workspace"

# 1) Read token (won't print)
GITHUB_TOKEN="$(sed -n '1p' /workspace/token.md)"
if [[ -z "${GITHUB_TOKEN:-}" ]]; then echo "❌ Missing token in /workspace/token.md"; exit 2; fi

# 2) Clone or update
if [[ -d "$DEST_DIR/.git" ]]; then
  git -C "$DEST_DIR" fetch --all || true
else
  git clone "$REPO_URL" "$DEST_DIR"
fi

cd "$DEST_DIR"

# 3) Recreate orphan branch cleanly
git checkout --orphan minimal-todo-bundle || true
# wipe working tree except .git
find . -mindepth 1 -maxdepth 1 ! -name .git -exec rm -rf {} +

copy() {
  local rel="$1"; local src="$SRC/$rel"; local dst="$DEST_DIR/$rel";
  if [[ -f "$src" ]]; then mkdir -p "$(dirname "$dst")"; cp -f "$src" "$dst";
  elif [[ -d "$src" ]]; then mkdir -p "$dst"; cp -a "$src/." "$dst/";
  else echo "⚠ missing: $rel"; fi
}

# 4) Copy EXACT minimal bundle
# Core modules
copy "todo_manager.py"
copy "task_interruption_manager.py"
copy "task_state_manager.py"
copy "cursor_memory_bridge.py"
copy "cursor_session_manager.py"
copy "auto_sync_manager.py"

# Logging dep
copy "common/__init__.py"
copy "common/utils/__init__.py"
copy "common/utils/log_setup.py"

# Namespace adapters
copy "memory_system/services/__init__.py"
copy "memory_system/services/todo_manager.py"
copy "memory_system/services/task_interruption_manager.py"

# Read-only analyzers
copy "plan_next.py"
copy "plain_hier.py"

# EXACT rules
copy ".cursor/rules/agent_plan_ingestion.mdc"
copy ".cursor/rules/analysis_tools.mdc"
copy ".cursor/rules/cursorrules.mdc"
copy ".cursor/rules/exec_policy.mdc"
copy ".cursor/rules/expertcursor.mdc"
copy ".cursor/rules/imporant_note_enforcement.mdc"
copy ".cursor/rules/phase_gates.mdc"
copy ".cursor/rules/rules.mdc"
copy ".cursor/rules/tasks_active_schema.mdc"
copy ".cursor/rules/todo-list-format.mdc"
copy ".cursor/rules/todo_manager_flow.mdc"
copy ".cursor/rules/trigger_phrases.mdc"
copy "main_pc_code/.cursor/rules/important.md"

# memory-bank skeleton
mkdir -p "$DEST_DIR/memory-bank/queue-system"
if [[ -f "$SRC/memory-bank/queue-system/tasks_active.json" ]]; then
  copy "memory-bank/queue-system/tasks_active.json"
else
  printf "[]\n" > "$DEST_DIR/memory-bank/queue-system/tasks_active.json"
fi
printf "# 📝 Current Cursor Session — (empty)\n" > "$DEST_DIR/memory-bank/current-session.md"
printf "{}\n" > "$DEST_DIR/memory-bank/cursor_state.json"
printf "{}\n" > "$DEST_DIR/memory-bank/task_state.json"
printf "{}\n" > "$DEST_DIR/memory-bank/task_interruption_state.json"

# .gitignore
cat > .gitignore <<EOF
__pycache__/
*.pyc
.env
.venv
EOF

git add -A
git commit -m "minimal todo_manager bundle + exact rules + memory-bank skeleton" || true

# 5) Push using token via header (no token printed)
BASIC="$(printf "x-access-token:%s" "$GITHUB_TOKEN" | base64 | tr -d '\n')"
git -c http.extraheader="Authorization: Basic $BASIC" push -u origin minimal-todo-bundle
echo "✅ Pushed: minimal-todo-bundle"