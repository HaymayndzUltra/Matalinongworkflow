#!/usr/bin/env python3
"""
KYC Identity Verification Task Manager
Handles phase-based task execution and state management
"""

import json
import sys
import os
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any
import argparse
import subprocess

# Constants
MEMORY_BANK_DIR = Path("memory-bank")
STATE_DIR = MEMORY_BANK_DIR / "state"
PLAN_DIR = MEMORY_BANK_DIR / "plan"
QUEUE_DIR = Path("queue")
OUTPUTS_DIR = Path("outputs")

# Ensure directories exist
for dir_path in [STATE_DIR, PLAN_DIR, QUEUE_DIR, OUTPUTS_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)

class TaskManager:
    """Manages KYC verification tasks with phase-based execution"""
    
    def __init__(self):
        self.state_file = STATE_DIR / "tasks.json"
        self.queue_file = QUEUE_DIR / "execution_queue.json"
        self.audit_log = OUTPUTS_DIR / "audit_log.jsonl"
        self.load_state()
        
    def load_state(self):
        """Load task state from persistent storage"""
        if self.state_file.exists():
            with open(self.state_file, 'r') as f:
                self.state = json.load(f)
        else:
            self.state = self._initialize_kyc_task()
            self.save_state()
    
    def save_state(self):
        """Save task state to persistent storage"""
        with open(self.state_file, 'w') as f:
            json.dump(self.state, f, indent=2, default=str)
        self._log_audit("state_saved", {"state": self.state})
    
    def _log_audit(self, action: str, data: Dict[str, Any]):
        """Log actions to audit trail (WORM-compliant)"""
        entry = {
            "timestamp": datetime.now(timezone(timedelta(hours=8))).isoformat(),
            "action": action,
            "data": data
        }
        with open(self.audit_log, 'a') as f:
            f.write(json.dumps(entry) + "\n")
    
    def _initialize_kyc_task(self) -> Dict:
        """Initialize the KYC verification task structure"""
        task_id = "kyc_identity_verification_manifest_actionable_20250813"
        return {
            task_id: {
                "description": "Actionable plan compiled from KYC Identity Verification Manifest",
                "status": "in_progress",
                "created": datetime.now(timezone(timedelta(hours=8))).isoformat(),
                "phases": [
                    {
                        "id": 0,
                        "name": "PHASE 0: SETUP & PROTOCOL (READ FIRST)",
                        "status": "pending",
                        "explanation": "Establish strict execution protocol, gating, and constraints before any action.",
                        "important_note": "No direct writes to queue/state files by the agent. Use only read-only analyzers prior to any execution.",
                        "tasks": [
                            "Set up project structure",
                            "Initialize state management",
                            "Create execution queue system",
                            "Establish audit logging"
                        ]
                    },
                    {
                        "id": 1,
                        "name": "PHASE 1: IDENTITY CAPTURE FOUNDATIONS",
                        "status": "pending",
                        "explanation": "Implement guided capture for web/mobile with automated glare/blur/orientation checks.",
                        "important_note": "IC1: >95% pass at 1000px width; orientation auto-correct; quality scores in [0..1].",
                        "tasks": [
                            "Implement image capture module",
                            "Add quality checks (blur, glare, orientation)",
                            "Multi-frame burst support",
                            "Input validation for ID/passport/selfie"
                        ]
                    },
                    {
                        "id": 2,
                        "name": "PHASE 2: EVIDENCE EXTRACTION PIPELINE",
                        "status": "pending",
                        "explanation": "Build a robust extraction layer: document classifier, OCR/MRZ/Barcode/NFC ingestion.",
                        "important_note": "EE1: Document classifier top-1 ≥0.9 confidence. EE2: ICAO 9303 MRZ checksums pass.",
                        "tasks": [
                            "Document classifier implementation",
                            "OCR integration (Tesseract/Cloud)",
                            "MRZ parsing (ICAO 9303)",
                            "Face cropping module"
                        ]
                    },
                    {
                        "id": 3,
                        "name": "PHASE 3: AUTHENTICITY & LIVENESS CHECKS",
                        "status": "pending",
                        "explanation": "Implement tamper/forgery detection, security-feature analysis, liveness checks.",
                        "important_note": "AU1: Security features with thresholds documented. AU2: Tamper detection AUC ≥0.9.",
                        "tasks": [
                            "Security feature detection",
                            "Tamper detection (ELA/noise)",
                            "Liveness detection module",
                            "Face matching system"
                        ]
                    },
                    {
                        "id": 4,
                        "name": "PHASE 4: SANCTIONS & AML SCREENING",
                        "status": "pending",
                        "explanation": "Integrate vendor APIs for sanctions, PEP, adverse media, and watchlists.",
                        "important_note": "SA1: Vendor API integrated; hit explainability available to reviewers.",
                        "tasks": [
                            "Sanctions API integration",
                            "PEP screening implementation",
                            "IP/geo verification",
                            "Watchlist matching"
                        ]
                    },
                    {
                        "id": 5,
                        "name": "PHASE 5: RISK SCORING & DECISIONING",
                        "status": "pending",
                        "explanation": "Combine signals into aggregate risk score for approve/review/deny decisions.",
                        "important_note": "RS1: Proxy/VPN detection enabled. RS3: Calibrated thresholds with ROC/AUC reported.",
                        "tasks": [
                            "Device fingerprinting",
                            "Proxy/VPN/TOR detection",
                            "Risk score aggregation",
                            "Decision engine rules"
                        ]
                    },
                    {
                        "id": 6,
                        "name": "PHASE 6: HUMAN REVIEW CONSOLE",
                        "status": "pending",
                        "explanation": "Deliver reviewer console with PII redaction and dual-control workflows.",
                        "important_note": "HR1: PII redaction toggle present; two-person approval for high risk.",
                        "tasks": [
                            "Review UI implementation",
                            "PII redaction system",
                            "Dual-control workflow",
                            "Case management system"
                        ]
                    },
                    {
                        "id": 7,
                        "name": "PHASE 7: COMPLIANCE, SECURITY, AND PRIVACY",
                        "status": "pending",
                        "explanation": "Ensure compliance with DPA/GDPR/CCPA and AML/KYC regulations.",
                        "important_note": "CP1: DPA/GDPR/CCPA alignment. CP2: AES-256 at rest; TLS1.2+.",
                        "tasks": [
                            "Data encryption implementation",
                            "Retention policy system",
                            "DPIA documentation",
                            "Compliance reporting"
                        ]
                    },
                    {
                        "id": 8,
                        "name": "PHASE 8: OPERATIONS, OBSERVABILITY, AND MODEL LIFECYCLE",
                        "status": "pending",
                        "explanation": "Implement observability, SLOs, monitoring, and model management.",
                        "important_note": "OP1: SLOs defined; dashboards show risk distributions. OP2: Drift monitoring configured.",
                        "tasks": [
                            "Metrics and monitoring",
                            "SLO implementation",
                            "Model drift detection",
                            "Fairness/bias audits"
                        ]
                    }
                ]
            }
        }
    
    def show(self, task_id: str) -> None:
        """Display task status and phases"""
        if task_id not in self.state:
            print(f"❌ Task not found: {task_id}")
            return
        
        task = self.state[task_id]
        print(f"\n{'='*60}")
        print(f"📋 TASK: {task_id}")
        print(f"{'='*60}")
        print(f"Description: {task['description']}")
        print(f"Status: {task['status']}")
        print(f"Created: {task['created']}")
        print(f"\n{'─'*60}")
        print("PHASES:")
        print(f"{'─'*60}\n")
        
        for phase in task['phases']:
            status_icon = "✅" if phase['status'] == 'completed' else "⏳" if phase['status'] == 'in_progress' else "⏸️"
            print(f"{status_icon} {phase['name']}")
            print(f"   Status: {phase['status']}")
            print(f"   Explanation: {phase['explanation']}")
            if 'important_note' in phase:
                print(f"   ⚠️  IMPORTANT NOTE: {phase['important_note']}")
            if 'tasks' in phase and phase['tasks']:
                print(f"   Tasks:")
                for task in phase['tasks']:
                    print(f"      • {task}")
            print()
    
    def done(self, task_id: str, phase_id: int) -> None:
        """Mark a phase as completed"""
        if task_id not in self.state:
            print(f"❌ Task not found: {task_id}")
            return
        
        task = self.state[task_id]
        if phase_id >= len(task['phases']):
            print(f"❌ Invalid phase ID: {phase_id}")
            return
        
        phase = task['phases'][phase_id]
        old_status = phase['status']
        phase['status'] = 'completed'
        phase['completed_at'] = datetime.now(timezone(timedelta(hours=8))).isoformat()
        
        # Check if all phases are complete
        all_complete = all(p['status'] == 'completed' for p in task['phases'])
        if all_complete:
            task['status'] = 'completed'
            task['completed_at'] = datetime.now(timezone(timedelta(hours=8))).isoformat()
        
        self.save_state()
        self._log_audit("phase_completed", {
            "task_id": task_id,
            "phase_id": phase_id,
            "phase_name": phase['name'],
            "old_status": old_status,
            "new_status": "completed"
        })
        
        print(f"✅ Phase {phase_id} marked as completed: {phase['name']}")
        
        # Show next phase if available
        if phase_id + 1 < len(task['phases']):
            next_phase = task['phases'][phase_id + 1]
            print(f"\n📌 Next Phase: {next_phase['name']}")
            print(f"   Explanation: {next_phase['explanation']}")
    
    def exec(self, task_id: str, sub_step: str) -> None:
        """Execute a specific sub-step"""
        # This would execute specific implementation steps
        # For now, we'll log the execution request
        self._log_audit("exec_requested", {
            "task_id": task_id,
            "sub_step": sub_step,
            "timestamp": datetime.now(timezone(timedelta(hours=8))).isoformat()
        })
        print(f"🚀 Executing sub-step {sub_step} for task {task_id}")
        print(f"   [Implementation would run here]")
    
    def list(self) -> None:
        """List all tasks"""
        print(f"\n{'='*60}")
        print("📋 ALL TASKS")
        print(f"{'='*60}\n")
        
        for task_id, task in self.state.items():
            status_icon = "✅" if task['status'] == 'completed' else "🔄"
            print(f"{status_icon} {task_id}")
            print(f"   Status: {task['status']}")
            print(f"   Description: {task['description']}")
            
            # Count phase completion
            total_phases = len(task['phases'])
            completed_phases = sum(1 for p in task['phases'] if p['status'] == 'completed')
            print(f"   Progress: {completed_phases}/{total_phases} phases completed")
            print()

