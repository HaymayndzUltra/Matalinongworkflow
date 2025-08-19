#!/usr/bin/env python3
# analysis_advanced_check.py
import argparse, json, os, re, math, itertools
from collections import Counter, defaultdict
from typing import List, Dict, Tuple

SECTION_KEYS = ["Purpose:", "Scope:", "Checks:", "IMPORTANT NOTE:"]

def load_json(path: str) -> List[Dict]:
	if not os.path.exists(path):
		raise FileNotFoundError(f"File not found: {path}")
	with open(path, "r", encoding="utf-8") as f:
		return json.load(f)

def extract_phase_index(text: str) -> int:
	m = re.search(r"PHASE\s+(\d+):", text, flags=re.IGNORECASE)
	return int(m.group(1)) if m else -1

def has_section(text: str, marker: str) -> bool:
	return marker in text

def extract_findings(text: str) -> List[Dict]:
	findings: List[Dict] = []
	# Capture blocks after "- Concern:" with subsequent Type/Similarity/Evidence
	pattern = re.compile(
		r"-\s*Concern:\s*(?P<concern>[^\n]+)\n\s*Type:\s*(?P<type>[^\n]+)\n\s*Similarity:\s*(?P<sim>[0-9.]+)\n\s*Evidence:\s*(?P<evidence>(?:\n\s*-\s*[^\n]+)+)",
		re.IGNORECASE
	)
	for m in pattern.finditer(text):
		ev_lines = [ln.strip()[2:].strip() for ln in m.group("evidence").strip().splitlines() if ln.strip().startswith("-")]
		findings.append({
			"concern": m.group("concern").strip(),
			"type": m.group("type").strip(),
			"similarity": float(m.group("sim")),
			"evidence": ev_lines,
		})
	return findings

def normalize(text: str) -> List[str]:
	text = text.lower()
	text = re.sub(r"[^\w\s]+", " ", text)
	tokens = [t for t in text.split() if len(t) > 2]
	# Minimal stoplist
	stop = {"the","and","for","with","that","this","are","not","only","but","also","when","from","into","your","their","have","has","had","will","shall","must","should","could","would","can"}
	return [t for t in tokens if t not in stop]

def bow(text: str) -> Counter:
	return Counter(normalize(text))

def cosine(a: Counter, b: Counter) -> float:
	if not a or not b:
		return 0.0
	keys = set(a) | set(b)
	num = sum(a[k]*b[k] for k in keys)
	da = math.sqrt(sum(v*v for v in a.values()))
	db = math.sqrt(sum(v*v for v in b.values()))
	return 0.0 if da == 0 or db == 0 else num/(da*db)

def phase_summary(todo: Dict) -> Dict:
	text = todo.get("text","")
	phase = extract_phase_index(text)
	sections_present = {k: has_section(text, k) for k in SECTION_KEYS}
	findings = extract_findings(text)
	return {
		"phase": phase,
		"sections_present": sections_present,
		"findings": findings,
		"text": text,
		"bow": bow(text),
	}

def status_for_phase(p: Dict) -> Tuple[str, List[str]]:
	missing = [name for name, present in p["sections_present"].items() if not present]
	conflicts = [f["concern"] for f in p["findings"] if f["type"].lower() == "conflict"]
	fail_reasons = []
	if "Purpose:" in missing: fail_reasons.append("Missing Purpose")
	if "Scope:" in missing: fail_reasons.append("Missing Scope")
	if "Checks:" in missing: fail_reasons.append("Missing Checks")
	if "IMPORTANT NOTE:" in missing: fail_reasons.append("Missing ImportantNote")
	if conflicts: fail_reasons.append("Conflicts in Findings: " + ", ".join(conflicts))
	return ("FAIL" if fail_reasons else "PASS", fail_reasons)

def cross_phase_similarity(phases: List[Dict], dup_threshold=0.80, overlap_threshold=0.55):
	pairs = []
	for a, b in itertools.combinations(sorted(phases, key=lambda x: x["phase"]), 2):
		sim = cosine(a["bow"], b["bow"])
		tag = "none"
		if sim >= dup_threshold: tag = "duplicate"
		elif sim >= overlap_threshold: tag = "overlap"
		if tag != "none":
			pairs.append({"a": a["phase"], "b": b["phase"], "similarity": round(sim, 2), "type": tag})
	return pairs

def concern_collisions(phases: List[Dict]) -> Dict[str, List[Tuple[int, str]]]:
	by_concern = defaultdict(list)
	for p in phases:
		for f in p["findings"]:
			by_concern[f["concern"]].append((p["phase"], f["type"]))
	return {k: v for k, v in by_concern.items() if len(v) > 1}

def main():
	ap = argparse.ArgumentParser()
	ap.add_argument("--file", default="/workspace/memory-bank/queue-system/analysis_active.json")
	ap.add_argument("--dup", type=float, default=0.80)
	ap.add_argument("--ovl", type=float, default=0.55)
	args = ap.parse_args()

	data = load_json(args.file)
	if not data:
		raise SystemExit("Empty analysis file.")
	task = data[0]
	todos = task.get("todos", [])

	phases = [phase_summary(td) for td in todos]
	phase_status = [(p["phase"],) + status_for_phase(p) for p in phases]

	# Cross-phase signals
	pairwise = cross_phase_similarity(phases, dup_threshold=args.dup, overlap_threshold=args.ovl)
	collisions = concern_collisions(phases)

	# Print STRICT ANALYSIS SUMMARY
	print("STRICT ANALYSIS SUMMARY")
	blockers = []
	for k, status, reasons in sorted(phase_status, key=lambda x: x[0]):
		missing = [r for r in reasons if r.startswith("Missing")]
		conf = [r for r in reasons if r.startswith("Conflicts")]
		line = f"Phase {k} — {status}"
		if missing:
			line += " — Missing:[" + "|".join(missing) + "]"
		if conf:
			line += " — Conflicts:[" + "|".join(conf) + "]"
		print(line)
		if status == "FAIL":
			blockers.append(f"Phase {k}: " + "; ".join(reasons))

	if pairwise:
		print("\nCROSS-PHASE SIMILARITIES (≥ thresholds)")
		for pr in pairwise:
			print(f"- {pr['type'].upper()}: Phase {pr['a']} vs {pr['b']} — similarity {pr['similarity']}")

	if collisions:
		print("\nCONCERN COLLISIONS")
		for concern, uses in collisions.items():
			desc = ", ".join([f"Phase {ph}({tp})" for ph, tp in sorted(uses)])
			print(f"- {concern}: {desc}")
			blockers.append(f"Concern collision: {concern} → {desc}")

	if blockers:
		print("\nBLOCKERS:")
		for b in blockers:
			print(f"- {b}")
		print("\nBLOCK EXECUTION: Analysis failed; fix blockers before proceeding.")
	else:
		print("\nAll phases PASS. No blockers detected.")

if __name__ == "__main__":
	main()


