"""五維評分（移植 fate internal/rating/rating.go）：文化 20%、五行 25%、生肖 10%、五格 30%、音韻 15%。

Nova 修正（相對 fate）：
- 五格：半吉 依序先判，給 8×權重（fate 因判斷順序永遠走到 吉 的 15×權重）。
- 五行：用神/忌神取自使用者選定的喜用神方法（fate 只讀簡化版且方法切換無效）。
- 音韻：聲調由數字調尾碼讀取（ETL 已轉換），韻母比較不含聲調。
- 四捨五入：round1 = floor(x*10+0.5)/10，Python 與 JS 一致。
文化維度中 fate 的 gender_hint 加分因資料全空而移除；common_level 由 Big5 等級推得。
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from . import dayan, sancai, tables, yinyun
from .bazi import FateData
from .chars import CharInfo
from .wuge import WuGe, calc_wuge

WEIGHTS = {'wenhua': 0.20, 'wuxing': 0.25, 'shengxiao': 0.10, 'wuge': 0.30, 'yinyun': 0.15}
GE_WEIGHTS = (('tian', 0.15), ('ren', 0.30), ('di', 0.20), ('wai', 0.15), ('zong', 0.20))
GE_NAMES = {'tian': '天格', 'ren': '人格', 'di': '地格', 'wai': '外格', 'zong': '總格'}
SHENG = {'木': '火', '火': '土', '土': '金', '金': '水', '水': '木'}
KE = {'木': '土', '土': '水', '水': '火', '火': '金', '金': '木'}


def round1(x: float) -> float:
    return math.floor(x * 10 + 0.5) / 10


def clamp100(x: float) -> float:
    return 100.0 if x > 100 else 0.0 if x < 0 else x


def is_sheng(a: str, b: str) -> bool:
    return SHENG.get(a) == b


def is_ke(a: str, b: str) -> bool:
    return KE.get(a) == b


def grade(total: float) -> str:
    if total >= 90:
        return '上上'
    if total >= 80:
        return '上吉'
    if total >= 70:
        return '中吉'
    if total >= 60:
        return '中平'
    if total >= 50:
        return '中下'
    return '下下'


@dataclass
class Rating:
    wenhua: float
    wuxing: float
    shengxiao: float
    wuge: float
    yinyun: float
    total: float
    grade: str
    ge: WuGe | None
    sancai_key: str
    details: dict[str, list[str]]


def rate_wenhua(c1: CharInfo, c2: CharInfo) -> tuple[float, list[str]]:
    score = 60.0
    d: list[str] = []
    for c in (c1, c2):
        if c.regular and c.nameable:
            score += 5
            d.append(f'「{c.char}」為常用取名用字')
        elif c.regular:
            score += 2
    for c in (c1, c2):
        if 0 < c.lvl <= 2:
            score += 3
        elif c.lvl == 3:
            score += 1
    for c in (c1, c2):
        if c.meaning:
            score += 4
    for c in (c1, c2):
        if 5 <= c.stroke <= 15:
            score += 2
    if c1.stroke > 0 and c2.stroke > 0 and abs(c1.stroke - c2.stroke) <= 5:
        score += 2
        d.append('筆畫搭配勻稱')
    if c1.py and c2.py:
        score += 2
    return clamp100(score), d


def rate_wuxing(c1: CharInfo, c2: CharInfo, fate: FateData | None) -> tuple[float, list[str]]:
    if fate is None:
        return 80.0, ['無生辰資料，五行以中性計']
    score = 70.0
    d: list[str] = []
    for c in (c1, c2):
        if not c.wx:
            continue
        if c.wx == fate.yong:
            score += 12
            d.append(f'「{c.char}」五行屬{c.wx}，為用神，加分')
        elif c.wx == fate.ji:
            score -= 8
            d.append(f'「{c.char}」五行屬{c.wx}，為忌神，減分')
        else:
            d.append(f'「{c.char}」五行屬{c.wx}，中性')
    if c1.wx and c2.wx:
        if is_sheng(c1.wx, c2.wx) or is_sheng(c2.wx, c1.wx):
            score += 8
            d.append('兩字五行相生，搭配協調')
        if is_ke(c1.wx, c2.wx) or is_ke(c2.wx, c1.wx):
            score -= 5
            d.append('兩字五行相剋，需注意')
    return clamp100(score), d


def rate_shengxiao(c1: CharInfo, c2: CharInfo, fate: FateData | None) -> tuple[float, list[str]]:
    score = 80.0
    if fate is None:
        return score, []
    zwx = tables.bazi()['zodiac_wuxing'].get(fate.zodiac, '')
    d: list[str] = []
    if zwx:
        d.append(f'生肖{fate.zodiac}，五行屬{zwx}')
        for c in (c1, c2):
            if c.wx and (is_sheng(zwx, c.wx) or is_sheng(c.wx, zwx)):
                score += 7
                d.append(f'「{c.char}」與生肖五行相生')
        for c in (c1, c2):
            if c.wx and (is_ke(zwx, c.wx) or is_ke(c.wx, zwx)):
                score -= 5
                d.append(f'「{c.char}」與生肖五行相剋')
    return clamp100(score), d


def rate_wuge(l1: int, l2: int, f1: int, f2: int) -> tuple[float, list[str], WuGe | None, str]:
    """只依賴筆畫；產生器可對每組 (f1, f2) 只算一次。運算順序：天→人→地→外→總→總格最大好運→三才。"""
    if l1 == 0:
        return 70.0, ['無姓氏筆畫'], None, ''
    g = calc_wuge(l1, l2, f1, f2)
    score = 60.0
    d: list[str] = []
    for name, w in GE_WEIGHTS:
        n = getattr(g, name)
        dy = dayan.find(n)
        if dy.lucky == '半吉':
            score += 8 * w
        elif dy.lucky == '吉':
            score += 15 * w
        else:
            score -= 5 * w
        d.append(f'{GE_NAMES[name]}{n}（{dy.title}）{dy.lucky}')
    if dayan.find(g.zong).max_luck:
        score += 5
        d.append('總格為最大好運數')
    key = sancai.key_of(g.tian, g.ren, g.di)
    v = sancai.verdict(key)
    if v == '大吉':
        score += 12
    elif v in ('吉', '吉多於凶'):
        score += 8
    elif v == '中吉':
        score += 5
    elif v in ('凶多於吉', '吉凶參半'):
        score -= 2
    elif v in ('凶', '大凶'):
        score -= 6
    d.append(f'三才{key}{v}')
    return clamp100(score), d, g, key


def rate_yinyun(c1: CharInfo, c2: CharInfo) -> tuple[float, list[str]]:
    score = 80.0
    d: list[str] = []
    if not c1.py or not c2.py:
        return score, d
    p1, p2 = c1.py[0], c2.py[0]
    t1, t2 = yinyun.tone(p1), yinyun.tone(p2)
    if t1 != t2 and t1 and t2:
        score += 8
        d.append('兩字聲調不同，抑揚頓挫')
    elif t1 == t2 and t1:
        score -= 5
        d.append('兩字聲調相同')
    s1, s2 = yinyun.shengmu(p1), yinyun.shengmu(p2)
    if s1 != s2 and s1 and s2:
        score += 5
        d.append('聲母不同，發音清晰')
    elif s1 == s2 and s1:
        score -= 3
        d.append('聲母相同')
    y1, y2 = yinyun.yunmu(p1), yinyun.yunmu(p2)
    if y1 != y2 and y1 and y2:
        score += 4
        d.append('韻母不同，朗朗上口')
    elif y1 == y2 and y1:
        score -= 3
        d.append('韻母相同')
    return clamp100(score), d


def total_of(wenhua: float, wuxing: float, shengxiao: float, wuge: float, yinyun_: float) -> float:
    """加權總分；JS 端必須使用相同的運算順序。"""
    return round1(wenhua * WEIGHTS['wenhua'] + wuxing * WEIGHTS['wuxing'] + shengxiao * WEIGHTS['shengxiao']
                  + wuge * WEIGHTS['wuge'] + yinyun_ * WEIGHTS['yinyun'])


def rate_name(l1: int, l2: int, c1: CharInfo, c2: CharInfo, fate: FateData | None) -> Rating:
    wh, d1 = rate_wenhua(c1, c2)
    wx, d2 = rate_wuxing(c1, c2, fate)
    sx, d3 = rate_shengxiao(c1, c2, fate)
    wg, d4, g, key = rate_wuge(l1, l2, c1.stroke, c2.stroke)
    yy, d5 = rate_yinyun(c1, c2)
    total = total_of(wh, wx, sx, wg, yy)
    return Rating(wh, wx, sx, wg, yy, total, grade(total), g, key,
                  {'wenhua': d1, 'wuxing': d2, 'shengxiao': d3, 'wuge': d4, 'yinyun': d5})
