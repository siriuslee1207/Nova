"""One-shot build: tables → chars → [fixtures] → bundle.

Run: .venv/Scripts/python tools/build.py [--fixtures] [--transcribe]
  --transcribe  re-transcribe fate's Go tables first (needs ref/fate/, see tools/transcribe_fate.py)
  --fixtures    regenerate tests/fixtures/golden.json from the Python reference (slow, ~1 min)
Requires data/raw/ (tools/fetch_source.py) and the venv extras: build, bazi.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / 'tools'


def run(script: str) -> None:
    print(f'== {script}')
    env = dict(os.environ, PYTHONUTF8='1')
    subprocess.run([sys.executable, str(TOOLS / script)], check=True, cwd=ROOT, env=env)


def main(argv: list[str]) -> None:
    steps = []
    if '--transcribe' in argv:
        steps.append('transcribe_fate.py')
    steps += ['build_tables.py', 'build_chars.py', 'build_prompts.py']
    if '--fixtures' in argv:
        steps.append('gen_fixtures.py')
    steps.append('bundle.py')
    for s in steps:
        run(s)
    print('build done → dist/nova.html')


if __name__ == '__main__':
    main(sys.argv[1:])
