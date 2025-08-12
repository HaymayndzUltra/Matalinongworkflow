#!/usr/bin/env python3
"""
Task Interruption Manager - Automatically handles task switching and resumption
"""

import json
import os
import time
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path

# Import existing managers
from todo_manager import new_task, add_todo, list_open_tasks, set_task_status
from task_state_manager import save_task_state, load_task_state

class TaskInterruptionManager:
    """Manages automatic task interruption and resumption"""
    
    def __init__(self):
        self.interruption_file = Path("task_interruption_state.json")
        self.current_task = None
        self.interrupted_tasks = []
        self.load_state()
    
    def load_state(self):
        """Load interruption state from file"""
        if self.interruption_file.exists():
            try:
                with open(self.interruption_file, 'r') as f:
                    data = json.load(f)
                    self.current_task = data.get('current_task')
                    self.interrupted_tasks = data.get('interrupted_tasks', [])
            except Exception as e:
                print(f"⚠️  Error loading interruption state: {e}")
    
    def save_state(self):
        """Save interruption state to file"""
        data = {
            'current_task': self.current_task,
            'interrupted_tasks': self.interrupted_tasks,
            'last_updated': datetime.utcnow().isoformat()
        }
        try:
            with open(self.interruption_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"⚠️  Error saving interruption state: {e}")
    
    def start_task(self, task_description: str) -> str:
        """Start a new task, interrupting current if any"""
        
        # If there's a current task, interrupt it
        if self.current_task:
            self.interrupt_current_task()
        
        # Create new task
        task_id = new_task(task_description)
        self.current_task = {
            'task_id': task_id,
            'description': task_description,
            'started_at': datetime.utcnow().isoformat(),
            'status': 'active'
        }
        
        self.save_state()
        print(f"🚀 Started new task: {task_description}")
        print(f"   Task ID: {task_id}")
        
        return task_id
    
    def interrupt_current_task(self):
        """Interrupt the current task and save it for later resumption"""
        if self.current_task:
            self.current_task['status'] = 'interrupted'
            self.current_task['interrupted_at'] = datetime.utcnow().isoformat()
            self.interrupted_tasks.append(self.current_task)
            
            print(f"⏸️  Interrupted task: {self.current_task['description']}")
            print(f"   Task ID: {self.current_task['task_id']}")
            print(f"   Will resume automatically after current task")
            
            # Update task status in todo_manager
            set_task_status(self.current_task['task_id'], 'interrupted')
    
    def resume_interrupted_tasks(self):
        """Resume all interrupted tasks"""
        if not self.interrupted_tasks:
            print("ℹ️  No interrupted tasks to resume")
            return
        
        print(f"🔄 Resuming {len(self.interrupted_tasks)} interrupted task(s)...")
        
        for task in self.interrupted_tasks:
            print(f"   📋 Resuming: {task['description']}")
            print(f"      Task ID: {task['task_id']}")
            
            # Update task status back to in_progress
            set_task_status(task['task_id'], 'in_progress')
        
        # Clear interrupted tasks list
        self.interrupted_tasks = []
        self.current_task = None
        self.save_state()
        
        print("✅ All interrupted tasks resumed")
    
    def get_current_status(self) -> Dict[str, Any]:
        """Get current interruption status"""
        return {
            'current_task': self.current_task,
            'interrupted_tasks_count': len(self.interrupted_tasks),
            'interrupted_tasks': self.interrupted_tasks
        }
    
    def auto_detect_new_task(self, command: str) -> bool:
        """Auto-detect if command is a new task"""
        new_task_indicators = [
            'new task', 'create task', 'add task', 'start task',
            'gawa', 'gawin', 'gawain', 'task', 'trabaho',
            'implement', 'create', 'build', 'develop',
            'fix', 'solve', 'resolve', 'address'
        ]
        
        command_lower = command.lower()
        return any(indicator in command_lower for indicator in new_task_indicators)
    
    def process_command(self, command: str) -> str:
        """Process command and handle task interruption automatically"""
        
        # Check if this is a new task
        if self.auto_detect_new_task(command):
            # Start new task (will automatically interrupt current)
            task_id = self.start_task(command)
            return f"🔄 Automatically interrupted previous task and started new task: {task_id}"
        
        # Check for resume command
        if 'resume' in command.lower() or 'ipagpatuloy' in command.lower():
            self.resume_interrupted_tasks()
            return "✅ Resumed all interrupted tasks"
        
        # Check for status command
        if 'status' in command.lower() or 'anong ginagawa' in command.lower():
            status = self.get_current_status()
            return self.format_status(status)
        
        # Regular command - continue with current task
        return f"📋 Continuing with current task: {self.current_task['description'] if self.current_task else 'None'}"
    
    def format_status(self, status: Dict[str, Any]) -> str:
        """Format status for display"""
        lines = ["📊 Task Interruption Status:"]
        
        if status['current_task']:
            # Handle both string (task ID) and dict formats
            if isinstance(status['current_task'], str):
                # It's a task ID, get the full task details
                from todo_manager import list_open_tasks
                tasks = list_open_tasks()
                current_task = None
                for task in tasks:
                    if task['id'] == status['current_task']:
                        current_task = task
                        break
                
                if current_task:
                    lines.append(f"   🚀 Current Task: {current_task['description']}")
                    lines.append(f"      ID: {current_task['id']}")
                    lines.append(f"      Status: {current_task['status']}")
                else:
                    lines.append(f"   🚀 Current Task ID: {status['current_task']} (details not found)")
                    lines.append(f"      ID: {status['current_task']}")
                    lines.append(f"      Status: Unknown")
            else:
                # It's already a dictionary
                lines.append(f"   🚀 Current Task: {status['current_task']['description']}")
                lines.append(f"      ID: {status['current_task']['task_id']}")
                lines.append(f"      Status: {status['current_task']['status']}")
        else:
            lines.append("   ℹ️  No current task")
        
        if status['interrupted_tasks_count'] > 0:
            lines.append(f"   ⏸️  Interrupted Tasks: {status['interrupted_tasks_count']}")
            for i, task in enumerate(status['interrupted_tasks'], 1):
                lines.append(f"      {i}. {task['description']}")
                lines.append(f"         ID: {task['task_id']}")
        else:
            lines.append("   ℹ️  No interrupted tasks")
        
        return "\n".join(lines)


# Global instance
interruption_manager = TaskInterruptionManager()


def auto_task_handler(command: str) -> str:
    """Main function to handle automatic task interruption"""
    return interruption_manager.process_command(command)


def start_interrupted_task(task_description: str) -> str:
    """Start a new task with automatic interruption"""
    return interruption_manager.start_task(task_description)


def resume_all_interrupted_tasks():
    """Resume all interrupted tasks"""
    interruption_manager.resume_interrupted_tasks()


def get_interruption_status() -> Dict[str, Any]:
    """Get current interruption status"""
    return interruption_manager.get_current_status()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        command = " ".join(sys.argv[1:])
        result = auto_task_handler(command)
        print(result)
    else:
        print("Task Interruption Manager")
        print("Usage: python3 task_interruption_manager.py <command>")
        print("Commands:")
        print("  <any text> - Auto-detect if it's a new task")
        print("  resume - Resume all interrupted tasks")
        print("  status - Show current status") 