Step 1 — Establish canonical memory domains
- Execution SOT: keep `memory-bank/queue-system/*.json` as-is.
- Context SOT: make `memory-bank/cursor_state.json` canonical; mirror to root `cursor_state.json` (compat only).
- Human-readable: single writer for `memory-bank/current-session.md` via `cursor_memory_bridge.dump_markdown()`; others call this instead of writing.

Step 2 — Add structured run/decision logging (SQLite, WAL)
- Create `memory-bank/memory/state.sqlite` with tables `runs`, `decisions`, `context`; enable WAL.
- Add `memory_store.py` CLI: `init`, `log-run`, `log-decision`, `set-context`.

Step 3 — Hook execution logging into todo runner
- In `todo_manager.exec_substep`:
  - Before run: compute stdout/stderr paths under `memory-bank/logs/`; record start time.
  - After each command: capture exit code; call `memory_store.py log-run` with: task_id, phase_index, sub_index, command, status, exit_code, stdout_path, stderr_path, started_at, ended_at.

Step 4 — Eliminate competing writers for `current-session.md`
- Modify `auto_sync_manager._update_current_session` to call `cursor_memory_bridge.dump_markdown()` (no direct writes).
- Keep `memory_system/cli.py save` append-only under a stable “Memory Note” header.

Step 5 — Atomic writes + file locking for JSON SOT
- Replace direct `write_text` with temp file + `os.replace` in `todo_manager._save()`.
- Wrap reads/writes of `tasks_active.json` (and any mutated `analysis_active.json`) with advisory `fcntl` lock.

Step 6 — Timezone normalization (PH +08:00)
- Emit ISO timestamps with `+08:00` everywhere; update `cursor_session_manager` to PH TZ; verify `todo_manager`/`auto_sync_manager` alignment.

Step 7 — Cursor state unification
- Point `cursor_session_manager.DEFAULT_STATE_FILE` to `memory-bank/cursor_state.json`.
- Mirror to root `cursor_state.json` only if root file exists.
- Gate `auto_sync_manager` from writing cursor state if session manager is active (or only fill when missing).

Step 8 — Retention policy safety
- Change `_cleanup_outdated_tasks()` to archive completed tasks into `memory-bank/queue-system/tasks_done.json` (not purge); add size/time rotation.

Step 9 — MCP config hygiene
- Replace embedded secrets in `mcp_memory.json` with env placeholders; remove secrets from VCS.
- Provide a valid `memory.json` (or symlink) for MCP clients; keep `setup_memory_mcp.py` fallback generator.

Step 10 — Tests and validation
- Concurrency: simulate parallel `todo_manager` writes; assert JSON not truncated, schema intact.
- Logging: run `exec_substep --run` on a benign command; assert `runs` row and stdout/stderr files exist.
- Session writer: multiple imports should not clobber `current-session.md`; only the bridge writes.

Step 11 — Observability (optional)
- Generate daily summaries from `runs` into `memory-bank/reports/` (top commands, failures, durations).

Step 12 — Documentation
- Ownership:
  - `cursor_memory_bridge`: sole writer of `current-session.md`
  - `memory_store.py`: runs/decisions/context (SQLite)
  - `todo_manager.py`: atomic task JSON writes + run logging hook
  - `auto_sync_manager`: JSON state sync only (no direct MD writes)