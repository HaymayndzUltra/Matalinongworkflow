"""Real-time monitoring dashboard (TUI).

Launch with:
    memoryctl monitor --watch
"""
from __future__ import annotations

import asyncio
import json
from typing import Deque, Dict
from collections import deque

from rich.console import Console
from rich.live import Live
from rich.table import Table
from rich.panel import Panel

from memory_system.services import telemetry as _telemetry


class TelemetryBuffer:
    """Stores recent telemetry events for display."""

    def __init__(self, maxlen: int = 1000):
        self.events: Deque[Dict] = deque(maxlen=maxlen)

    def add(self, payload: Dict):
        self.events.appendleft(payload)

    def task_counts(self):
        start = sum(1 for e in self.events if e["event"].endswith("_start"))
        end = sum(1 for e in self.events if e["event"].endswith("_end"))
        error = sum(1 for e in self.events if e["event"].endswith("_error"))
        return start, end, error

    def to_table(self):
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("TS", justify="right", width=10)
        table.add_column("Event")
        table.add_column("Desc", overflow="fold")
        for ev in list(self.events)[:20]:
            table.add_row(
                f"{ev['ts']:.3f}",
                ev["event"],
                ev.get("description", "")[:40],
            )
        return table


async def _run_dashboard():  # noqa: D401
    console = Console()
    buf = TelemetryBuffer()

    def _on_event(payload):
        buf.add(payload)

    _telemetry.register_subscriber(_on_event)

    with Live(refresh_per_second=4, console=console) as live:
        while True:
            start, end, error = buf.task_counts()
            header = Panel(
                f"[bold]Telemetry[/]  start={start}  end={end}  error={error}",
                style="green",
            )
            live.update(Panel.fit(buf.to_table(), title="Recent Events", border_style="blue"))
            await asyncio.sleep(0.25)


def run_dashboard():  # noqa: D401
    try:
        asyncio.run(_run_dashboard())
    finally:
        _telemetry.unregister_subscriber