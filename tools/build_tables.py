"""Merge data/tables/*.json into data/gen/tables.gen.js for the browser build.

The JSON files stay the single source of truth (Python reads them directly); this step only
re-emits them as one classic-script global so the single-file HTML needs no fetch().

Run: .venv/Scripts/python tools/build_tables.py
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TABLES = ROOT / 'data' / 'tables'
GEN = ROOT / 'data' / 'gen'

FILES = {
    'dayan': 'dayan81.json',
    'sancai': 'sancai125.json',
    'sancaiText': 'sancai_text.json',
    'bazi': 'bazi_tables.json',
    'strokeOverrides': 'stroke_overrides.json',
    'sancaiCdi': 'sancai_cdi.json',
    'jishu': 'jishu36.json',
}


def load_all() -> dict:
    out = {}
    for key, name in FILES.items():
        with open(TABLES / name, encoding='utf-8') as f:
            out[key] = json.load(f)
    assert len(out['dayan']) == 81
    assert len(out['sancai']['combos']) == 125
    assert len(out['sancaiCdi']['combos']) == 125
    assert out['sancaiCdi']['grades'] == ['最吉', '吉', '平吉', '半吉', '凶', '最凶']
    assert set(out['sancaiCdi']['combos']) == set(out['sancai']['combos'])
    nums = out['jishu']['numbers']
    assert len(nums) == 36 and nums == sorted(set(nums)) and all(isinstance(n, int) and 1 <= n <= 81 for n in nums)
    return out


def main() -> None:
    GEN.mkdir(parents=True, exist_ok=True)
    data = load_all()
    js = 'globalThis.NOVA_TABLES = ' + json.dumps(data, ensure_ascii=False, separators=(',', ':')) + ';\n'
    path = GEN / 'tables.gen.js'
    path.write_text(js, encoding='utf-8')
    print(f'wrote {path.relative_to(ROOT)} ({path.stat().st_size} bytes)')


if __name__ == '__main__':
    main()
