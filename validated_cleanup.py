#!/usr/bin/env python3
import argparse, os, sys, json, subprocess, shlex, time
from pathlib import Path
from typing import List, Dict


SAFE_DIR_RULES = {
	"D1_CACHE_DIRS": {"names": ["__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".ipynb_checkpoints"]},
	"D3_BUILD_DIRS": {"names": ["dist", "build", "coverage", "htmlcov"]},
	"D7_BACKUPS_DIRS": {"names": ["backups", "analysis_results", "analysis_output", "audits", "performance_analysis", "phase1_implementation/backups", "pc2_code/agents/backups"]},
}

SAFE_FILE_RULES = {
	"D1_CACHE_FILES": {"globs": ["*.pyc"]},
	"D4_TRANSIENT": {"globs": ["*.log", "*.tmp", "*.bak", "*.swp", "*~"]},
	"D7_OLDSESSION": {"globs": ["*oldsession*.md*", "*.md.save", "*.save"]},
	"D5_VENDOR": {"globs": ["get-pip.py", "legacy_report.json"]},
}

SOFT_RULES = {
	"S1_NODE_MODULES": {"paths": ["node_modules"]},
	"S2_LARGE_ASSETS": {"exts": [".wav", ".mp4", ".mov", ".zip", ".tar", ".tgz", ".gz", ".7z", ".jpg", ".jpeg", ".png", ".deb"], "min_bytes": 5*1024*1024},
}


def rg_exists() -> bool:
	return subprocess.call(["bash","-lc","command -v rg >/dev/null"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0


def run_rg(pattern: str, root: Path) -> str:
	cmd = f'rg -n -S --hidden --glob "!.git" {shlex.quote(pattern)} {shlex.quote(str(root))}'
	p = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
	return p.stdout or ""


def path_size(p: Path) -> int:
	if p.is_file():
		try:
			return p.stat().st_size
		except Exception:
			return 0
	total = 0
	for sub in p.rglob("*"):
		if sub.is_file():
			try:
				total += sub.stat().st_size
			except Exception:
				pass
	return total


def list_candidates(repo: Path, allow_node_modules: bool, include_large_assets: bool, large_min_bytes: int) -> List[Dict]:
	cands: List[Dict] = []

	# SAFE DIRS
	for rule, spec in SAFE_DIR_RULES.items():
		for name in spec["names"]:
			for p in repo.rglob(name):
				if p.is_dir():
					cands.append({"rule": rule, "path": str(p.relative_to(repo)), "type": "dir"})

	# SAFE FILES
	for rule, spec in SAFE_FILE_RULES.items():
		for g in spec["globs"]:
			for p in repo.rglob(g):
				if p.is_file():
					cands.append({"rule": rule, "path": str(p.relative_to(repo)), "type": "file"})

	# SOFT: node_modules at repo root only (tracked/checked)
	if allow_node_modules:
		nm = repo / "node_modules"
		if nm.exists() and nm.is_dir():
			cands.append({"rule": "S1_NODE_MODULES", "path": "node_modules", "type": "dir"})

	# SOFT: large assets
	if include_large_assets:
		exts = set(SOFT_RULES["S2_LARGE_ASSETS"]["exts"])
		for p in repo.rglob("*"):
			if p.is_file():
				try:
					sz = p.stat().st_size
				except Exception:
					sz = 0
				if p.suffix.lower() in exts and sz >= large_min_bytes:
					cands.append({"rule": "S2_LARGE_ASSETS", "path": str(p.relative_to(repo)), "type": "file"})

	# de-dup
	seen = set()
	uniq = []
	for c in cands:
		key = (c["rule"], c["path"])
		if key in seen:
			continue
		seen.add(key)
		uniq.append(c)
	return uniq


def ref_scan(repo: Path, rel_path: str) -> Dict:
	p = repo / rel_path
	name = p.name
	base = os.path.splitext(name)[0]
	patterns = []
	# include quoted path and filename/basename
	patterns.append(shlex.quote(rel_path))
	patterns.append(shlex.quote(name))
	if base and base != name:
		patterns.append(shlex.quote(base))
	hits = []
	code_exts = {".py", ".yml", ".yaml", ".toml", ".json", ".sh", ".bash", ".ini", ".cfg", ".conf"}
	if rg_exists():
		for pat in patterns:
			out = run_rg(pat, repo)
			if out:
				for line in out.splitlines():
					try:
						file_part = line.split(":", 1)[0]
						# skip self-hits inside the same path
						if (repo / file_part).resolve().is_relative_to(p.resolve()):
							continue
						# ignore references from .md docs and non-code files (except Dockerfile)
						fp = repo / file_part
						ext = fp.suffix.lower()
						if ext == ".md":
							continue
						if fp.name != "Dockerfile" and ext not in code_exts:
							continue
					except Exception:
						pass
					hits.append(line)
			if len(hits) >= 20:
				break
	return {"patterns": patterns, "hits": hits[:20], "hit_count": len(hits)}


def compile_check(repo: Path) -> bool:
	# AST-parse all Python files to avoid generating .pyc artifacts
	cmd = (
		"python3 - <<'PY'\n"
		"import ast, sys, pathlib\n"
		f"root = pathlib.Path({json.dumps(str(repo))})\n"
		"ok = True\n"
		"for p in root.rglob('*.py'):\n"
		"    try:\n"
		"        ast.parse(p.read_text(encoding='utf-8', errors='ignore'))\n"
		"    except Exception:\n"
		"        ok = False\n"
		"        print(f'AST_FAIL: {p}', file=sys.stderr)\n"
		"        break\n"
		"sys.exit(0 if ok else 2)\n"
		"PY"
	)
	return subprocess.call(["bash","-lc", cmd]) == 0


def main():
	ap = argparse.ArgumentParser()
	ap.add_argument("--repo", default="/workspace/voice-assistant-prod")
	ap.add_argument("--apply", action="store_true")
	ap.add_argument("--allow-node-modules", action="store_true")
	ap.add_argument("--include-large-assets", action="store_true")
	ap.add_argument("--large-min-bytes", type=int, default=5*1024*1024)
	ap.add_argument("--json-out", default="validated_cleanup_report.json")
	ap.add_argument("--md-out", default="validated_cleanup_report.md")
	args = ap.parse_args()

	repo = Path(args.repo).resolve()
	if not (repo.exists() and (repo / ".git").exists()):
		print(f"Repo not found: {repo}", file=sys.stderr)
		sys.exit(2)

	candidates = list_candidates(repo, args.allow_node_modules, args.include_large_assets, args.large_min_bytes)
	results = []

	for c in candidates:
		rel = c["path"]
		p = repo / rel
		size = path_size(p)
		ref = ref_scan(repo, rel)
		rule = c["rule"]
		auto_rules = set(SAFE_DIR_RULES.keys()) | set(SAFE_FILE_RULES.keys())
		auto = rule in auto_rules
		decision = "keep"
		reason = "has_references" if ref["hit_count"] > 0 else ("auto_rule_no_refs" if auto else "soft_rule_review")
		if args.apply and ref["hit_count"] == 0 and (auto or rule in {"S1_NODE_MODULES", "S2_LARGE_ASSETS"}):
			decision = "delete"
			try:
				target = repo / rel
				if target.is_dir():
					subprocess.run(["bash","-lc", f"git -C {shlex.quote(str(repo))} rm -r --ignore-unmatch -- {shlex.quote(rel)} || rm -rf -- {shlex.quote(str(target))}"], check=False)
				else:
					subprocess.run(["bash","-lc", f"git -C {shlex.quote(str(repo))} rm -f --ignore-unmatch -- {shlex.quote(rel)} || rm -f -- {shlex.quote(str(target))}"], check=False)
			except Exception as e:
				decision = f"error:{e}"

		results.append({
			"rule": rule,
			"path": rel,
			"type": c["type"],
			"size": size,
			"ref_hit_count": ref["hit_count"],
			"ref_samples": ref["hits"],
			"decision": decision,
			"reason": reason,
		})

	compile_ok = True
	if args.apply:
		compile_ok = compile_check(repo)

	with open(args.json_out, "w", encoding="utf-8") as f:
		json.dump({"repo": str(repo), "time": int(time.time()), "compile_ok": compile_ok, "entries": results}, f, indent=2)

	with open(args.md_out, "w", encoding="utf-8") as f:
		f.write("| Rule | Path | Type | Size(bytes) | RefHits | Decision | Reason |\n|---|---|---:|---:|---:|---|---|\n")
		for r in sorted(results, key=lambda x: (-int(x["decision"]=="delete"), -x["size"], x["path"])):
			f.write(f'| {r["rule"]} | {r["path"]} | {r["type"]} | {r["size"]} | {r["ref_hit_count"]} | {r["decision"]} | {r["reason"]} |\n')
		if args.apply:
			f.write(f"\nCompile after delete: {'PASS' if compile_ok else 'FAIL'}\n")

	print(f"Report: {args.json_out}\nSummary: {args.md_out}")
	if args.apply and not compile_ok:
		print("WARNING: Python compile check failed after deletions; review the report.")


if __name__ == "__main__":
	main()