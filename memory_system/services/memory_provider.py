"""Memory Provider Abstraction Layer

Phase-3 milestone: consolidate existing markdown/JSON memories into a pluggable
provider system so we can later move to SQLite or vector stores without changing
call-sites.
"""
from __future__ import annotations

import os
import re
import sqlite3
from pathlib import Path
from typing import List, Protocol, Optional

# ---------------------------------------------------------------------------
# Provider Interface
# ---------------------------------------------------------------------------


class MemoryProvider(Protocol):  # noqa: D401
    """Interface every provider must implement."""

    def search(self, keyword: str, limit: int = 10) -> List[str]:  # noqa: D401
        """Return paths or identifiers of memories containing keyword."""

    def add(self, title: str, content: str) -> None:  # noqa: D401
        """Persist a new memory snippet."""


# ---------------------------------------------------------------------------
# File-System Provider (current default)
# ---------------------------------------------------------------------------


class FileSystemMemoryProvider:
    """Current default provider scanning *.md files inside `memory-bank/`."""

    def __init__(self, root: str | Path = "memory-bank"):
        self.root = Path(root)

    def _iter_files(self):
        return self.root.rglob("*.md")

    def search(self, keyword: str, limit: int = 10) -> List[str]:
        pattern = re.compile(re.escape(keyword), re.IGNORECASE)
        results: List[str] = []
        for p in self._iter_files():
            try:
                if pattern.search(p.read_text(errors="ignore")):
                    results.append(str(p))
                    if len(results) >= limit:
                        break
            except Exception:  # noqa: BLE001
                continue
        return results

    def add(self, title: str, content: str) -> None:
        safe_title = re.sub(r"[^\w\-]+", "_", title)[:50]
        path = self.root / f"{safe_title}.md"
        path.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# SQLite Provider (prototype)
# ---------------------------------------------------------------------------


class SQLiteMemoryProvider:
    """SQLite-based provider storing memories in a single DB file."""

    def __init__(self, db_path: str | Path = "memory-bank/memory.db"):
        self.db_path = Path(db_path)
        self._ensure_schema()

    # ––––– Internal helpers –––––
    def _get_conn(self):
        return sqlite3.connect(self.db_path)

    def _ensure_schema(self):
        conn = self._get_conn()
        with conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL
                )
                """
            )
        conn.close()

    # ––––– Public API –––––
    def search(self, keyword: str, limit: int = 10) -> List[str]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT id, title FROM memories WHERE content LIKE ? LIMIT ?",
            (f"%{keyword}%", limit),
        ).fetchall()
        conn.close()
        return [f"sqlite://memory/{row[0]}:{row[1]}" for row in rows]

    def add(self, title: str, content: str) -> None:
        conn = self._get_conn()
        with conn:
            conn.execute("INSERT INTO memories (title, content) VALUES (?,?)", (title, content))
        conn.close()


# ---------------------------------------------------------------------------
# Chroma Provider (stub for vector-store integration)
# ---------------------------------------------------------------------------


class ChromaMemoryProvider:
    """ChromaDB-backed provider with sentence-transformers embeddings.

    Falls back to in-memory search if dependencies are missing.
    """

    def __init__(self, persist_dir: str | Path = "memory-bank/chroma_db"):
        try:
            import chromadb  # type: ignore
            from sentence_transformers import SentenceTransformer  # type: ignore

            self._chroma = chromadb.PersistentClient(path=str(persist_dir))
            self._collection = self._chroma.get_or_create_collection("memories")
            self._model = SentenceTransformer("all-MiniLM-L6-v2")
            self._fallback = None
        except ImportError:
            # Dependencies missing – use simple in-memory fallback
            self._fallback: list[tuple[str, str]] = []

    # ----------------------------- helpers -----------------------------
    def _embed(self, texts: List[str]):
        if hasattr(self, "_model"):
            return self._model.encode(texts).tolist()
        return []

    # ----------------------------- public API --------------------------
    def search(self, keyword: str, limit: int = 10) -> List[str]:
        if self._fallback is not None:
            return [title for title, content in self._fallback if keyword.lower() in content.lower()][:limit]

        # Semantic search via embeddings
        query_vec = self._embed([keyword])[0]
        results = self._collection.query(query_embeddings=[query_vec], n_results=limit)
        return [doc for doc in results.get("documents", [[]])[0]]

    def add(self, title: str, content: str) -> None:
        if self._fallback is not None:
            self._fallback.append((title, content))
            return

        emb = self._embed([content])[0]
        self._collection.add(ids=[title], documents=[content], embeddings=[emb])


# ---------------------------------------------------------------------------
# Factory helper
# ---------------------------------------------------------------------------


def get_provider(kind: str = "fs") -> MemoryProvider:  # noqa: D401
    if kind == "fs":
        return FileSystemMemoryProvider()
    elif kind == "sqlite":
        return SQLiteMemoryProvider()
    elif kind == "chroma":
        return ChromaMemoryProvider()
    else:
        raise ValueError(f"Unknown memory provider kind: {kind}")