"""八十一數理（大衍之數）查表（fate internal/wuge/dayan.go → data/tables/dayan81.json）。

另有「筆畫組合選字」用的 36 吉數（data/tables/jishu36.json）與吉數等級
（data/tables/jishu_grade.json：大吉／吉／半吉／半凶／凶，大吉＋吉＝36 吉數），
以及可切換的吉數表（JISHU_TABLES：36／fate 吉／謝達輝 吉／自選）。
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from . import tables

LUCKY_ACCEPT_DEFAULT = frozenset({'吉', '半吉'})  # fate 以 contains("吉") 隱含此集合；Nova 明確化


@dataclass(frozen=True)
class DaYan:
    number: int
    lucky: str            # 吉 | 凶 | 半吉
    max_luck: bool        # 最大好運數（21 23 28 33 41）
    female_caution: bool  # 女性不宜（21 23 28 33）
    title: str
    comment: str


def find(n: int) -> DaYan:
    """n 為任一正整數；超過 81 循環（(n-1) % 81）。"""
    if n <= 0:
        raise ValueError(f'數理必須為正整數: {n}')
    return DaYan(**tables.dayan()[(n - 1) % 81])


def is_lucky(d: DaYan, accept: frozenset[str] = LUCKY_ACCEPT_DEFAULT) -> bool:
    return d.lucky in accept


@lru_cache(maxsize=None)
def jishu() -> frozenset[int]:
    """36 吉數（data/tables/jishu36.json，使用者指定表）；「筆畫組合選字」以此判定五格，與 lucky 分級無關。"""
    return frozenset(tables.jishu()['numbers'])


def is_jishu(n: int, jishu_set: frozenset[int] | None = None) -> bool:
    """n 為任一正整數；超過 81 與 find 同法循環。jishu_set 不給＝36 吉數，給了就以該集合（1..81）判定。"""
    if n <= 0:
        raise ValueError(f'數理必須為正整數: {n}')
    return ((n - 1) % 81) + 1 in (jishu() if jishu_set is None else jishu_set)


# 吉數表：「筆畫組合選字」的吉數可從既有的幾張表擇一，或自選一組數字（custom）
JISHU_TABLES = ('36', 'fate', 'cdi', 'custom')
JISHU_TABLE_LABELS = {'36': '熊崎氏 36 吉數', 'fate': 'fate 81 數理「吉」', 'cdi': '謝達輝 81 劃表「吉」', 'custom': '自選'}


@lru_cache(maxsize=None)
def jishu_table(name: str) -> frozenset[int]:
    """具名吉數表 → 1..81 的集合：36＝jishu36.json；fate＝dayan81 的「吉」；cdi＝謝達輝 81 劃表的「吉」。"""
    if name == '36':
        return jishu()
    if name == 'fate':
        return frozenset(n for n in range(1, 82) if find(n).lucky == '吉')
    if name == 'cdi':
        return frozenset(n for n in range(1, 82) if cdi_grade(n) == '吉')
    raise ValueError(f'未知的吉數表: {name}（可選 ' + ','.join(JISHU_TABLES) + '）')


def jishu_of(table: str = '36', custom=()) -> frozenset[int]:
    """吉數表名稱＋自選數字 → 實際判定用的集合；custom 只在 table == 'custom' 時採用，超過 81 以 (n-1)%81+1 循環，0 以下丟掉。"""
    if table == 'custom':
        return frozenset(((n - 1) % 81) + 1 for n in custom if n > 0)
    return jishu_table(table)


GRADES = ('大吉', '吉', '半吉', '半凶', '凶')   # 吉數等級，由好到壞（data/tables/jishu_grade.json）
JISHU_GRADES = frozenset({'大吉', '吉'})        # 這兩級合起來恰為 36 吉數


@lru_cache(maxsize=None)
def _grades() -> tuple[str, ...]:
    t = tables.jishu_grade()
    return tuple(t['grade'])


@lru_cache(maxsize=None)
def _cdi_grades() -> tuple[str, ...]:
    return tuple(tables.jishu_grade()['cdi'])


def grade(n: int) -> str:
    """吉數等級（大吉／吉／半吉／半凶／凶）；n 為任一正整數，超過 81 與 find 同法循環。"""
    if n <= 0:
        raise ValueError(f'數理必須為正整數: {n}')
    return _grades()[(n - 1) % 81]


def cdi_grade(n: int) -> str:
    """謝達輝「81 劃吉凶分類表」原級（吉／吉帶凶／凶帶吉／凶），僅供對照顯示。"""
    if n <= 0:
        raise ValueError(f'數理必須為正整數: {n}')
    return _cdi_grades()[(n - 1) % 81]
