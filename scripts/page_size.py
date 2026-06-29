#!/usr/bin/env python3
"""Post-build page size calculator for Hugo site.

Walks public/**/*.html, computes total page weight (HTML + local assets),
and substitutes %%PAGESIZE%% in each file with the result (e.g. "423.91 KB"
or "2.46 MB" for pages >= 1000 KB).

Usage:
    python3 scripts/page_size.py public/            # substitute sizes
    python3 scripts/page_size.py public/ --verify   # assert sizes are correct
    python3 scripts/page_size.py public/ --dry-run  # print sizes, no writes
"""

import argparse
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

PLACEHOLDER = b"%%PAGESIZE%%"
CSS_URL_RE = re.compile(r"""url\(\s*['"]?([^)'"]+?)['"]?\s*\)""")


class AssetCollector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls = []

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        if tag == "link":
            rel = (d.get("rel") or "").lower()
            if rel in ("stylesheet", "icon", "shortcut icon", "apple-touch-icon"):
                href = d.get("href")
                if href:
                    self.urls.append(href)
        elif tag in ("script", "img", "video", "audio", "iframe", "embed"):
            src = d.get("src")
            if src:
                self.urls.append(src)
            srcset = d.get("srcset")
            if srcset:
                self._add_srcset(srcset)
        elif tag == "source":
            src = d.get("src")
            if src:
                self.urls.append(src)
            srcset = d.get("srcset")
            if srcset:
                self._add_srcset(srcset)

    def _add_srcset(self, srcset):
        for part in srcset.split(","):
            tokens = part.strip().split()
            if tokens:
                self.urls.append(tokens[0])


def detect_base_path(public_dir):
    for name in ("hugo.toml", "config.toml", "hugo.yaml"):
        cfg = public_dir.parent / name
        if cfg.exists():
            m = re.search(r"""(?i)baseURL\s*=\s*['"]([^'"]+)['"]""", cfg.read_text())
            if m:
                return urlparse(m.group(1)).path.rstrip("/")
    return ""


def resolve_url(url, html_path, public_dir, base_path):
    if not url or url.startswith("data:"):
        return None
    parsed = urlparse(url)
    if parsed.scheme or url.startswith("//"):
        return None
    if url.startswith("/"):
        path = parsed.path
        if base_path and path.startswith(base_path + "/"):
            path = path[len(base_path):]
        resolved = public_dir / path.lstrip("/")
    else:
        resolved = html_path.parent / parsed.path
    resolved = resolved.resolve()
    try:
        resolved.relative_to(public_dir.resolve())
    except ValueError:
        return None
    return resolved if resolved.is_file() else None


def collect_css_assets(css_path, public_dir, base_path):
    """Return local asset paths referenced by url() in a CSS file (e.g. fonts)."""
    try:
        text = css_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return set()
    assets = set()
    for m in CSS_URL_RE.finditer(text):
        r = resolve_url(m.group(1).strip(), css_path, public_dir, base_path)
        if r is not None:
            assets.add(r)
    return assets


def page_weight(html_path, html_bytes, public_dir, base_path):
    collector = AssetCollector()
    collector.feed(html_bytes.decode("utf-8", errors="replace"))
    assets = set()
    for url in collector.urls:
        r = resolve_url(url, html_path, public_dir, base_path)
        if r is not None:
            assets.add(r)
            if r.suffix == ".css":
                assets.update(collect_css_assets(r, public_dir, base_path))
    total = len(html_bytes) + sum(p.stat().st_size for p in assets)
    return total, assets


def format_size(n):
    kb = n / 1024
    if kb >= 1000:
        return f"{n / (1024 * 1024):.0f} MB"
    return f"{kb:.0f} KB"


def compute_substituted(total_with_placeholder):
    """Compute the formatted size string, accounting for the substitution delta."""
    phlen = len(PLACEHOLDER)
    size = total_with_placeholder
    for _ in range(4):
        s = format_size(size)
        adjusted = total_with_placeholder + len(s.encode()) - phlen
        if format_size(adjusted) == s:
            return s
        size = adjusted
    return format_size(size)


def process(html_path, public_dir, base_path, dry_run):
    html_bytes = html_path.read_bytes()
    if PLACEHOLDER not in html_bytes:
        return
    total, _ = page_weight(html_path, html_bytes, public_dir, base_path)
    size_str = compute_substituted(total)
    if dry_run:
        print(f"{html_path.relative_to(public_dir)}: {size_str}")
    else:
        html_path.write_bytes(html_bytes.replace(PLACEHOLDER, size_str.encode(), 1))


def verify(html_path, public_dir, base_path):
    html_bytes = html_path.read_bytes()
    m = re.search(rb"Page size:\s*([\d.]+)\s*(KB|MB)", html_bytes)
    if m is None:
        return True
    displayed_val = float(m.group(1))
    displayed_unit = m.group(2).decode()
    total, _ = page_weight(html_path, html_bytes, public_dir, base_path)
    expected = format_size(total)
    em = re.match(r"([\d.]+) (KB|MB)", expected)
    assert em is not None
    expected_val, expected_unit = float(em.group(1)), em.group(2)
    if displayed_unit != expected_unit or abs(expected_val - displayed_val) > 0.5:
        print(f"FAIL {html_path.relative_to(public_dir)}: shows {displayed_val} {displayed_unit}, expected {expected}")
        return False
    return True


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("public_dir", type=Path)
    ap.add_argument("--verify", action="store_true", help="Assert sizes match (non-zero exit on failure)")
    ap.add_argument("--dry-run", action="store_true", help="Print sizes without writing")
    args = ap.parse_args()

    public_dir = args.public_dir.resolve()
    if not public_dir.is_dir():
        sys.exit(f"Not a directory: {public_dir}")

    base_path = detect_base_path(public_dir)
    html_files = sorted(public_dir.rglob("*.html"))
    if not html_files:
        sys.exit(f"No HTML files found in {public_dir}")

    errors = 0
    for p in html_files:
        try:
            if args.verify:
                if not verify(p, public_dir, base_path):
                    errors += 1
            else:
                process(p, public_dir, base_path, args.dry_run)
        except Exception as e:
            print(f"Error: {p}: {e}", file=sys.stderr)
            errors += 1

    if args.verify:
        marked = sum(1 for p in html_files if re.search(b"Page size:", p.read_bytes()))
        if errors == 0:
            print(f"OK: {marked} pages verified.")
        else:
            sys.exit(f"{errors} page(s) failed verification.")
    elif not args.dry_run:
        print(f"Updated {len(html_files)} pages.")


if __name__ == "__main__":
    main()
