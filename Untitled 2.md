---

description: TASK , MEMORY , NEW SESSION

alwaysApply: true

---

## **⚡ TASK EXECUTION PROTOCOL**

  

- **AI ASSISTANT SCOPE (CRITICAL)**:

    - **ONLY WORK WITH**: `memory-bank/queue-system/tasks_active.json`

    - **DO NOT MANAGE**: Queue transitions, task distribution, system management

    - **FOCUS ON**: Pure task execution and TODO completion

    - **AUTO-SYNC**: Triggers automatically on every task modification

  

- After any significant code change, task completion, or decision:

    - **STORE MEMORY**: Run `mcp_memory_store` (save summary ng pagbabago)

    - **UPDATE DOCUMENTATION**: Append summary sa tamang `memory-bank/*.md`

    - **TRIGGER AUTO-SYNC**: All state files automatically updated

        • `memory-bank/cursor_state.json` - Current task focus

        • `memory-bank/task_state.json` - Execution progress

        • `memory-bank/task_interruption_state.json` - Active interruptions

        • `memory-bank/current-session.md` - Session activity

        • Queue system files - Managed by autonomous engine

  

---

  

## **🔄 AUTONOMOUS QUEUE INTEGRATION**

  

- **QUEUE SYSTEM FLOW**:

    • Queue (`tasks_queue.json`) → Active (`tasks_active.json`) → Done (`tasks_done.json`)

    • **AI READS ONLY**: `tasks_active.json` for pure execution focus

    • **SYSTEM MANAGES**: All queue transitions, priority, interruptions

    • **AUTO-DETECTION**: Completion triggers automatic queue movement

  

- **TASK LIFECYCLE**:

    • New tasks → Added to queue automatically

    • Active tasks → AI executes and marks TODOs done

    • Completed tasks → Auto-moved to done queue

    • Interrupted tasks → Priority resume on next session

  

---

  

## **💬 Q&A AND MEMORY PROTOCOL**

  

- For all questions and responses:

    - **PRIORITY ORDER**: MCP memory → memory-bank → execution context

    - **STATE VERIFICATION**: Always check state file consistency

    - **CURRENT FOCUS**: Use `tasks_active.json` as primary task source

    - **SESSION CONTEXT**: Reference `current-session.md` for recent activity

  

---

  

## **🔧 SESSION CONTINUITY SYSTEM**

  

- **AUTOMATIC STATE SYNC** (After file saves, edits, tests):

    • Auto-sync manager handles all state consistency

    • No manual intervention required

    • Real-time state updates across all files

    • Timestamps automatically managed

  

- **DISCONNECT/RECONNECT HANDLING**:

    • **RESUME STATE**: Read `tasks_active.json` for current work

    • **RESTORE CONTEXT**: Load `cursor_state.json` for cursor position

    • **SYNC REALITY**: Ensure all state files match current system state

    • **QUEUE CONTINUITY**: Autonomous queue system maintains flow

  

---

  

## **🛡️ CONSISTENCY ENFORCEMENT**

  

- **DUPLICATE PREVENTION**:

    • Check existing tasks before creating new ones

    • Reuse and update existing tasks instead of duplicating

    • Maintain task ID consistency across system

  

- **DATA INTEGRITY**:

    • All timestamps in Philippines timezone (UTC+8)

    • Consistent JSON formatting across all files

    • Automatic backup and rollback capabilities

    • Error recovery with graceful degradation

  

---

  

## **🎯 SUCCESS METRICS**

  

- **OPERATIONAL EXCELLENCE**:

    • Zero manual queue management required

    • 100% auto-sync success rate

    • Complete task execution focus for AI

    • Seamless session continuity across disconnections

  

- **AUTOMATION GOALS**:

    • AI focuses purely on task execution

    • System handles all queue and state management

    • No state inconsistencies or data loss

    • Real-time monitoring and auto-correction

  

---

  

**SYSTEM STATUS**: 🟢 FULLY OPERATIONAL

**AUTO-SYNC**: ✅ ACTIVE  

**QUEUE ENGINE**: ✅ AUTONOMOUS

**AI SCOPE**: ✅ EXECUTION FOCUSED

  

- **MAINTAIN TIMESTAMP CONSISTENCY**:

    • Use ISO format timestamps consistently

    • Update `last_activity` and `disconnected_at` timestamps

    • Ensure all state files have consistent timestamps

  

- **VALIDATE STATE INTEGRITY**:

    • Check that `memory-bank/task_state.json` matches active tasks

    • Verify `memory-bank/task_interruption_state.json` points to valid task ID

    • Ensure `memory-bank/cursor_state.json` reflects current reality

    • Confirm AI only reads `memory-bank/queue-system/tasks_active.json`

- On disconnect / reconnect events:

    - Look at cursor_state.json to resume cursor position.

  

---

  

## ✅ STRICT PLAN ADHERENCE (HARD ENFORCEMENT)

- `memory-bank/queue-system/tasks_active.json` is the single source of truth.

- No deviation or improvisation. If a step fails, follow its defined rollback.

- All actions must map to a specific phase index in the plan.

  

## 🔒 REQUIRED LOOP PER PHASE k

1. Post-Review: Create `memory-bank/DOCUMENTS/<task_id>_phase{k}_postreview.md`

   - Summarize what was done and validate against the phase’s "IMPORTANT NOTE".

2. Next-Phase Pre-Analysis: Create `memory-bank/DOCUMENTS/<task_id>_phase{k+1}_preanalysis.md`

   - Restate next phase "IMPORTANT NOTE", add risks and prerequisites.

  

4. Done: Run `python3 todo_manager.py done <task_id> <k>`.

5. Sync/Memory: Run `mcp_memory_store` and rely on auto-sync to update state files.