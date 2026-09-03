"""Emit data/prompts/*.md as data/gen/prompts.gen.js for the browser (Python reads the .md files directly).

Run: .venv/Scripts/python tools/build_prompts.py
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROMPTS = ROOT / 'data' / 'prompts'
GEN = ROOT / 'data' / 'gen'


def main() -> None:
    GEN.mkdir(parents=True, exist_ok=True)
    templates = {p.stem: p.read_text(encoding='utf-8') for p in sorted(PROMPTS.glob('*.md'))}
    assert {'system', 'recommend_chars', 'explain_name'} <= set(templates), templates.keys()
    js = 'globalThis.NOVA_PROMPTS = ' + json.dumps(templates, ensure_ascii=False) + ';\n'
    out = GEN / 'prompts.gen.js'
    out.write_text(js, encoding='utf-8')
    print(f'wrote {out.relative_to(ROOT)} ({out.stat().st_size} bytes, {len(templates)} templates)')


if __name__ == '__main__':
    main()
