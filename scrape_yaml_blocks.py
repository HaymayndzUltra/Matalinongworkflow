#!/usr/bin/env python3
import asyncio
import re
import sys
import os
import argparse
import hashlib
from urllib.parse import urljoin, urlparse
from typing import Set, List, Optional

import aiohttp
from aiohttp import ClientSession
from bs4 import BeautifulSoup

YAML_BLOCK_RE = re.compile(r"^---\s*[\r\n]+(.*?\bdescription:\b.*?\balwaysApply:\b.*?)[\r\n]+---\s*$",
                           re.DOTALL | re.MULTILINE | re.IGNORECASE)

CODE_CANDIDATE_SELECTORS = [
    "pre code",
    "code",
    "pre",
    "[class*=code]",
    "[class*=Code]",
    "[class*=copy]",
    "article",
    "main",
]

DEFAULT_HEADERS = {
    "User-Agent": "yaml-scraper/1.0 (+https://example.com)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def normalize_url(base: str, link: str) -> Optional[str]:
    try:
        url = urljoin(base, link)
        parsed = urlparse(url)
        if parsed.scheme in {"http", "https"}:
            # strip fragments
            return parsed._replace(fragment="").geturl()
    except Exception:
        return None
    return None


def allowed(url: str, includes: List[str], excludes: List[str]) -> bool:
    if includes:
        if not any(inc in url for inc in includes):
            return False
    if any(exc in url for exc in excludes):
        return False
    return True


async def fetch(session: ClientSession, url: str, timeout: int) -> Optional[str]:
    try:
        async with session.get(url, timeout=timeout) as resp:
            if resp.status == 200 and "text/html" in resp.headers.get("Content-Type", ""):
                return await resp.text()
    except Exception:
        return None
    return None


def extract_yaml_blocks(html: str) -> List[str]:
    soup = BeautifulSoup(html, "html.parser")
    texts = []
    # Pull visible text from likely code/text containers
    for sel in CODE_CANDIDATE_SELECTORS:
        for node in soup.select(sel):
            txt = node.get_text("\n", strip=False)
            if txt:
                texts.append(txt)
    # fallback to whole-page text (last)
    texts.append(soup.get_text("\n", strip=False))

    blocks = []
    for t in texts:
        for m in YAML_BLOCK_RE.finditer(t):
            block_body = m.group(1).strip()
            # Re-wrap with --- ... ---
            blocks.append(f"---\n{block_body}\n---\n")
    return dedupe(blocks)


def dedupe(items: List[str]) -> List[str]:
    seen = set()
    out = []
    for it in items:
        h = hashlib.sha256(it.encode("utf-8")).hexdigest()
        if h not in seen:
            seen.add(h)
            out.append(it)
    return out


def safe_filename(text: str) -> str:
    h = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
    return f"rule_{h}.mdc"


async def crawl(start_urls: List[str],
                include: List[str],
                exclude: List[str],
                max_pages: int,
                concurrency: int,
                timeout: int,
                outdir: str) -> None:
    os.makedirs(outdir, exist_ok=True)
    seen: Set[str] = set()
    q = asyncio.Queue()
    for u in start_urls:
        await q.put(u)

    async with aiohttp.ClientSession(headers=DEFAULT_HEADERS) as session:
        sem = asyncio.Semaphore(concurrency)
        found_count = 0
        page_count = 0

        async def worker():
            nonlocal found_count, page_count
            while True:
                try:
                    url = await q.get()
                except asyncio.CancelledError:
                    return
                if url in seen or page_count >= max_pages:
                    q.task_done()
                    continue
                seen.add(url)
                page_count += 1
                async with sem:
                    html = await fetch(session, url, timeout)
                if html:
                    blocks = extract_yaml_blocks(html)
                    for b in blocks:
                        fname = safe_filename(b)
                        path = os.path.join(outdir, fname)
                        with open(path, "w", encoding="utf-8") as f:
                            f.write(b)
                        found_count += 1
                    # enqueue links
                    soup = BeautifulSoup(html, "html.parser")
                    for a in soup.find_all("a", href=True):
                        nxt = normalize_url(url, a["href"])
                        if not nxt:
                            continue
                        if nxt in seen:
                            continue
                        if allowed(nxt, include, exclude):
                            await q.put(nxt)
                q.task_done()

        workers = [asyncio.create_task(worker()) for _ in range(concurrency)]
        await q.join()
        for w in workers:
            w.cancel()
        # Summary
        print(f"Pages scanned: {page_count}, YAML blocks saved: {found_count}, Output: {outdir}")


def parse_args():
    ap = argparse.ArgumentParser(description="Scrape YAML front-matter blocks containing description: and alwaysApply:.")
    start = ap.add_mutually_exclusive_group(required=False)
    start.add_argument("--start", help="Start URL to crawl")
    start.add_argument("--urls", help="Path to file with one URL per line")
    ap.add_argument("--include", nargs="*", default=[], help="Only crawl URLs containing these substrings")
    ap.add_argument("--exclude", nargs="*", default=[], help="Exclude URLs containing these substrings")
    ap.add_argument("--max-pages", type=int, default=200, help="Max pages to scan")
    ap.add_argument("--concurrency", type=int, default=8, help="Concurrent requests")
    ap.add_argument("--timeout", type=int, default=20, help="Request timeout seconds")
    ap.add_argument("--out", default="rules_out", help="Output directory for .mdc files")
    return ap.parse_args()


def load_start_urls(args) -> List[str]:
    urls = []
    if args.start:
        urls = [args.start]
    elif args.urls:
        with open(args.urls, "r", encoding="utf-8") as f:
            urls = [ln.strip() for ln in f if ln.strip()]
    else:
        print("Error: provide --start URL or --urls FILE", file=sys.stderr)
        sys.exit(2)
    return urls


def main():
    args = parse_args()
    start_urls = load_start_urls(args)
    asyncio.run(crawl(
        start_urls=start_urls,
        include=args.include,
        exclude=args.exclude,
        max_pages=args.max_pages,
        concurrency=args.concurrency,
        timeout=args.timeout,
        outdir=args.out,
    ))


if __name__ == "__main__":
    main()
