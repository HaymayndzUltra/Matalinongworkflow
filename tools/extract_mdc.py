#!/usr/bin/env python3
import argparse
import hashlib
import os
import re
import sys
from datetime import datetime, timezone, timedelta
from typing import List, Tuple, Set

CODE_BLOCK_PATTERN = re.compile(
    r'<code\s+class="text-sm\s+block\s+pr-3">\s*(.*?)\s*</code>',
    re.IGNORECASE | re.DOTALL,
)


def get_ph_time_iso() -> str:
    tz = timezone(timedelta(hours=8))
    return datetime.now(tz).isoformat()


def read_text(path: str) -> str:
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


def write_text(path: str, content: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)


def extract_code_blocks(md_text: str) -> List[str]:
    return [m.group(1).strip() for m in CODE_BLOCK_PATTERN.finditer(md_text) if m.group(1).strip()]


def slugify(text: str, max_len: int = 60) -> str:
    base = re.sub(r'\s+', ' ', text).strip().lower()
    # keep alnum, dash; convert spaces to dash
    base = base.replace('/', ' ')
    base = re.sub(r'[^a-z0-9\-\s]+', '', base)
    base = re.sub(r'\s+', '-', base)
    if not base:
        base = 'snippet'
    return base[:max_len].strip('-') or 'snippet'


def hash8(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()[:8]


def find_existing_files(dir_path: str) -> List[str]:
    if not os.path.isdir(dir_path):
        return []
    files = []
    for root, _, filenames in os.walk(dir_path):
        for name in filenames:
            if name.lower().endswith('.mdc'):
                files.append(os.path.join(root, name))
    return files


def build_existing_index(file_paths: List[str]) -> Tuple[Set[str], List[Tuple[str, str]]]:
    """Return (content_hashes, [(path, content)]) for quick membership checks and later substring checks."""
    content_hashes: Set[str] = set()
    files_with_content: List[Tuple[str, str]] = []
    for p in file_paths:
        try:
            txt = read_text(p)
            files_with_content.append((p, txt))
            content_hashes.add(hashlib.sha256(txt.encode('utf-8')).hexdigest())
        except Exception:
            # ignore unreadable
            continue
    return content_hashes, files_with_content


def snippet_exists(snippet: str, files_with_content: List[Tuple[str, str]]) -> bool:
    # direct substring presence check
    for _, content in files_with_content:
        if snippet in content:
            return True
    return False


def compose_mdc(snippet: str, source: str) -> str:
    created_at = get_ph_time_iso()
    header = (
        f"---\n"
        f"created_at: {created_at}\n"
        f"source: {source}\n"
        f"snippet_sha256: {hashlib.sha256(snippet.encode('utf-8')).hexdigest()}\n"
        f"---\n\n"
    )
    body = (
        f"Extracted snippet from {source} on {created_at} (PH +08:00).\n\n"
        f"```\n{snippet}\n```\n"
    )
    return header + body


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description='Extract <code class="text-sm block pr-3">...</code> blocks and create .mdc files if new.')
    parser.add_argument('--input', default='/workspace/harvested/try.md', help='Path to the input markdown file')
    parser.add_argument('--output-dir', default='/workspace/harvested', help='Directory where .mdc files are stored/created')
    parser.add_argument('--apply', action='store_true', help='Actually write files (otherwise dry-run)')
    args = parser.parse_args()

    input_path = os.path.abspath(args.input)
    output_dir = os.path.abspath(args.output_dir)

    if not os.path.isfile(input_path):
        print(f"ERROR: Input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    md_text = read_text(input_path)
    snippets = extract_code_blocks(md_text)

    if not snippets:
        print("No matching <code class=\"text-sm block pr-3\"> blocks found.")
        sys.exit(0)

    existing_files = find_existing_files(output_dir)
    _, files_with_content = build_existing_index(existing_files)

    created = 0
    skipped = 0
    planned: List[str] = []

    # Track per-run deduplication to avoid writing the same snippet twice in one execution
    seen_in_run: Set[str] = set()

    for idx, snippet in enumerate(snippets, start=1):
        s_hash = hashlib.sha256(snippet.encode('utf-8')).hexdigest()
        if s_hash in seen_in_run:
            skipped += 1
            continue
        seen_in_run.add(s_hash)

        if snippet_exists(snippet, files_with_content):
            skipped += 1
            continue

        slug = slugify(snippet)
        fname = f"{slug}-{hash8(snippet)}.mdc"
        out_path = os.path.join(output_dir, fname)
        planned.append(out_path)
        if args.apply:
            ensure_dir(output_dir)
            content = compose_mdc(snippet, source=input_path)
            write_text(out_path, content)
            created += 1

    print(f"Input: {input_path}")
    print(f"Output dir: {output_dir}")
    print(f"Snippets found: {len(snippets)}")
    print(f"Existing .mdc files scanned: {len(existing_files)}")
    print(f"Will create: {len(planned)} (apply={args.apply})")
    if planned:
        print("Planned new files:")
        for p in planned:
            print(f" - {p}")
    if args.apply:
        print(f"Created: {created}, Skipped (existing/duplicate): {skipped}")


if __name__ == '__main__':
    main()