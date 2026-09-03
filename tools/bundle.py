"""Bundle src/index.html + css + data + vendor + core + ui into one self-contained dist/nova.html.

Every `<script src="...">` and `<link rel="stylesheet" href="...">` in src/index.html is replaced by inline
content (paths resolved relative to src/). The result uses only classic inline scripts, so it works from file://.

Run: .venv/Scripts/python tools/bundle.py
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'src'
DIST = ROOT / 'dist'

_SCRIPT = re.compile(r'<script\s+src="([^"]+)"(?:\s+id="([^"]+)")?\s*></script>')
_LINK = re.compile(r'<link\s+rel="stylesheet"\s+href="([^"]+)"\s*>')


def inline_js(path: Path, script_id: str | None) -> str:
    js = path.read_text(encoding='utf-8')
    js = re.sub(r'</script', r'<\\/script', js, flags=re.I)  # never terminate the wrapping tag early
    attr = f' id="{script_id}"' if script_id else ''
    return f'<script{attr} data-src="{path.name}">\n{js}\n</script>'


def inline_css(path: Path) -> str:
    return f'<style data-src="{path.name}">\n{path.read_text(encoding="utf-8")}\n</style>'


def main() -> None:
    html = (SRC / 'index.html').read_text(encoding='utf-8')
    html = _LINK.sub(lambda m: inline_css((SRC / m.group(1)).resolve()), html)
    html = _SCRIPT.sub(lambda m: inline_js((SRC / m.group(1)).resolve(), m.group(2)), html)
    DIST.mkdir(exist_ok=True)
    out = DIST / 'nova.html'
    out.write_text(html, encoding='utf-8')
    size = out.stat().st_size
    print(f'wrote {out.relative_to(ROOT)} ({size / 1024:.0f} KB)')
    leftovers = re.findall(r'<(?:script|link)[^>]*?\s(?:src|href)="(?!data:|https?:)([^"]+)"', html)
    if leftovers:
        print('WARNING: external references remain:', leftovers)


if __name__ == '__main__':
    main()
