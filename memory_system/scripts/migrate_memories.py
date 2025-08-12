"""Migrate markdown memories into SQLite provider.

Usage:
    python -m memory_system.scripts.migrate_memories --to sqlite
"""
from __future__ import annotations

import argparse
from pathlib import Path
from memory_system.services.memory_provider import get_provider, MemoryProvider


def migrate_to_sqlite(root: Path = Path("memory-bank")) -> None:  # noqa: D401
    provider = get_provider("sqlite")
    count = 0
    for md_file in root.glob("*.md"):
        title = md_file.stem
        content = md_file.read_text(encoding="utf-8", errors="ignore")
        provider.add(title, content)
        count += 1
    print(f"✅ Migrated {count} markdown memories into SQLite DB.")


def main(argv: list[str] | None = None) -> None:  # noqa: D401
    parser = argparse.ArgumentParser(description="Memory migration utility")
    parser.add_argument("--to", choices=["sqlite"], required=True, help="Target provider kind")
    args = parser.parse_args(argv)

    if args.to == "sqlite":
        migrate_to_sqlite()


if __name__ == "__main__":
    import sys

    main(sys.argv[1:])