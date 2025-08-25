#!/usr/bin/env python3
import re, sys, os
from pathlib import Path

SRC = Path(sys.argv[1] if len(sys.argv) > 1 else "")
if not SRC or not SRC.exists():
    print("Usage: split_harvest.py /path/to/all_rules.txt", file=sys.stderr)
    sys.exit(1)

# Output roots
MIRROR_ROOT = Path("rules_out/split")
PROJECT_RULES = Path(".cursor/rules")

# Mapping (keyword → (bucket, globs, base))
MAP = [
    (r"\bdjango\b",                 ("framework/django",          "**/*.py",                           "django-general")),
    (r"\bfastapi\b",                ("framework/fastapi",         "**/*.py",                           "fastapi-general")),
    (r"\breact(-native)?\b|r3f|\bshadcn\b|\btailwind(-css)?\b", ("framework/react", "**/*.{jsx,tsx,css,scss,html,vue}", "react-general")),
    (r"\bvue\b|\bnuxt\b",          ("framework/vue",             "**/*.vue",                          "vue-general")),
    (r"\bnode(js)?\b",             ("platform/nodejs",           "**/*.{js,mjs,cjs,ts}",              "nodejs-general")),
    (r"\btypescript\b",            ("language/typescript",       "**/*.ts",                           "typescript-general")),
    (r"\bpython\b",                ("language/python",           "**/*.py",                           "python-general")),
    (r"\bphp\b|\blaravel\b",       ("framework/laravel",         "**/*.php",                          "laravel-general")),
    (r"\bwordpress\b",             ("framework/wordpress",       "**/*.php",                          "wordpress-general")),
    (r"\bdrupal\b",                ("framework/drupal",          "**/*.php",                          "drupal-general")),
    (r"\bgolang\b|\bgo\b",         ("language/golang",           "**/*.go",                           "golang-general")),
    (r"\brust\b",                  ("language/rust",             "**/*.rs",                           "rust-general")),
    (r"\bterraform\b",             ("domain/devops/terraform",   "**/*.tf",                           "terraform-general")),
    (r"\btesting\b|\bqa\b|test-case", ("domain/testing",        "**/*.{spec,test}.{js,ts,tsx,py}",    "testing-general")),
    (r"\bserverless\b",            ("domain/devops/serverless",  "**/*",                              "serverless-general")),
    (r"\btooling\b|\bdevops\b",    ("domain/devops/tooling",     "**/*",                              "tooling-general")),
]

ANCHOR_RE = re.compile(
    r"(?im)^(?:"
    r".+\.mdc$|"                                 # filename lines ending .mdc
    r"(?:rules\s+for|rules-for-|you\s+are\s+an\s+expert|overview|test-case|write\s+code|this\s+comprehensive\s+guide)|"
    r"(?:#{1,2}\s+.+)"                           # markdown headings
    r")"
)

def slugify(title: str) -> str:
    s = title.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    s = re.sub(r"-{2,}", "-", s)
    # Limit length to avoid filename too long errors
    if len(s) > 50:
        s = s[:50].rstrip("-")
    return s

def pick_map(title: str) -> tuple[str, str, str]:
    t = title.lower()
    for pat, (bucket, globs, base) in MAP:
        if re.search(pat, t):
            return bucket, globs, base
    return "general", "**/*", "general"

def derive_title(line: str) -> str:
    l = line.strip().lstrip("#").strip()
    l = re.sub(r"\.mdc$", "", l, flags=re.I)
    l = re.sub(r"[-_]{2,}", " ", l)
    l = re.sub(r"you are an expert in|you are an expert|rules for|overview|test-case|write code", "", l, flags=re.I)
    l = re.sub(r"\s+", " ", l).strip()
    if not l:
        l = "General Rules"
    
    # Limit title length to avoid extremely long titles
    if len(l) > 100:
        l = l[:100] + "..."
    
    # Title-case but keep common acronyms
    words = []
    for w in l.split():
        if w.upper() in {"API","ORM","PHP","JS","TS","CSS","HTML","Vue","Nuxt","React","Next","Django","FastAPI","Laravel","WordPress","Drupal","Golang","Rust","Terraform","TypeScript","JavaScript","NodeJS","Python","Testing","QA","DevOps","Serverless","Tooling"}:
            words.append(w.upper())
        else:
            words.append(w.capitalize())
    return " ".join(words)

text = SRC.read_text(encoding="utf-8", errors="ignore")

# Find anchors
indices = [m.start() for m in ANCHOR_RE.finditer(text)]
if not indices:
    # fallback: split by double blank lines
    chunks = [c for c in re.split(r"\n\s*\n\s*\n+", text) if c.strip()]
    anchor_lines = [c.splitlines()[0] if c.splitlines() else "General Rules" for c in chunks]
else:
    indices.append(len(text))
    chunks = []
    anchor_lines = []
    for i in range(len(indices)-1):
        block = text[indices[i]:indices[i+1]]
        chunks.append(block)
        first_line = block.splitlines()[0] if block.splitlines() else "General Rules"
        anchor_lines.append(first_line)

# Ensure output dirs
MIRROR_ROOT.mkdir(parents=True, exist_ok=True)
PROJECT_RULES.mkdir(parents=True, exist_ok=True)

report = []
for block, anchor in zip(chunks, anchor_lines):
    content = block.strip()
    if len(content) < 5:
        continue
    title = derive_title(anchor)
    bucket, globs, base = pick_map(title)
    base_slug = slugify(title if title else base)
    fname = f"{base_slug}.mdc"

    # Choose targets
    mirror_dir = MIRROR_ROOT / bucket
    proj_dir = PROJECT_RULES / bucket
    mirror_dir.mkdir(parents=True, exist_ok=True)
    proj_dir.mkdir(parents=True, exist_ok=True)

    # handle duplicates
    def next_path(d: Path, name: str) -> Path:
        p = d / name
        if not p.exists():
            return p
        stem = p.stem
        suf = p.suffix
        n = 2
        while True:
            q = d / f"{stem}-{n}{suf}"
            if not q.exists():
                return q
            n += 1

    mirror_path = next_path(mirror_dir, fname)
    proj_path   = next_path(proj_dir, fname)

    # detect existing frontmatter
    has_fm = bool(re.match(r"^\s*---\s*\n", content))
    if has_fm:
        # patch missing fields
        m = re.match(r"(?s)^\s*---\s*(.*?)\s*---\s*(.*)$", content)
        if m:
            fm, body = m.groups()
            if "description:" not in fm:
                fm += f'\ndescription: "Guidelines for {title}."'
            if "globs:" not in fm:
                fm += f'\nglobs: "{globs}"'
            if "alwaysApply:" not in fm:
                fm += f'\nalwaysApply: false'
            final = f"---\n{fm}\n---\n# {title}\n\n{body.strip()}\n"
        else:
            final = f"""---
description: "Guidelines for {title}."
globs: "{globs}"
alwaysApply: false
---

# {title}

{content}
"""
    else:
        final = f"""---
description: "Guidelines for {title}."
globs: "{globs}"
alwaysApply: false
---

# {title}

{content}
"""

    mirror_path.write_text(final, encoding="utf-8")
    proj_path.write_text(final, encoding="utf-8")
    report.append((title, bucket, globs, str(mirror_path), str(proj_path)))

# Print summary
print(f"{'Title':50} | {'Bucket':30} | {'Globs':25} | Mirror Path")
print("-"*140)
for t,b,g,m,_ in report:
    print(f"{t[:50]:50} | {b[:30]:30} | {g[:25]:25} | {m}")
print(f"\nTotal files: {len(report)}")
