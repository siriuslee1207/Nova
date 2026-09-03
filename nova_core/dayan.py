"""八十一數理（大衍之數）查表（fate internal/wuge/dayan.go → data/tables/dayan81.json）。"""
from __future__ import annotations

from dataclasses import dataclass

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
