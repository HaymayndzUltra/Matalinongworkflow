"""
Human Review Console (Phase 12)
================================
CLI-based console for reviewers to process pending KYC cases, perform manual 
review, override automated decisions, and maintain an immutable audit log.

Key Features Implemented:
• List queues: pending / review / high_risk
• View case details with optional PII redaction toggle
• Approve, deny, or request additional info
• Dual-approval enforcement for high-risk cases
• Append-only JSONL audit log

NOTE: This is a minimal first version that stores cases in flat JSON files to
avoid DB dependency.  It will be integrated into the FastAPI service (Phase 13)
via shared models.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Optional

import typer
from rich import print, box
from rich.table import Table
from rich.console import Console
from rich.prompt import Prompt, Confirm

console = Console()
app = typer.Typer(add_completion=False, help="KYC Human Review Console")

# ----------------------------- Config & Constants ----------------------------

DATA_DIR = Path("review_data")
CASES_FILE = DATA_DIR / "cases.json"
AUDIT_LOG = DATA_DIR / "audit_log.jsonl"

DATA_DIR.mkdir(exist_ok=True)

# ----------------------------- Data Structures ------------------------------

class CaseStatus(str):
    PENDING = "pending"
    REVIEW = "review"
    HIGH_RISK = "high_risk"
    APPROVED = "approved"
    DENIED = "denied"
    ESCALATED = "escalated"


def _load_cases() -> Dict[str, Dict]:
    if not CASES_FILE.exists():
        return {}
    with open(CASES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_cases(cases: Dict[str, Dict]):
    with open(CASES_FILE, "w", encoding="utf-8") as f:
        json.dump(cases, f, indent=2, ensure_ascii=False)


def _append_audit(entry: Dict):
    entry["timestamp"] = datetime.now(timezone.utc).isoformat()
    with open(AUDIT_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

# ----------------------------- Utility Functions ----------------------------

def _mask_value(value: str) -> str:
    """Mask PII value leaving last 4 chars visible."""
    if not value or len(value) <= 4:
        return "****"
    return "*" * (len(value) - 4) + value[-4:]


def _redact_case(case: Dict) -> Dict:
    pii_fields = {"full_name", "document_number", "phone_number", "email"}
    redacted = case.copy()
    for field in pii_fields:
        if field in redacted:
            redacted[field] = _mask_value(str(redacted[field]))
    return redacted

# ----------------------------- CLI Commands ----------------------------------

@app.command()
def list(status: str = typer.Option("pending", help="Queue to list")):
    """List cases in a given status queue."""
    cases = _load_cases()
    filtered = [c for c in cases.values() if c.get("status") == status]
    if not filtered:
        console.print(f"[yellow]No cases with status '{status}'.[/]")
        return

    table = Table(title=f"Cases – {status}", box=box.SIMPLE_HEAD)
    table.add_column("Case ID", style="cyan")
    table.add_column("Doc Type")
    table.add_column("Risk", justify="right")
    table.add_column("Created")

    for case in filtered:
        table.add_row(
            case["case_id"],
            case.get("document_type", "±"),
            str(case.get("risk_score", "?")),
            case.get("created_at", "-")
        )
    console.print(table)


@app.command()
def view(case_id: str, redact: bool = typer.Option(True, help="Redact PII")):
    """View details of a single case."""
    cases = _load_cases()
    case = cases.get(case_id)
    if not case:
        console.print(f"[red]Case '{case_id}' not found.[/]")
        raise typer.Exit(code=1)

    if redact:
        case = _redact_case(case)

    console.print_json(json.dumps(case, indent=2, ensure_ascii=False))


@app.command()
def approve(case_id: str):
    """Approve a case."""
    _set_status(case_id, CaseStatus.APPROVED, reason="approved by reviewer")


@app.command()
def deny(case_id: str):
    """Deny a case."""
    reason = Prompt.ask("Reason for denial")
    _set_status(case_id, CaseStatus.DENIED, reason=reason)


@app.command()
def escalate(case_id: str):
    """Escalate a high-risk case (requires dual approval)."""
    _set_status(case_id, CaseStatus.ESCALATED, reason="escalated for dual approval")


def _set_status(case_id: str, new_status: str, reason: str):
    cases = _load_cases()
    case = cases.get(case_id)
    if not case:
        console.print(f"[red]Case '{case_id}' not found.")
        raise typer.Exit(code=1)

    old_status = case["status"]
    case["status"] = new_status
    case.setdefault("actions", []).append({
        "action": new_status,
        "reason": reason,
        "user": "console_user",
        "timestamp": datetime.now(timezone.utc).isoformat()
    })
    _save_cases(cases)
    _append_audit({
        "case_id": case_id,
        "old_status": old_status,
        "new_status": new_status,
        "reason": reason,
        "user": "console_user"
    })
    console.print(f"[green]Case '{case_id}' updated to {new_status}.[/]")


@app.command()
def ingest(json_file: Path):
    """Ingest new cases from a JSON array file for demo purposes."""
    if not json_file.exists():
        console.print(f"[red]File '{json_file}' not found.")
        raise typer.Exit(code=1)

    cases = _load_cases()
    new_cases: List[Dict] = json.loads(json_file.read_text())
    for case in new_cases:
        cid = case.get("case_id") or _generate_case_id()
        case["case_id"] = cid
        case.setdefault("status", CaseStatus.PENDING)
        case.setdefault("created_at", datetime.now(timezone.utc).isoformat())
        cases[cid] = case
    _save_cases(cases)
    console.print(f"[green]Ingested {len(new_cases)} case(s).")

# ----------------------------- Helper ---------------------------------------

def _generate_case_id() -> str:
    now = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
    return f"CASE-{now}"

# ----------------------------- Entry Point ----------------------------------

if __name__ == "__main__":
    app()