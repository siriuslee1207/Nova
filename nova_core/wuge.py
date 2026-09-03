"""五格剖象：天格、人格、地格、外格、總格（移植自 fate internal/wuge/wuge.go）。

l1, l2 為姓氏筆畫（單姓 l2 = 0），f1, f2 為名字筆畫（單字名 f2 = 0）。
缺位以 1 代入（假成數）；總格取 1..81 循環，其餘四格不循環，查數理時再取 (n-1) % 81。
"""
from __future__ import annotations

from dataclasses import dataclass

MAX_STROKE = 30
ELEMENT_BY_DIGIT = '水木木火火土土金金水'  # 格數末位 → 五行


@dataclass(frozen=True)
class WuGe:
    tian: int
    ren: int
    di: int
    wai: int
    zong: int

    def as_dict(self) -> dict[str, int]:
        return {'tian': self.tian, 'ren': self.ren, 'di': self.di, 'wai': self.wai, 'zong': self.zong}


def calc_wuge(l1: int, l2: int, f1: int, f2: int) -> WuGe:
    tian = l1 + 1 if l2 == 0 else l1 + l2
    ren = (l1 if l2 == 0 else l2) + f1
    di = f1 + 1 if f2 == 0 else f1 + f2
    wai = (1 if l2 == 0 else l1) + (1 if f2 == 0 else f2)
    zong = (l1 + l2 + f1 + f2 - 1) % 81 + 1
    return WuGe(tian, ren, di, wai, zong)


def element_of(n: int) -> str:
    """格數 → 五行（1,2 木；3,4 火；5,6 土；7,8 金；9,0 水）。"""
    return ELEMENT_BY_DIGIT[n % 10]


def yinyang_of(n: int) -> str:
    return '陰' if n % 2 == 0 else '陽'
