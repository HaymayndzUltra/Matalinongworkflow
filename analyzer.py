#!/usr/bin/env python3
"""
analyzer.py — Phase-by-phase Pre-Execution Analysis

Purpose
  Analyze a single phase (index K) from tasks_active.json against the repository
  to detect semantic duplicates, architectural conflicts, codebase misalignment,
  missing dependencies, and blind spots. Outputs a structured JSON report.

CLI
  python3 analyzer.py --tasks-file /path/to/tasks_active.json --phase-index K --repo-root /path/to/repo

  Alternatively, pass the full JSON content directly:
  python3 analyzer.py --tasks-json "$(cat /path/to/tasks_active.json)" --phase-index K --repo-root /path/to/repo

Output
  Prints JSON to stdout with the schema:
  {
    "phase_index": int,
    "title": str,
    "findings": [
      {
        "category": "duplicate|conflict|misalignment|missing_dependency|blind_spot",
        "severity": "LOW|MEDIUM|HIGH",
        "description": str,
        "evidence": [ {"path": str, "line": int, "snippet": str} ]
      },
      ...
    ]
  }

Notes
  - Heuristic-based; conservative thresholds to reduce false positives.
  - Scans common text/code files; skips large/binary/ignored folders.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple


# --------------------------- Filesystem Scanning ---------------------------

DEFAULT_INCLUDE_EXTENSIONS = {
    ".py", ".md", ".rst", ".txt", ".yml", ".yaml", ".json", ".toml", ".ini",
    ".sh", ".bash", ".zsh", ".fish", ".dockerignore", ".gitignore", ".env",
    ".js", ".jsx", ".ts", ".tsx", ".go", ".rs", ".java", ".cs", ".rb",
}

SPECIAL_FILENAMES = {"Dockerfile", "docker-compose.yml", "Makefile"}

DEFAULT_EXCLUDE_DIRS = {
    ".git", "node_modules", ".venv", "venv", "__pycache__", ".pytest_cache",
    ".mypy_cache", ".cache", "dist", "build", "outputs", "tmp", ".cursor",
    ".windsurf", ".idea", ".vscode", "photo-id",
}


def should_scan_file(path: Path) -> bool:
    if path.name in SPECIAL_FILENAMES:
        return True
    if path.suffix in DEFAULT_INCLUDE_EXTENSIONS:
        return True
    if path.name.lower().startswith("readme"):
        return True
    return False


def iter_repo_files(root: Path) -> Iterable[Path]:
    for dirpath, dirnames, filenames in os.walk(root):
        # prune excluded directories in-place for performance
        dirnames[:] = [d for d in dirnames if d not in DEFAULT_EXCLUDE_DIRS]
        for name in filenames:
            p = Path(dirpath) / name
            if should_scan_file(p):
                yield p


# --------------------------- Text Utilities -------------------------------

WORD_RE = re.compile(r"[A-Za-z0-9_./:-]{2,}")


def normalize(text: str) -> List[str]:
    tokens = [t.lower() for t in WORD_RE.findall(text or "")]
    stop = {
        "the", "and", "for", "with", "that", "this", "are", "not", "only", "but",
        "also", "when", "from", "into", "your", "their", "have", "has", "had",
        "will", "shall", "must", "should", "could", "would", "can", "may", "like",
        "then", "else", "elif", "true", "false", "none",
    }
    return [t for t in tokens if t not in stop and len(t) >= 3]


def bow(text: str) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for tok in normalize(text):
        counts[tok] = counts.get(tok, 0) + 1
    return counts


def cosine(a: Dict[str, int], b: Dict[str, int]) -> float:
    if not a or not b:
        return 0.0
    keys = set(a) | set(b)
    num = sum(a.get(k, 0) * b.get(k, 0) for k in keys)
    da = sum(v * v for v in a.values()) ** 0.5
    db = sum(v * v for v in b.values()) ** 0.5
    return 0.0 if da == 0 or db == 0 else float(num) / float(da * db)


def lines_with_regex(text: str, pattern: re.Pattern[str]) -> List[Tuple[int, str]]:
    out: List[Tuple[int, str]] = []
    for i, line in enumerate(text.splitlines(), start=1):
        if pattern.search(line):
            out.append((i, line.rstrip()))
    return out


# --------------------------- Findings Schema ------------------------------

@dataclass
class Evidence:
    path: str
    line: int
    snippet: str


@dataclass
class Finding:
    category: str
    severity: str
    description: str
    evidence: List[Evidence]

    def to_json(self) -> Dict[str, object]:
        return {
            "category": self.category,
            "severity": self.severity,
            "description": self.description,
            "evidence": [e.__dict__ for e in self.evidence],
        }


# --------------------------- Detectors ------------------------------------

def detect_semantic_duplicates(phase_text: str, repo_root: Path) -> List[Finding]:
    findings: List[Finding] = []
    phase_bow = bow(phase_text)
    threshold = 0.78
    for fp in iter_repo_files(repo_root):
        try:
            text = fp.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        file_bow = bow(text)
        sim = cosine(phase_bow, file_bow)
        if sim >= threshold:
            # collect a few top evidence lines that match prominent keywords
            keywords = sorted(phase_bow, key=lambda k: phase_bow[k], reverse=True)[:6]
            pattern = re.compile(r"|".join(re.escape(k) for k in keywords if k), re.I) if keywords else re.compile(r"^$")
            ev_lines = lines_with_regex(text, pattern)[:5]
            if ev_lines:
                evidence = [Evidence(path=str(fp), line=ln, snippet=snip[:200]) for ln, snip in ev_lines]
            else:
                evidence = [Evidence(path=str(fp), line=1, snippet=(text[:200] if text else ""))]
            findings.append(Finding(
                category="duplicate",
                severity="MEDIUM",
                description=f"Repository file appears semantically similar to this phase (cosine={sim:.2f}).",
                evidence=evidence,
            ))
    return findings


def detect_architectural_conflicts(phase_text: str, repo_root: Path) -> List[Finding]:
    findings: List[Finding] = []

    policy_markers = {
        "non_root": re.compile(r"non[- ]root|uid:gid|user\s+10001", re.I),
        "tini": re.compile(r"\btini\b", re.I),
        "ghcr": re.compile(r"ghcr\.io", re.I),
        "cuda": re.compile(r"cuda\s*12\.1|cu121|TORCH_CUDA_ARCH_LIST", re.I),
        "trivy": re.compile(r"\btrivy\b", re.I),
        "sbom": re.compile(r"sbom|spdx|syft", re.I),
        "health": re.compile(r"/health", re.I),
        "observability": re.compile(r"UnifiedObservabilityCenter|observability", re.I),
    }

    # quick scan corpus of repo
    file_cache: List[Tuple[Path, str]] = []
    for fp in iter_repo_files(repo_root):
        try:
            text = fp.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        file_cache.append((fp, text))

    def repo_has(pattern: re.Pattern[str]) -> List[Tuple[Path, int, str]]:
        hits: List[Tuple[Path, int, str]] = []
        for p, txt in file_cache:
            for ln, sn in lines_with_regex(txt, pattern):
                hits.append((p, ln, sn))
        return hits

    # Check each policy only if implied by phase text, to limit noise
    for name, marker in policy_markers.items():
        if marker.search(phase_text):
            hits = repo_has(marker)
            if not hits:
                findings.append(Finding(
                    category="misalignment",
                    severity="MEDIUM",
                    description=f"Phase references '{name}' policy/feature but repository shows no evidence of it.",
                    evidence=[],
                ))

    # Dockerfile policy checks
    dockerfiles = [p for p, _ in file_cache if p.name == "Dockerfile"]
    docker_texts = {p: (p.read_text(encoding="utf-8", errors="ignore") if p.exists() else "") for p in dockerfiles}

    # Non-root user enforcement
    expects_non_root = re.search(r"non[- ]root|uid:gid|user\s+10001", phase_text, re.I) is not None
    if expects_non_root and dockerfiles:
        nonroot_evidence: List[Evidence] = []
        for p, txt in docker_texts.items():
            for ln, sn in lines_with_regex(txt, re.compile(r"^\s*USER\s+10001(?::10001)?\b", re.I)):
                nonroot_evidence.append(Evidence(str(p), ln, sn))
        if not nonroot_evidence:
            findings.append(Finding(
                category="conflict",
                severity="HIGH",
                description="Non-root policy expected but no Dockerfile sets USER 10001:10001.",
                evidence=[],
            ))

    # Tini presence
    expects_tini = re.search(r"\btini\b", phase_text, re.I) is not None
    if expects_tini and dockerfiles:
        tini_ev: List[Evidence] = []
        pattern_entry = re.compile(r"ENTRYPOINT\s+\[.*tini.*\]|tini\s+--", re.I)
        for p, txt in docker_texts.items():
            for ln, sn in lines_with_regex(txt, pattern_entry):
                tini_ev.append(Evidence(str(p), ln, sn))
        if not tini_ev:
            findings.append(Finding(
                category="conflict",
                severity="HIGH",
                description="tini expected as PID 1 but not found in Dockerfile ENTRYPOINT.",
                evidence=[],
            ))

    # CUDA baseline
    expects_cuda = re.search(r"cuda\s*12\.1|cu121|TORCH_CUDA_ARCH_LIST", phase_text, re.I) is not None
    if expects_cuda and dockerfiles:
        cuda_ev: List[Evidence] = []
        for p, txt in docker_texts.items():
            for ln, sn in lines_with_regex(txt, re.compile(r"cuda\s*12\.1|cu121|TORCH_CUDA_ARCH_LIST", re.I)):
                cuda_ev.append(Evidence(str(p), ln, sn))
        if not cuda_ev:
            findings.append(Finding(
                category="misalignment",
                severity="MEDIUM",
                description="Phase expects CUDA 12.1/arch flags but Dockerfiles show no such config.",
                evidence=[],
            ))

    return findings


def _extract_bash_code_blocks(text: str) -> List[str]:
    blocks: List[str] = []
    # ```bash ... ``` or ```sh ... ``` or untyped fences
    fence = re.compile(r"```(?:bash|sh)?\n([\s\S]*?)\n```", re.I | re.M)
    for m in fence.finditer(text or ""):
        blocks.append(m.group(1))
    return blocks


def detect_missing_dependencies(phase_text: str, repo_root: Path) -> List[Finding]:
    findings: List[Finding] = []

    # Extract apt/pip installs ONLY from fenced bash/sh code blocks to reduce noise
    req_tokens: List[str] = []
    for block in _extract_bash_code_blocks(phase_text):
        for line in block.splitlines():
            m_apt = re.search(r"apt(?:-get)?\s+install\s+(.+)$", line.strip(), flags=re.I)
            if m_apt:
                pkgs = [p for p in re.split(r"\s+", m_apt.group(1)) if p and not p.startswith("-")]
                req_tokens.extend(pkgs)
            m_pip = re.search(r"pip\s+install\s+(.+)$", line.strip(), flags=re.I)
            if m_pip:
                pkgs = [p for p in re.split(r"\s+", m_pip.group(1)) if p and not p.startswith("-") and not p.startswith("-")]
                # skip -r requirements.txt patterns (handled via requirements files)
                if "-r" in line or "--requirement" in line:
                    continue
                req_tokens.extend(pkgs)

    req_tokens = [t for t in req_tokens if re.match(r"^[A-Za-z0-9_.+-]{2,}$", t)]
    req_tokens = list(dict.fromkeys(req_tokens))[:40]

    # Build sets of known deps from repo
    requirements_files = [p for p in iter_repo_files(repo_root) if p.name.lower().startswith("requirements")]
    pip_known: set[str] = set()
    for rf in requirements_files:
        try:
            for line in rf.read_text(encoding="utf-8", errors="ignore").splitlines():
                if line.strip() and not line.strip().startswith("#"):
                    pkg = re.split(r"[<>=\[]", line.strip())[0]
                    if pkg:
                        pip_known.add(pkg.lower())
        except Exception:
            continue

    apt_known: set[str] = set()
    for p in iter_repo_files(repo_root):
        if p.name == "Dockerfile" or p.suffix in {".sh", ".bash"}:
            try:
                text = p.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            for m in re.finditer(r"apt[- ]get\s+install\s+-y?\s+([^\n]+)", text, flags=re.I):
                pkgs = re.split(r"\s+", m.group(1).strip())
                for pkg in pkgs:
                    if pkg and not pkg.startswith("-"):
                        apt_known.add(pkg.lower())

    # Check missing
    for token in req_tokens:
        low = token.lower()
        if low in {"apt", "apt-get", "install", "pip"}:
            continue
        if low not in pip_known and low not in apt_known:
            findings.append(Finding(
                category="missing_dependency",
                severity="HIGH",
                description=f"Referenced dependency '{token}' not found in requirements or apt installs.",
                evidence=[],
            ))

    return findings


def detect_blind_spots(phase_text: str, repo_root: Path) -> List[Finding]:
    findings: List[Finding] = []
    # Example blind spots inferred from text
    patterns = {
        "health_endpoint": re.compile(r"/health", re.I),
        "rollback_prev_tag": re.compile(r"\bprev\b|FORCE_IMAGE_TAG", re.I),
        "observability_payload": re.compile(r"UnifiedObservabilityCenter|SBOM\s+digest|git\s+SHA", re.I),
    }

    file_cache: List[Tuple[Path, str]] = []
    for fp in iter_repo_files(repo_root):
        try:
            text = fp.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        file_cache.append((fp, text))

    def repo_has(pattern: re.Pattern[str]) -> bool:
        for _, txt in file_cache:
            if pattern.search(txt):
                return True
        return False

    for label, pat in patterns.items():
        if pat.search(phase_text) and not repo_has(pat):
            findings.append(Finding(
                category="blind_spot",
                severity="MEDIUM",
                description=f"Phase references '{label}' but repository lacks any obvious implementation.",
                evidence=[],
            ))

    return findings


# --------------------------- Phase Extraction -----------------------------

def load_tasks_from_args(tasks_file: Optional[str], tasks_json: Optional[str]) -> List[Dict[str, object]]:
    if not tasks_file and not tasks_json:
        raise SystemExit("Provide --tasks-file or --tasks-json")
    data: object
    if tasks_json:
        data = json.loads(tasks_json)
    else:
        path = Path(tasks_file)  # type: ignore[arg-type]
        if not path.exists():
            raise SystemExit(f"tasks file not found: {path}")
        data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and "tasks" in data:
        data = data["tasks"]  # legacy wrapper
    if not isinstance(data, list):
        raise SystemExit("tasks JSON must be a list of task objects")
    return data  # type: ignore[return-value]


def get_phase_text(tasks: List[Dict[str, object]], phase_index: int) -> Tuple[str, str]:
    if not tasks:
        raise SystemExit("no tasks present in tasks JSON")
    task = tasks[0]
    todos = task.get("todos", []) if isinstance(task, dict) else []
    if not isinstance(todos, list) or phase_index < 0 or phase_index >= len(todos):
        raise SystemExit(f"invalid phase index: {phase_index}")
    td = todos[phase_index]
    if not isinstance(td, dict):
        raise SystemExit("todo item is not an object")
    text = str(td.get("text", ""))
    # title is first line
    title = (text.splitlines()[0] if text.strip() else f"PHASE {phase_index}").strip()
    return title, text


# --------------------------- Main -----------------------------------------

def analyze_phase(tasks: List[Dict[str, object]], phase_index: int, repo_root: Path) -> Dict[str, object]:
    title, text = get_phase_text(tasks, phase_index)
    findings: List[Finding] = []

    # Detectors
    try:
        findings.extend(detect_semantic_duplicates(text, repo_root))
    except Exception:
        pass
    try:
        findings.extend(detect_architectural_conflicts(text, repo_root))
    except Exception:
        pass
    try:
        findings.extend(detect_missing_dependencies(text, repo_root))
    except Exception:
        pass
    try:
        findings.extend(detect_blind_spots(text, repo_root))
    except Exception:
        pass

    return {
        "phase_index": phase_index,
        "title": title,
        "findings": [f.to_json() for f in findings],
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Pre-Execution Analyzer (single-phase)")
    ap.add_argument("--tasks-file", help="Path to tasks_active.json", default=None)
    ap.add_argument("--tasks-json", help="Raw JSON content of tasks_active.json", default=None)
    ap.add_argument("--phase-index", type=int, required=True, help="Phase index to analyze (0-based)")
    ap.add_argument("--repo-root", required=True, help="Path to repository root")
    ap.add_argument("--output", help="Optional output JSON file path", default=None)
    args = ap.parse_args()

    tasks = load_tasks_from_args(args.tasks_file, args.tasks_json)
    repo_root = Path(args.repo_root)
    if not repo_root.exists():
        raise SystemExit(f"repo root not found: {repo_root}")

    report = analyze_phase(tasks, args.phase_index, repo_root)
    out_text = json.dumps(report, indent=2, ensure_ascii=False)
    if args.output:
        Path(args.output).write_text(out_text, encoding="utf-8")
    print(out_text)


if __name__ == "__main__":
    main()

