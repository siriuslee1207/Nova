"""字典：ETL 產出的 data/gen/chars.json（與瀏覽器端 chars.gen.js 同一份內容）。"""
from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache

from . import ROOT

GEN_DIR = ROOT / 'data' / 'gen'


@dataclass(frozen=True)
class CharInfo:
    char: str
    py: tuple[str, ...]   # 數字調拼音，第一個為主讀音（臺灣讀音優先）
    stroke: int           # 姓名學筆畫（康熙）
    wx: str               # 五行
    lvl: int              # 1 常見取名用字、2 常用（Big5 常用區）、3 次常用（Big5 次常用區）
    nameable: bool
    meaning: str = ''
    radical: str = ''

    @property
    def regular(self) -> bool:
        """常用字（對應 fate regular）：等級 1–2。"""
        return self.lvl <= 2


@lru_cache(maxsize=None)
def _payload() -> dict:
    with open(GEN_DIR / 'chars.json', encoding='utf-8') as f:
        return json.load(f)


@lru_cache(maxsize=None)
def all_chars() -> dict[str, CharInfo]:
    p = _payload()
    assert p['fields'] == ['char', 'py', 'stroke', 'wx', 'lvl', 'nameable', 'meaning', 'radical']
    out = {}
    for ch, py, stroke, wx, lvl, nameable, meaning, radical in p['rows']:
        out[ch] = CharInfo(ch, tuple(py.split('/')), stroke, wx, lvl, bool(nameable), meaning, radical)
    return out


def simp2trad() -> dict[str, str]:
    return _payload()['simp2trad']


def lookup(ch: str) -> CharInfo | None:
    return all_chars().get(ch)


def normalize_surname(surname: str) -> tuple[str, list[str]]:
    """簡體姓氏自動轉繁；回傳 (繁體姓, 提示訊息)。"""
    table = simp2trad()
    notes = []
    out = []
    for ch in surname.strip():
        if ch in table:
            out.append(table[ch])
            notes.append(f'「{ch}」已轉為繁體「{table[ch]}」')
        else:
            out.append(ch)
    return ''.join(out), notes


def by_stroke(max_level: int = 2, nameable_only: bool = True) -> dict[int, list[CharInfo]]:
    """候選字依筆畫分桶；桶內依（等級、字元）排序以保證確定性。"""
    buckets: dict[int, list[CharInfo]] = {}
    for c in all_chars().values():
        if c.lvl > max_level or (nameable_only and not c.nameable):
            continue
        buckets.setdefault(c.stroke, []).append(c)
    for lst in buckets.values():
        lst.sort(key=lambda c: (c.lvl, c.char))
    return buckets
