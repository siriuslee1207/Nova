"""三才（天格・人格・地格 五行配置）吉凶（fate internal/wuxing → data/tables/sancai125.json）。

Nova 修正：fate 的 luckyPoint 缺「中吉」與筆誤「凶多吉少」，導致這些配置永遠被過濾；
此處 125 組全部有 1..7 分級（大凶1 凶2 凶多於吉3 吉凶參半4 中吉5 吉多於凶5 吉6 大吉7）。
"""
from __future__ import annotations

from . import tables
from .wuge import element_of

STRICTNESS_MIN_LEVEL = {'strict': 6, 'moderate': 5, 'relaxed': 4}


def key_of(tian: int, ren: int, di: int) -> str:
    return element_of(tian) + element_of(ren) + element_of(di)


def verdict(key: str) -> str:
    return tables.sancai()['combos'][key]['verdict']


def level(key: str) -> int:
    return tables.sancai()['combos'][key]['level']


def passes(key: str, strictness: str = 'moderate') -> bool:
    return level(key) >= STRICTNESS_MIN_LEVEL[strictness]


# 謝達輝表（data/tables/sancai_cdi.json）：另一套三才分級，由好到壞；「筆畫組合選字」以此過濾，原表只作對照。
CDI_GRADES = ('最吉', '吉', '平吉', '半吉', '凶', '最凶')
CDI_SELECTABLE = CDI_GRADES[:4]   # UI／CLI 可勾選的等級（凶、最凶不可選）


def cdi_grade(key: str) -> str:
    return tables.sancai_cdi()['combos'][key]['grade']


def cdi_no(key: str) -> int:
    """該站的組別編號 1..125（木木木=1 … 水水水=125）。"""
    return tables.sancai_cdi()['combos'][key]['no']


def detail(key: str) -> str:
    text = tables.sancai_text()['detail'].get(key)
    return text or f'三才{key}配置{verdict(key)}。'


def jichu(ren_el: str, di_el: str) -> str:
    """基礎運（人格 × 地格）。"""
    return tables.sancai_text()['jichu'].get(ren_el + di_el, '')


def chenggong(ren_el: str, tian_el: str) -> str:
    """成功運（人格 × 天格）。"""
    return tables.sancai_text()['chenggong'].get(ren_el + tian_el, '')


def renji(ren_el: str, wai_el: str) -> str:
    """人際關係（人格 × 外格）。"""
    return tables.sancai_text()['renji'].get(ren_el + wai_el, '')
