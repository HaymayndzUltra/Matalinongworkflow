#!/usr/bin/env python3
"""
KYC Identity Verification Todo Manager
Manages task tracking and phase completion for KYC system implementation
"""

import json
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum

class TaskStatus(Enum):
    """Task status enumeration"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BLOCKED = "blocked"

@dataclass
class TodoItem:
    """Individual todo item"""
    text: str
    done: bool
    phase: Optional[int] = None
    timestamp: Optional[str] = None

@dataclass
class Task:
    """Task with multiple todo items"""
    id: str
    description: str
    status: str
    created: str
    updated: str
    todos: List[TodoItem]
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        return {
            "id": self.id,
            "description": self.description,
            "status": self.status,
            "created": self.created,
            "updated": self.updated,
            "todos": [
                {"text": t.text, "done": t.done, "phase": t.phase}
                for t in self.todos
            ]
        }

class TodoManager:
    """Manages KYC implementation tasks and phases"""
    
    def __init__(self, tasks_file: str = "tasks_active.json"):
        self.tasks_file = Path(tasks_file)
        self.tasks: List[Task] = []
        self.load_tasks()
        
    def get_timestamp(self) -> str:
        """Get ISO8601 timestamp with +08:00 timezone"""
        tz = timezone(timedelta(hours=8))
        return datetime.now(tz).isoformat()
    
    def load_tasks(self):
        """Load tasks from JSON file"""
        if self.tasks_file.exists():
            with open(self.tasks_file, 'r') as f:
                data = json.load(f)
                for task_data in data:
                    todos = []
                    for todo in task_data.get('todos', []):
                        todos.append(TodoItem(
                            text=todo['text'],
                            done=todo.get('done', False),
                            phase=todo.get('phase')
                        ))
                    self.tasks.append(Task(
                        id=task_data['id'],
                        description=task_data['description'],
                        status=task_data['status'],
                        created=task_data['created'],
                        updated=task_data['updated'],
                        todos=todos
                    ))
    
    def save_tasks(self):
        """Save tasks to JSON file"""
        data = [task.to_dict() for task in self.tasks]
        with open(self.tasks_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def show_task(self, task_id: str):
        """Display task details and progress"""
        task = self.find_task(task_id)
        if not task:
            print(f"❌ Task '{task_id}' not found")
            return
        
        total = len(task.todos)
        completed = sum(1 for t in task.todos if t.done)
        progress = (completed / total * 100) if total > 0 else 0
        
        print(f"\n📋 Task: {task.id}")
        print(f"📝 Description: {task.description}")
        print(f"📊 Status: {task.status}")
        print(f"📅 Created: {task.created}")
        print(f"🔄 Updated: {task.updated}")
        print(f"📈 Progress: {completed}/{total} ({progress:.1f}%)")
        print("\n📌 Phases:")
        
        for i, todo in enumerate(task.todos):
            status = "✅" if todo.done else "⏳"
            phase_num = todo.phase if todo.phase is not None else i
            # Extract phase title from todo text
            lines = todo.text.split('\n')
            phase_title = lines[0] if lines else f"Phase {phase_num}"
            print(f"  {status} [{phase_num:2d}] {phase_title}")
    
    def find_task(self, task_id: str) -> Optional[Task]:
        """Find task by ID"""
        for task in self.tasks:
            if task.id == task_id:
                return task
        return None
    
    def mark_phase_done(self, task_id: str, phase: int):
        """Mark a phase as completed"""
        task = self.find_task(task_id)
        if not task:
            print(f"❌ Task '{task_id}' not found")
            return False
        
        if 0 <= phase < len(task.todos):
            task.todos[phase].done = True
            task.todos[phase].timestamp = self.get_timestamp()
            task.updated = self.get_timestamp()
            
            # Update task status
            all_done = all(t.done for t in task.todos)
            if all_done:
                task.status = "completed"
            elif any(t.done for t in task.todos):
                task.status = "in_progress"
            
            self.save_tasks()
            
            # Extract phase title
            lines = task.todos[phase].text.split('\n')
            phase_title = lines[0] if lines else f"Phase {phase}"
            print(f"✅ Completed: {phase_title}")
            
            # Show next phase if available
            if phase + 1 < len(task.todos) and not task.todos[phase + 1].done:
                next_lines = task.todos[phase + 1].text.split('\n')
                next_title = next_lines[0] if next_lines else f"Phase {phase + 1}"
                print(f"➡️  Next: {next_title}")
            
            return True
        else:
            print(f"❌ Invalid phase number: {phase}")
            return False
    
    def list_tasks(self):
        """List all tasks with their status"""
        if not self.tasks:
            print("📭 No tasks found")
            return
        
        print("\n📋 Active Tasks:")
        print("-" * 80)
        
        for task in self.tasks:
            total = len(task.todos)
            completed = sum(1 for t in task.todos if t.done)
            progress = (completed / total * 100) if total > 0 else 0
            
            status_icon = {
                "pending": "⏳",
                "in_progress": "🔄",
                "completed": "✅",
                "blocked": "🚫"
            }.get(task.status, "❓")
            
            print(f"{status_icon} {task.id}")
            print(f"   Progress: {completed}/{total} phases ({progress:.1f}%)")
            print(f"   Status: {task.status}")
            print(f"   Updated: {task.updated}")
            print()

def main():
    """CLI interface for todo manager"""
    manager = TodoManager()
    
    if len(sys.argv) < 2:
        print("Usage: python todo_manager.py <command> [args]")
        print("\nCommands:")
        print("  list                    - List all tasks")
        print("  show <task_id>          - Show task details and progress")
        print("  done <task_id> <phase>  - Mark phase as completed")
        return
    
    command = sys.argv[1]
    
    if command == "list":
        manager.list_tasks()
    
    elif command == "show":
        if len(sys.argv) < 3:
            print("Usage: python todo_manager.py show <task_id>")
            return
        manager.show_task(sys.argv[2])
    
    elif command == "done":
        if len(sys.argv) < 4:
            print("Usage: python todo_manager.py done <task_id> <phase>")
            return
        try:
            phase = int(sys.argv[3])
            manager.mark_phase_done(sys.argv[2], phase)
        except ValueError:
            print("❌ Phase must be a number")
    
    else:
        print(f"❌ Unknown command: {command}")

if __name__ == "__main__":
    main()