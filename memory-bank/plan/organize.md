Non-Destructive Flow Test — Two Phases (Portable, Read-Only)
Version: v1.0
Status: Frozen (for ingestion in a separate session)
Phase 1 — Environment & Path Sanity
Explanations:
Quick, safe checks for shell, time, Python, and working directory.
Command Preview:

pwd
date '+%Y-%m-%d %H:%M:%S'
python3 -c "import sys,os; print('PY:',sys.version.split()[0],' CWD:',os.getcwd())"
ls -la | head -n 20

Phase 2 — Read-only Inspection & No-op Simulation
Explanations:
Tolerant, read-only peeks plus a short no-op sequence.
Command Preview:

test -f README.md && head -n 20 README.md || echo "SKIP_HEAD_README"
ps -eo pid,comm --no-headers 2>/dev/null | head -n 5 || echo "SKIP_PS"
git rev-parse --show-toplevel 2>/dev/null || echo "NO_GIT_REPO"
echo "SIM_STEP_1"; sleep 1; echo "SIM_STEP_2"; true

End-of-Task Reporting Instruction (Do this in the executing session)
After completing the two phases, produce a “Command Rules Mapping” report that:
Lists ALL user-provided command rules.
For EACH rule, shows:
Trigger: the exact phrase/token that activated the AI.
Runs: the exact command(s) the AI executed in response (verbatim).