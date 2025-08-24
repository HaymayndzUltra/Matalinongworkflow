# Task Queue System - Memory-Bank Organization

## Queue Files Location
All queue system files are now organized in `memory-bank/queue-system/`:

### Queue Files:
- **`tasks_queue.json`** - Waiting tasks (FIFO queue)
- **`tasks_active.json`** - Currently executing tasks (AI focus area)
- **`tasks_done.json`** - Completed tasks (archive)
- **`tasks_interrupted.json`** - Paused tasks (resume priority)

## AI Assistant Interface

### For Cursor/Cascade:
```python
# AI ONLY reads this file:
active_tasks = read_json("memory-bank/queue-system/tasks_active.json")

# AI workflow:
1. Read tasks_active.json
2. Execute tasks and mark TODOs as done
3. System automatically handles queue management
```

## Automatic Queue Management

### Background Engine:
- **File Path**: `task_queue_engine.py`
- **Real-time monitoring**: Watches `tasks_active.json` for changes
- **Automatic transitions**: Queue → Active → Done
- **Priority system**: Interrupted tasks get priority over queue

### Commands:
```bash
# Start queue engine
python3 queue_cli.py start --daemon

# Check status
python3 queue_cli.py status --detailed

# Add task to queue
python3 queue_cli.py add "Task description"

# Interrupt with urgent work
python3 queue_cli.py interrupt "Urgent task"
```

## Queue Flow Logic

### Normal Flow:
```
tasks_queue.json → tasks_active.json → tasks_done.json
```

### Interruption Flow:
```
tasks_active.json → tasks_interrupted.json
urgent_task → tasks_active.json
(when urgent done) → tasks_interrupted.json → tasks_active.json
```

## Migration Information

- **Old system**: Single `todo-tasks.json` with status fields
- **New system**: Separate files for each queue state
- **Migration date**: 2025-07-30
- **Backup location**: `backups/queue_migration_*`

## File Structure

```
memory-bank/
├── queue-system/
│   ├── tasks_queue.json      # Waiting tasks
│   ├── tasks_active.json     # ← AI READS THIS
│   ├── tasks_done.json       # Completed tasks
│   ├── tasks_interrupted.json # Paused tasks
│   └── README.md             # This file
├── cursor_state.json         # Cursor session state
├── task_state.json          # Current task execution state
└── task_interruption_state.json # Interruption management
```

## System Benefits

1. **AI Simplicity**: AI only needs to focus on `tasks_active.json`
2. **Automatic Management**: Queue transitions handled by background engine
3. **Real-time Response**: File watchers detect changes instantly
4. **Interruption Support**: Graceful pause/resume capability
5. **Clean Organization**: All files organized in memory-bank structure
