"""載入 data/tables/*.json（Python 與 JS 共用的單一真相來源）。"""
from __future__ import annotations

import json
from functools import lru_cache

from . import ROOT

TABLES_DIR = ROOT / 'data' / 'tables'


@lru_cache(maxsize=None)
def load(name: str):
    with open(TABLES_DIR / name, encoding='utf-8') as f:
        return json.load(f)


def dayan() -> list[dict]:
    return load('dayan81.json')


def sancai() -> dict:
    return load('sancai125.json')


def sancai_text() -> dict:
    return load('sancai_text.json')


def bazi() -> dict:
    return load('bazi_tables.json')


def stroke_overrides() -> dict:
    return load('stroke_overrides.json')
