#!/usr/bin/env python3
"""Download Google Fonts as local WOFF2 files and generate a self-hosted fonts.css.

Run once to set up self-hosted fonts:
    python3 scripts/download_fonts.py
"""

import re
import urllib.request
from pathlib import Path

FONTS_URL = (
    "https://fonts.googleapis.com/css2"
    "?family=Merriweather:wght@400..700"
    "&family=Source+Serif+4:ital,wght@0,400;0,500;0,600;0,700;1,400"
    "&display=swap"
)
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120 Safari/537.36"

RANGE_SLUG = {
    "cyrillic-ext": "cyrillic-ext",
    "cyrillic": "cyrillic",
    "greek-ext": "greek-ext",
    "greek": "greek",
    "vietnamese": "vietnamese",
    "latin-ext": "latin-ext",
    "latin": "latin",
}

FACE_RE = re.compile(
    r"/\*\s*([^*]+?)\s*\*/\s*@font-face\s*\{([^}]+)\}", re.DOTALL
)
PROP_RE = re.compile(r"([\w-]+)\s*:\s*([^;]+);")
URL_RE = re.compile(r"url\(([^)]+)\)")


def fetch_css():
    req = urllib.request.Request(FONTS_URL, headers={"User-Agent": UA})
    return urllib.request.urlopen(req).read().decode()


def parse_faces(css):
    faces = []
    for m in FACE_RE.finditer(css):
        range_label = m.group(1).strip()
        props = {k.strip(): v.strip() for k, v in PROP_RE.findall(m.group(2))}
        url_m = URL_RE.search(props.get("src", ""))
        if not url_m:
            continue
        faces.append({
            "range_label": range_label,
            "family": props.get("font-family", "").strip("'\""),
            "style": props.get("font-style", "normal"),
            "weight": props.get("font-weight", "400"),
            "display": props.get("font-display", "swap"),
            "unicode_range": props.get("unicode-range", ""),
            "url": url_m.group(1),
        })
    return faces


def make_filename(family, style, range_label):
    slug = family.lower().replace(" ", "-")
    style_part = "" if style == "normal" else f"-{style}"
    range_part = RANGE_SLUG.get(range_label, range_label.replace(" ", "-"))
    return f"{slug}{style_part}-{range_part}.woff2"


def download_files(url_to_file, dest_dir):
    dest_dir.mkdir(parents=True, exist_ok=True)
    for url, filename in url_to_file.items():
        dest = dest_dir / filename
        if dest.exists():
            print(f"  exists  {filename}")
            continue
        print(f"  downloading {filename} ...")
        urllib.request.urlretrieve(url, dest)


def generate_css(faces, url_to_file):
    # Group faces by (family, style, unicode_range) so we can emit one
    # @font-face per range with a weight range instead of one per weight.
    from collections import defaultdict
    groups = defaultdict(list)
    for face in faces:
        key = (face["family"], face["style"], face["url"], face["unicode_range"])
        groups[key].extend(int(weight) for weight in face["weight"].split())

    lines = []
    seen_keys = set()
    for face in faces:
        key = (face["family"], face["style"], face["url"], face["unicode_range"])
        if key in seen_keys:
            continue
        seen_keys.add(key)
        weights = sorted(groups[key])
        weight_val = f"{weights[0]} {weights[-1]}" if len(weights) > 1 else str(weights[0])
        filename = url_to_file[face["url"]]
        lines.append(
            f"@font-face {{\n"
            f"  font-family: '{face['family']}';\n"
            f"  font-style: {face['style']};\n"
            f"  font-weight: {weight_val};\n"
            f"  font-display: {face['display']};\n"
            f"  src: url('../fonts/{filename}') format('woff2');\n"
            f"  unicode-range: {face['unicode_range']};\n"
            f"}}"
        )
    return "\n".join(lines) + "\n"


def main():
    root = Path(__file__).parent.parent
    fonts_dir = root / "static" / "fonts"
    css_out = root / "static" / "css" / "fonts.css"

    print("Fetching Google Fonts CSS ...")
    css = fetch_css()
    faces = parse_faces(css)
    print(f"  found {len(faces)} @font-face declarations")

    # Build URL → filename map (deduped — same file serves all weights)
    url_to_file = {}
    for face in faces:
        url = face["url"]
        if url not in url_to_file:
            url_to_file[url] = make_filename(
                face["family"], face["style"], face["range_label"]
            )

    print(f"  {len(url_to_file)} unique WOFF2 files")
    print(f"Downloading to {fonts_dir} ...")
    download_files(url_to_file, fonts_dir)

    css_content = generate_css(faces, url_to_file)
    css_out.write_text(css_content)
    print(f"Wrote {css_out.relative_to(root)}")


if __name__ == "__main__":
    main()
