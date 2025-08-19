#!/usr/bin/env python3
"""
analyzer.py — Phase-by-phase Pre-Execution Analysis (auto repo-root detection)

Purpose
  Analyze a single phase (index K) from tasks_active.json against the repository
  to detect semantic duplicates, architectural conflicts, codebase misalignment,
  missing dependencies, and blind spots. Outputs a structured JSON report.

Key features
  - Auto-detects repository root (walks upward for memory-bank/queue-system/tasks_active.json;
    falls back to git top-level; then CWD)
  - Defaults tasks file to <repo_root>/memory-bank/queue-system/tasks_active.json
  - Proactive mode performs repo-wide audits (CI policies, port collisions, global Dockerfile policies)

CLI
  python3 analyzer.py --phase-index K [--proactive]
  python3 analyzer.py --tasks-file /abs/tasks_active.json --phase-index K --repo-root /abs/repo
  python3 analyzer.py --tasks-json "$(cat tasks_active.json)" --phase-index K --repo-root /abs/repo

Output JSON schema
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
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import subprocess
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


# --------------------------- Repo Root Detection ---------------------------

def _find_root_with_tasks(start: Path) -> Optional[Path]:
    cur = start.resolve()
    while True:
        if (cur / "memory-bank" / "queue-system" / "tasks_active.json").exists():
            return cur
        if cur.parent == cur:
            break
        cur = cur.parent
    return None


def _detect_repo_root() -> Path:
    # 1) CWD → upwards
    cwd = Path.cwd()
    root = _find_root_with_tasks(cwd)
    if root:
        return root
    # 2) analyzer.py location → upwards
    here = Path(__file__).resolve().parent
    root = _find_root_with_tasks(here)
    if root:
        return root
    # 3) git top-level
    try:
        top = subprocess.check_output(["git", "rev-parse", "--show-toplevel"], stderr=subprocess.DEVNULL).decode().strip()
        root = _find_root_with_tasks(Path(top))
        if root:
            return root
    except Exception:
        pass
    # 4) fallback to cwd
    return cwd


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

    dockerfiles = [p for p, _ in file_cache if p.name == "Dockerfile"]
    docker_texts = {p: (p.read_text(encoding="utf-8", errors="ignore") if p.exists() else "") for p in dockerfiles}

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
    fence = re.compile(r"```(?:bash|sh)?\n([\s\S]*?)\n```", re.I | re.M)
    for m in fence.finditer(text or ""):
        blocks.append(m.group(1))
    return blocks


def detect_missing_dependencies(phase_text: str, repo_root: Path) -> List[Finding]:
    findings: List[Finding] = []

    # Extract apt/pip installs ONLY from fenced bash/sh code blocks
    req_tokens: List[str] = []
    for block in _extract_bash_code_blocks(phase_text):
        for line in block.splitlines():
            m_apt = re.search(r"apt(?:-get)?\s+install\s+(.+)$", line.strip(), flags=re.I)
            if m_apt:
                pkgs = [p for p in re.split(r"\s+", m_apt.group(1)) if p and not p.startswith("-")]
                req_tokens.extend(pkgs)
            m_pip = re.search(r"pip\s+install\s+(.+)$", line.strip(), flags=re.I)
            if m_pip:
                if "-r" in line or "--requirement" in line:
                    continue
                pkgs = [p for p in re.split(r"\s+", m_pip.group(1)) if p and not p.startswith("-")]
                req_tokens.extend(pkgs)

    req_tokens = [t for t in req_tokens if re.match(r"^[A-Za-z0-9_.+-]{2,}$", t)]
    req_tokens = list(dict.fromkeys(req_tokens))[:40]

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
            pass

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


def detect_ci_policy_gaps(phase_text: str, repo_root: Path) -> List[Finding]:
    findings: List[Finding] = []
    workflows_dir = repo_root / ".github" / "workflows"
    expects_trivy = re.search(r"trivy|HIGH/CRITICAL|severity", phase_text, re.I) is not None
    expects_sbom = re.search(r"sbom|spdx|syft", phase_text, re.I) is not None
    expects_tags = re.search(r"ghcr\.io|YYYYMMDD-<git_sha>", phase_text, re.I) is not None

    if workflows_dir.exists():
        texts: List[Tuple[Path, str]] = []
        for fp in workflows_dir.glob("**/*"):
            if fp.is_file() and fp.suffix in {".yml", ".yaml"}:
                try:
                    texts.append((fp, fp.read_text(encoding="utf-8", errors="ignore")))
                except Exception:
                    pass
        def any_match(pat: re.Pattern[str]) -> List[Evidence]:
            ev: List[Evidence] = []
            for p, t in texts:
                for ln, sn in lines_with_regex(t, pat):
                    ev.append(Evidence(str(p), ln, sn[:200]))
            return ev
        if expects_trivy:
            ev = any_match(re.compile(r"trivy|aquasecurity/trivy-action|severity|exit-code", re.I))
            if not ev:
                findings.append(Finding(
                    category="misalignment",
                    severity="MEDIUM",
                    description="CI missing Trivy or severity-gated config.",
                    evidence=[],
                ))
        if expects_sbom:
            ev = any_match(re.compile(r"syft|sbom|spdx|anchore/sbom-action", re.I))
            if not ev:
                findings.append(Finding(
                    category="misalignment",
                    severity="MEDIUM",
                    description="CI missing SBOM generation (syft/SPDX).",
                    evidence=[],
                ))
        if expects_tags:
            ev = any_match(re.compile(r"ghcr\.io|\bYYYYMMDD-[0-9a-f]{7,}\b", re.I))
            if not ev:
                findings.append(Finding(
                    category="misalignment",
                    severity="LOW",
                    description="CI missing GHCR tag scheme references (date+git).",
                    evidence=[],
                ))
    else:
        if any([expects_trivy, expects_sbom, expects_tags]):
            findings.append(Finding(
                category="misalignment",
                severity="LOW",
                description=".github/workflows not found but plan expects CI security/SBOM/tag policies.",
                evidence=[],
            ))
    return findings


def detect_port_collisions(repo_root: Path) -> List[Finding]:
    findings: List[Finding] = []
    compose = repo_root / "docker-compose.yml"
    if not compose.exists():
        return findings
    try:
        text = compose.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return findings
    host_ports: Dict[str, List[int]] = {}
    current_service: Optional[str] = None
    for line in text.splitlines():
        if re.match(r"^[A-Za-z0-9_.-]+:\s*$", line.strip()):
            current_service = line.strip().split(":")[0]
        m = re.search(r"-\s*\"?(\d{2,5}):\d{2,5}\"?", line)
        if m:
            port = int(m.group(1))
            host_ports.setdefault(str(port), []).append(port)
    duplicates = [int(p) for p, lst in host_ports.items() if len(lst) > 1]
    if duplicates:
        findings.append(Finding(
            category="conflict",
            severity="HIGH",
            description=f"docker-compose host port collisions detected: {sorted(set(duplicates))}",
            evidence=[Evidence(str(compose), 1, "host:container port duplicates present")],
        ))
    return findings


def detect_global_docker_policies(repo_root: Path, require_nonroot: bool, require_tini: bool) -> List[Finding]:
    findings: List[Finding] = []
    dockerfiles = list(p for p in iter_repo_files(repo_root) if p.name == "Dockerfile")
    if not dockerfiles:
        return findings
    if require_nonroot:
        offenders: List[str] = []
        for p in dockerfiles:
            try:
                txt = p.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            if not re.search(r"^\s*USER\s+10001(?::10001)?\b", txt, re.I | re.M):
                offenders.append(str(p))
        if offenders:
            findings.append(Finding(
                category="conflict",
                severity="HIGH",
                description="Some Dockerfiles do not enforce non-root USER 10001:10001.",
                evidence=[Evidence(path=o, line=1, snippet="USER missing") for o in offenders[:8]],
            ))
    if require_tini:
        offenders: List[str] = []
        for p in dockerfiles:
            try:
                txt = p.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            if not re.search(r"ENTRYPOINT\s+\[.*tini.*\]|tini\s+--", txt, re.I):
                offenders.append(str(p))
        if offenders:
            findings.append(Finding(
                category="conflict",
                severity="HIGH",
                description="Some Dockerfiles do not use tini as PID 1.",
                evidence=[Evidence(path=o, line=1, snippet="tini missing") for o in offenders[:8]],
            ))
    return findings


def analyze_phase(tasks: List[Dict[str, object]], phase_index: int, repo_root: Path, proactive: bool = False) -> Dict[str, object]:
    title, text = get_phase_text(tasks, phase_index)
    findings: List[Finding] = []

    # Detectors (phase-scoped)
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

    # Proactive repo-wide audits (policy/ports/CI) when enabled
    if proactive:
        try:
            findings.extend(detect_ci_policy_gaps(text, repo_root))
        except Exception:
            pass
        try:
            findings.extend(detect_port_collisions(repo_root))
        except Exception:
            pass
        try:
            require_nr = re.search(r"non[- ]root|uid:gid|user\s+10001", text, re.I) is not None
            require_tini = re.search(r"\btini\b", text, re.I) is not None
            if require_nr or require_tini:
                findings.extend(detect_global_docker_policies(repo_root, require_nr, require_tini))
        except Exception:
            pass

    # De-duplicate similar findings by (category, severity, description)
    bucket: Dict[Tuple[str, str, str], List[Evidence]] = {}
    for f in findings:
        key = (f.category, f.severity, f.description)
        if key not in bucket:
            bucket[key] = []
        # merge evidence (dedupe by path+line)
        seen = {(e.path, e.line) for e in bucket[key]}
        for ev in f.evidence:
            if (ev.path, ev.line) not in seen:
                bucket[key].append(ev)
                seen.add((ev.path, ev.line))

    final_findings: List[Dict[str, object]] = []
    for (cat, sev, desc), evs in bucket.items():
        final_findings.append(Finding(category=cat, severity=sev, description=desc, evidence=evs).to_json())

    return {
        "phase_index": phase_index,
        "title": title,
        "findings": final_findings,
    }


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
        data = data["tasks"]
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
    title = (text.splitlines()[0] if text.strip() else f"PHASE {phase_index}").strip()
    return title, text


def main() -> None:
    ap = argparse.ArgumentParser(description="Pre-Execution Analyzer (single-phase)")
    ap.add_argument("--tasks-file", help="Path to tasks_active.json", default=None)
    ap.add_argument("--tasks-json", help="Raw JSON content of tasks_active.json", default=None)
    ap.add_argument("--phase-index", type=int, required=True, help="Phase index to analyze (0-based)")
    ap.add_argument("--repo-root", required=False, help="Path to repository root (auto-detected if omitted)")
    ap.add_argument("--output", help="Optional output JSON file path", default=None)
    ap.add_argument("--proactive", action="store_true", help="Enable proactive repo-wide audits (CI, ports, global Dockerfile policies)")
    args = ap.parse_args()

    repo_root = Path(args.repo_root) if args.repo_root else _detect_repo_root()
    if not repo_root.exists():
        raise SystemExit(f"repo root not found: {repo_root}")

    tasks = load_tasks_from_args(args.tasks_file or str(repo_root / "memory-bank" / "queue-system" / "tasks_active.json"), args.tasks_json)

    report = analyze_phase(tasks, args.phase_index, repo_root, proactive=args.proactive)
    out_text = json.dumps(report, indent=2, ensure_ascii=False)
    if args.output:
        Path(args.output).write_text(out_text, encoding="utf-8")
    print(out_text)


if __name__ == "__main__":
    main()

