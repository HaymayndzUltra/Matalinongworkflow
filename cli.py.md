Monitoring dashboard (placeholder)
subparsers.add_parser("monitor", help="Launch real-time monitoring dashboard (TUI)")

    # Save memory note (new)
    save_parser = subparsers.add_parser("save", help="Save a memory note to current-session and JSON store")
    save_parser.add_argument("message", help="Memory note/message to save")
    save_parser.add_argument("--task", dest="task", help="Optional task ID to associate with this memory")
    save_parser.add_argument("--tag", dest="tag", default="note", help="Optional tag/category (default: note)")

Architecture Mode commands
arch_parser = subparsers.add_parser("arch-mode", help="Architecture-first planning and development workflow")
arch_subparsers = arch_parser.add_subparsers(dest="arch_command")
@@ -165,6 +171,69 @@ def main(argv: OptionalList[str] = None) -> None:  # noqa: D401
from architecture_mode_engine import handle_arch_mode_command

handle_arch_mode_command(args)
    elif args.command == "save":
        # Persist memory note to markdown and JSON store
        from pathlib import Path
        from datetime import datetime, timezone, timedelta
        import json as json

        repo_root = Path(__file__).resolve().parent.parent
        session_md = repo_root / "memory-bank" / "current-session.md"
        json_store = repo_root / "memory_store.json"

        # PH timezone ISO8601
        ph_time = datetime.utcnow().replace(tzinfo=timezone.utc).astimezone(timezone(timedelta(hours=8)))
        iso = ph_time.isoformat()

        # Append to current-session.md
        try:
            lines = []
            if session_md.exists():
                try:
                    lines.append("")
                except Exception:
                    pass
            lines.append(f"## Memory Note — {iso}")
            if getattr(args, "task", None):
                lines.append(f"- Task: {args.task}")
            if getattr(args, "tag", None):
                lines.append(f"- Tag: {args.tag}")
            lines.append(f"- Note: {args.message}")
            lines.append("")
            session_md.parent.mkdir(parents=True, exist_ok=True)
            with session_md.open("a", encoding="utf-8") as fh:
                fh.write("\n".join(lines))
        except Exception as e:  # noqa: BLE001
            print(f"⚠️  Could not write current-session.md: {e}")

        # Append to memory_store.json
        try:
            payload = {"timestamp": iso, "task": getattr(args, "task", None), "tag": getattr(args, "tag", None), "note": args.message}
            if json_store.exists():
                try:
                    data = _json.loads(json_store.read_text(encoding="utf-8"))
                except Exception:
                    data = {}
            else:
                data = {}
            notes = data.get("notes", [])
            notes.append(payload)
            data["notes"] = notes
            json_store.write_text(_json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception as e:  # noqa: BLE001
            print(f"⚠️  Could not write memory_store.json: {e}")

        # Auto-sync if available
        try:
            from auto_sync_manager import auto_sync  # type: ignore
            auto_sync()
        except Exception:
            pass

        # Final message
        task_val = getattr(args, "task", None)
        target = f"task={task_val}" if task_val else "no-task"
        print(f"✅ Saved memory ({target}) @ {iso}")
else:
parser.print_help()
