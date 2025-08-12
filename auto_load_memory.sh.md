#!/bin/bash
echo "🧠 Auto-loading memory context for new session..."
echo "🧠 Auto-loading memory context for new session... (quiet)"

Load memory-bank files
echo "📖 Loading memory-bank files:"
count=$(ls memory-bank/.md 2>/dev/null | wc -l | tr -d ' ')
echo "  ✅ $count markdown documents loaded"

Check MCP services
echo "🔗 Checking MCP services:"
if source .env 2>/dev/null &&  ! -z "$MEMORY_API_KEY" ; then
    echo "  ✅ Environment variables loaded"
    if curl -s --connect-timeout 3 "https://memory-mcp.hpkv.io/health" > /dev/null; then
        echo "  ✅ MCP Memory Service: Online"
    else
        echo "  ⚠️  MCP Memory Service: Connection timeout"
    fi
else
    echo "  ❌ Environment variables not loaded"
fi
if source .env 2>/dev/null &&  ! -z "$MEMORY_API_KEY" ; then :; fi

Check local memory system  
echo "🖥️  Local Memory System:"
if pgrep -f "memory_orchestrator" > /dev/null; then
    echo "  ✅ MemoryOrchestratorService: Running"
else
    echo "  ⚠️  MemoryOrchestratorService: Not detected"
fi
if pgrep -f "memory_orchestrator" > /dev/null; then :; fi

Show last Cursor session state (if available)
echo "📝 Last Cursor Session State:"
python3 cursor_session_manager.py --summary 2>/dev/null || echo "  ℹ️  No session summary available"
python3 cursor_session_manager.py --summary 1>/dev/null 2>&1 || true

Show count of open tasks (todo_manager)
echo "📋 Open Tasks:"
python3 - <<'PY' 2>/dev/null
python3 - <<'PY' 1>/dev/null 2>&1
import json, pathlib, os
fp = pathlib.Path(os.getcwd()) / 'todo-tasks.json'
if fp.exists():
@@ -44,10 +25,4 @@ else:
   print("📋 Open Tasks: 0 (no todo-tasks.json)")
PY

echo "🚀 Memory loading complete!"
echo ""
echo "💡 To get started:"
echo "   - Use standard memory functions for conversation context"
echo "   - Memory-bank files contain project documentation"
echo "   - MCP Memory service is configured and ready"
echo ""