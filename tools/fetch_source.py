"""Download the raw data Nova's ETL needs into data/raw/ (all gitignored).

- fate resources/character.json (MIT) — base character dictionary
- Unihan.zip (Unicode License) — 康熙 radical/stroke, readings, definitions, variants

Run: .venv/Scripts/python tools/fetch_source.py [--force]
"""
from __future__ import annotations

import hashlib
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'data' / 'raw'

SOURCES = {
    'character.json': {
        'url': 'https://raw.githubusercontent.com/babyname/fate/main/resources/character.json',
        # fate main @ 2026-09-03; a mismatch means upstream changed — re-run the ETL report and review.
        'sha256': '848951bca0af07f37889acbe5a8dc741c776188f3a6bdba391c91f50007696c6',
    },
    'Unihan.zip': {
        'url': 'https://www.unicode.org/Public/UCD/latest/ucd/Unihan.zip',
        'sha256': None,  # "latest" moves with each Unicode release; checksum is printed, not enforced
    },
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def fetch(name: str, spec: dict, force: bool) -> None:
    dest = RAW / name
    if dest.exists() and not force:
        print(f'{name}: exists ({dest.stat().st_size} bytes), sha256={sha256(dest)}')
    else:
        print(f'{name}: downloading {spec["url"]}')
        with urllib.request.urlopen(spec['url'], timeout=120) as r, open(dest, 'wb') as f:
            while chunk := r.read(1 << 20):
                f.write(chunk)
        print(f'{name}: {dest.stat().st_size} bytes, sha256={sha256(dest)}')
    if spec['sha256'] and sha256(dest) != spec['sha256']:
        print(f'WARNING: {name} sha256 differs from the pinned value — upstream data changed; review etl_report.md after building.')


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    force = '--force' in sys.argv
    for name, spec in SOURCES.items():
        fetch(name, spec, force)


if __name__ == '__main__':
    main()