def main():
    """Main entry point for the task manager"""
    parser = argparse.ArgumentParser(description='KYC Identity Verification Task Manager')
    parser.add_argument('command', choices=['show', 'done', 'exec', 'list'],
                       help='Command to execute')
    parser.add_argument('task_id', nargs='?', help='Task ID')
    parser.add_argument('phase_or_substep', nargs='?', help='Phase ID (for done) or sub-step (for exec)')
    
    args = parser.parse_args()
    
    manager = TaskManager()
    
    if args.command == 'list':
        manager.list()
    elif args.command == 'show':
        if not args.task_id:
            print("❌ Task ID required for 'show' command")
            sys.exit(1)
        manager.show(args.task_id)
    elif args.command == 'done':
        if not args.task_id or args.phase_or_substep is None:
            print("❌ Task ID and phase ID required for 'done' command")
            sys.exit(1)
        try:
            phase_id = int(args.phase_or_substep)
            manager.done(args.task_id, phase_id)
        except ValueError:
            print(f"❌ Invalid phase ID: {args.phase_or_substep}")
            sys.exit(1)
    elif args.command == 'exec':
        if not args.task_id or not args.phase_or_substep:
            print("❌ Task ID and sub-step required for 'exec' command")
            sys.exit(1)
        manager.exec(args.task_id, args.phase_or_substep)

if __name__ == "__main__":
    main()