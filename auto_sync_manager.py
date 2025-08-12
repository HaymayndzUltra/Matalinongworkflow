#!/usr/bin/env python3
"""
Auto Sync Manager
Automatically syncs all state files on session start and after task changes
"""

import json
import os
import logging
import atexit
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from common.utils.log_setup import configure_logging

# Configure logging
logger = configure_logging(__name__)

def get_philippines_time() -> datetime:
    """Get current Philippines time (UTC+8)"""
    utc_now = datetime.now(timezone.utc)
    philippines_tz = timezone(timedelta(hours=8))
    return utc_now.astimezone(philippines_tz)

def format_philippines_time(dt: datetime) -> str:
    """Format datetime to Philippines time with 12-hour format"""
    philippines_tz = timezone(timedelta(hours=8))
    ph_time = dt.astimezone(philippines_tz)
    return ph_time.strftime('%Y-%m-%d %I:%M:%S %p')  # 12-hour format with AM/PM

def format_philippines_time_iso(dt: datetime) -> str:
    """Format datetime to Philippines time in ISO format"""
    philippines_tz = timezone(timedelta(hours=8))
    ph_time = dt.astimezone(philippines_tz)
    return ph_time.isoformat()

class AutoSyncManager:
    """Automatically syncs state files without manual intervention"""
    
    def __init__(self):
        self.state_files = {
            'cursor_state': 'memory-bank/cursor_state.json',
            'task_state': 'memory-bank/task_state.json',
            'task_interruption': 'memory-bank/task_interruption_state.json',
            'active_tasks': 'memory-bank/queue-system/tasks_active.json',
            'current_session': 'memory-bank/current-session.md'
        }
        self._setup_auto_sync()
        logger.info("🔄 AutoSyncManager initialized - automatic sync enabled")
    
    def _setup_auto_sync(self):
        """Setup automatic sync on session start and exit"""
        # Auto-sync on session start
        self.sync_all_states()
        
        # Auto-sync on session exit
        atexit.register(self._sync_on_exit)
        
        logger.info("✅ Auto-sync setup complete")
    
    def _sync_on_exit(self):
        """Sync all states when session ends"""
        logger.info("🔄 Auto-syncing on session exit...")
        self.sync_all_states()
    
    def sync_all_states(self) -> Dict[str, Any]:
        """Sync all state files automatically"""
        try:
            # Step 1: Read current state from active tasks (new system)
            current_tasks = self._get_current_active_tasks()
            
            # Step 2: Determine the most recent active task
            active_task = self._get_most_recent_active_task(current_tasks)
            
            # Step 3: Update all state files
            self._update_cursor_state(active_task)
            self._update_task_state(active_task)
            self._update_task_interruption_state(active_task)
            self._update_current_session(active_task, current_tasks)
            
            logger.info("✅ Auto-sync completed successfully")
            return {
                "status": "success",
                "active_task": active_task.get('id') if active_task else None,
                "total_tasks": len(current_tasks),
                "synced_at": format_philippines_time_iso(get_philippines_time())
            }
            
        except Exception as e:
            logger.error(f"❌ Auto-sync failed: {e}")
            return {
                "status": "error",
                "error": str(e),
                "synced_at": format_philippines_time_iso(get_philippines_time())
            }
    
    def _get_current_active_tasks(self) -> List[Dict[str, Any]]:
        """Get current active tasks from queue system"""
        try:
            with open(self.state_files['active_tasks'], 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.warning("Active tasks file not found - creating empty")
            return []
        except Exception as e:
            logger.error(f"❌ Failed to read active tasks: {e}")
            return []
    
    def _get_most_recent_active_task(self, tasks: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Get the most recent active task"""
        if not tasks:
            return None
        
        # Filter for in_progress tasks
        active_tasks = [task for task in tasks if task.get('status') == 'in_progress']
        
        if not active_tasks:
            # If no in_progress tasks, get the most recent task
            active_tasks = tasks
        
        # Sort by updated timestamp (most recent first)
        active_tasks.sort(key=lambda x: x.get('updated', ''), reverse=True)
        
        return active_tasks[0] if active_tasks else None
    
    def _update_cursor_state(self, active_task: Optional[Dict[str, Any]]):
        """Update cursor_state.json"""
        try:
            ph_time = get_philippines_time()
            cursor_state = {
                "cursor_session": {
                    "disconnected_at": format_philippines_time_iso(ph_time),
                    "current_task": active_task.get('description', '') if active_task else '',
                    "progress": self._calculate_progress(active_task) if active_task else 0.0,
                    "last_activity": active_task.get('updated', format_philippines_time_iso(ph_time)) if active_task else format_philippines_time_iso(ph_time)
                }
            }
            
            # Update memory-bank version (primary)
            with open(self.state_files['cursor_state'], 'w') as f:
                json.dump(cursor_state, f, indent=2)
            
            # Also update root level if it exists (for compatibility)
            root_cursor_state = 'cursor_state.json'
            if os.path.exists(root_cursor_state):
                with open(root_cursor_state, 'w') as f:
                    json.dump(cursor_state, f, indent=2)
            
        except Exception as e:
            logger.error(f"❌ Failed to update cursor_state.json: {e}")
    
    def _update_task_state(self, active_task: Optional[Dict[str, Any]]):
        """Update task-state.json"""
        try:
            ph_time = get_philippines_time()
            if active_task:
                task_state = {
                    "current_task_id": active_task.get('id', ''),
                    "current_task_description": active_task.get('description', ''),
                    "status": active_task.get('status', ''),
                    "last_updated": active_task.get('updated', format_philippines_time_iso(ph_time)),
                    "todos_count": len(active_task.get('todos', [])),
                    "completed_todos": len([todo for todo in active_task.get('todos', []) if todo.get('done', False)])
                }
            else:
                task_state = {}
            
            with open(self.state_files['task_state'], 'w') as f:
                json.dump(task_state, f, indent=2)
            
        except Exception as e:
            logger.error(f"❌ Failed to update task-state.json: {e}")
    
    def _update_task_interruption_state(self, active_task: Optional[Dict[str, Any]]):
        """Update task_interruption_state.json"""
        try:
            ph_time = get_philippines_time()
            interruption_state = {
                "current_task": active_task.get('id', None) if active_task else None,
                "interrupted_tasks": [],
                "last_updated": format_philippines_time_iso(ph_time)
            }
            
            with open(self.state_files['task_interruption'], 'w') as f:
                json.dump(interruption_state, f, indent=2)
            
        except Exception as e:
            logger.error(f"❌ Failed to update task_interruption_state.json: {e}")
    
    def _update_current_session(self, active_task: Optional[Dict[str, Any]], all_tasks: List[Dict[str, Any]]):
        """Update memory-bank/current-session.md"""
        try:
            # Get in_progress tasks for display
            in_progress_tasks = [task for task in all_tasks if task.get('status') == 'in_progress']
            
            ph_time = get_philippines_time()
            session_content = f"""# 📝 Current Cursor Session — {format_philippines_time(ph_time)} PH

| Field | Value |
|-------|-------|
| current_file | — |
| cursor_line | — |
| current_task | {active_task.get('description', 'No active task') if active_task else 'No active task'} |
| progress | {self._calculate_progress(active_task) if active_task else 0.0} |
| last_activity | {active_task.get('updated', format_philippines_time_iso(ph_time)) if active_task else format_philippines_time_iso(ph_time)} |
| disconnected_at | {format_philippines_time_iso(ph_time)} |

## 🕒 Open Tasks (Todo Manager)
"""
            
            for task in in_progress_tasks:
                todos_left = len([todo for todo in task.get('todos', []) if not todo.get('done', False)])
                session_content += f"- **{task.get('description', 'Unknown task')}** ({todos_left} todos left)\n"
            
            if not in_progress_tasks:
                session_content += "- No active tasks\n"
            
            # Ensure memory-bank directory exists
            os.makedirs('memory-bank', exist_ok=True)
            
            with open(self.state_files['current_session'], 'w') as f:
                f.write(session_content)
            
        except Exception as e:
            logger.error(f"❌ Failed to update current-session.md: {e}")
    
    def _calculate_progress(self, task: Optional[Dict[str, Any]]) -> float:
        """Calculate progress based on completed TODOs"""
        if not task or not task.get('todos'):
            return 0.0
        
        todos = task.get('todos', [])
        completed = len([todo for todo in todos if todo.get('done', False)])
        total = len(todos)
        
        return completed / total if total > 0 else 0.0
    
    def cleanup_duplicate_tasks(self) -> Dict[str, Any]:
        """Clean up duplicate tasks in active tasks queue"""
        logger.info("🧹 Starting duplicate task cleanup...")
        
        try:
            tasks = self._get_current_active_tasks()
            original_count = len(tasks)
            
            # Group tasks by description
            tasks_by_description = {}
            for task in tasks:
                description = task.get('description', '').strip()
                if description not in tasks_by_description:
                    tasks_by_description[description] = []
                tasks_by_description[description].append(task)
            
            # Keep only the most recent task for each description
            cleaned_tasks = []
            duplicates_removed = 0
            
            for description, task_list in tasks_by_description.items():
                if len(task_list) > 1:
                    # Sort by updated timestamp (most recent first)
                    task_list.sort(key=lambda x: x.get('updated', ''), reverse=True)
                    cleaned_tasks.append(task_list[0])
                    duplicates_removed += len(task_list) - 1
                    logger.info(f"🔍 Removed {len(task_list) - 1} duplicates for: {description[:50]}...")
                else:
                    cleaned_tasks.append(task_list[0])
            
            # Update active tasks file
            with open(self.state_files['active_tasks'], 'w') as f:
                json.dump(cleaned_tasks, f, indent=2)
            
            logger.info(f"✅ Cleanup complete: {duplicates_removed} duplicates removed")
            
            return {
                "status": "success",
                "original_count": original_count,
                "final_count": len(cleaned_tasks),
                "duplicates_removed": duplicates_removed
            }
            
        except Exception as e:
            logger.error(f"❌ Cleanup failed: {e}")
            return {
                "status": "error",
                "error": str(e)
            }

    def force_sync(self):
        """Force immediate sync (for manual triggers)"""
        logger.info("🔄 Force sync triggered...")
        return self.sync_all_states()

# Global instance for auto-sync
_auto_sync_manager = None

def get_auto_sync_manager() -> AutoSyncManager:
    """Get the global auto-sync manager instance"""
    global _auto_sync_manager
    if _auto_sync_manager is None:
        _auto_sync_manager = AutoSyncManager()
    return _auto_sync_manager

def auto_sync():
    """Trigger auto-sync manually"""
    manager = get_auto_sync_manager()
    return manager.force_sync()

# Auto-initialize on import
get_auto_sync_manager() 