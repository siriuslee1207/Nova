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


def sancai_cdi() -> dict:
    """三才配置吉凶（謝達輝表：最吉／吉／平吉／半吉／凶／最凶），供「筆畫組合選字」過濾。"""
    return load('sancai_cdi.json')


def jishu() -> dict:
    """36 吉數（使用者指定表），供「筆畫組合選字」判定五格。"""
    return load('jishu36.json')


def jishu_grade() -> dict:
    """81 數的吉數等級（大吉／吉／半吉／半凶／凶，fate dayan81 × 謝達輝 81 劃表合併）；大吉＋吉＝36 吉數。"""
    return load('jishu_grade.json')
