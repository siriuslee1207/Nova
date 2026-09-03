"""候選產生（移植 fate internal/service/naming）：姓氏筆畫 → 合格筆畫組合 → 字對交叉 → 評分 → Top-N。

過濾鏈（與 fate CLI 預設一致）：總格 ∈ 接受集合 → 數理嚴格度（strict 人地外總、moderate 人地總、relaxed 人總 皆吉）
→ 三才等級門檻 →（可選）女性排除 女性不宜 之總格。

快速路徑：五格分只依賴 (f1, f2)，每組算一次；文化/五行/生肖/音韻的單字部分預先算好（皆為整數，
與 rating.rate_name 逐項相加結果完全相同）；再以每組合的分數上界剪枝。排名：總分降冪 →
兩字等級和升冪 → 第一字碼位 → 第二字碼位，確定性且與 JS 端一致。
"""
from __future__ import annotations

import heapq
from dataclasses import dataclass, field

from . import dayan, sancai, yinyun
from .bazi import FateData
from .chars import CharInfo, all_chars, by_stroke
from .rating import Rating, clamp100, grade, is_ke, is_sheng, rate_name, rate_wuge, total_of
from .tables import bazi as bazi_tables
from .wuge import MAX_STROKE, WuGe, calc_wuge

DAYAN_NEED = {'strict': ('ren', 'di', 'wai', 'zong'), 'moderate': ('ren', 'di', 'zong'), 'relaxed': ('ren', 'zong')}


@dataclass
class Options:
    strictness: str = 'moderate'
    zong_accept: frozenset[str] = dayan.LUCKY_ACCEPT_DEFAULT
    exclude_female_caution: bool = False   # 排除 女性不宜 總格（21 23 28 33）
    max_level: int = 2                     # 1 僅常見取名用字；2 含常用字；3 含次常用字
    avoid_chars: frozenset[str] = frozenset()
    require_chars: frozenset[str] = frozenset()  # 非空時名字至少含其一
    fixed_first: str | None = None         # 指定第一字（輩字）
    fixed_second: str | None = None        # 指定第二字
    top_n: int = 10
    min_stroke: int = 1
    max_stroke: int = MAX_STROKE


@dataclass(frozen=True)
class StrokeCombo:
    f1: int
    f2: int
    ge: WuGe
    sancai_key: str
    wuge_score: float
    wuge_details: tuple[str, ...]


def lucky_combos(l1: int, l2: int, opt: Options) -> list[StrokeCombo]:
    need = DAYAN_NEED[opt.strictness]
    out = []
    for f1 in range(opt.min_stroke, opt.max_stroke + 1):
        for f2 in range(opt.min_stroke, opt.max_stroke + 1):
            g = calc_wuge(l1, l2, f1, f2)
            zd = dayan.find(g.zong)
            if zd.lucky not in opt.zong_accept:
                continue
            if opt.exclude_female_caution and zd.female_caution:
                continue
            if any(dayan.find(getattr(g, k)).lucky not in opt.zong_accept for k in need):
                continue
            key = sancai.key_of(g.tian, g.ren, g.di)
            if not sancai.passes(key, opt.strictness):
                continue
            score, details, _, _ = rate_wuge(l1, l2, f1, f2)
            out.append(StrokeCombo(f1, f2, g, key, score, tuple(details)))
    return out


@dataclass(frozen=True)
class Pre:
    """單字預算分（整數），與 rating.rate_* 的逐字加項一致。"""
    c: CharInfo
    wenhua: int
    wuxing: int
    shengxiao: int
    tone: int
    sm: str
    ym: str


def precompute(c: CharInfo, fate: FateData | None) -> Pre:
    wh = (5 if c.regular and c.nameable else 2 if c.regular else 0)
    wh += 3 if 0 < c.lvl <= 2 else 1 if c.lvl == 3 else 0
    wh += 4 if c.meaning else 0
    wh += 2 if 5 <= c.stroke <= 15 else 0
    wx = sx = 0
    if fate is not None and c.wx:
        wx = 12 if c.wx == fate.yong else -8 if c.wx == fate.ji else 0
        zwx = bazi_tables()['zodiac_wuxing'].get(fate.zodiac, '')
        if zwx:
            if is_sheng(zwx, c.wx) or is_sheng(c.wx, zwx):
                sx += 7
            if is_ke(zwx, c.wx) or is_ke(c.wx, zwx):
                sx -= 5
    p = c.py[0] if c.py else ''
    return Pre(c, wh, wx, sx, yinyun.tone(p), yinyun.shengmu(p), yinyun.yunmu(p))


def fast_scores(a: Pre, b: Pre, combo: StrokeCombo, fate: FateData | None) -> tuple[float, float, float, float, float]:
    """回傳 (文化, 五行, 生肖, 五格, 音韻)，與 rate_name 逐項相等。"""
    wh = 60 + a.wenhua + b.wenhua
    if a.c.stroke > 0 and b.c.stroke > 0 and abs(a.c.stroke - b.c.stroke) <= 5:
        wh += 2
    if a.c.py and b.c.py:
        wh += 2
    if fate is None:
        wx = 80.0
        sx = 80.0
    else:
        wx = 70 + a.wuxing + b.wuxing
        if a.c.wx and b.c.wx:
            if is_sheng(a.c.wx, b.c.wx) or is_sheng(b.c.wx, a.c.wx):
                wx += 8
            if is_ke(a.c.wx, b.c.wx) or is_ke(b.c.wx, a.c.wx):
                wx -= 5
        sx = 80 + a.shengxiao + b.shengxiao
    yy = 80
    if a.c.py and b.c.py:
        if a.tone != b.tone and a.tone and b.tone:
            yy += 8
        elif a.tone == b.tone and a.tone:
            yy -= 5
        if a.sm != b.sm and a.sm and b.sm:
            yy += 5
        elif a.sm == b.sm and a.sm:
            yy -= 3
        if a.ym != b.ym and a.ym and b.ym:
            yy += 4
        elif a.ym == b.ym and a.ym:
            yy -= 3
    return clamp100(float(wh)), clamp100(float(wx)), clamp100(float(sx)), combo.wuge_score, clamp100(float(yy))


@dataclass
class Candidate:
    c1: CharInfo
    c2: CharInfo
    combo: StrokeCombo
    scores: tuple[float, float, float, float, float]
    total: float
    grade: str

    @property
    def name(self) -> str:
        return self.c1.char + self.c2.char

    def full_rating(self, l1: int, l2: int, fate: FateData | None) -> Rating:
        return rate_name(l1, l2, self.c1, self.c2, fate)


def _sort_key(c: Candidate) -> tuple:
    return (-c.total, c.c1.lvl + c.c2.lvl, c.c1.char, c.c2.char)


def _heap_key(total: float, c1: CharInfo, c2: CharInfo) -> tuple:
    # min-heap：最差在堆頂；與 _sort_key 反向
    return (total, -(c1.lvl + c2.lvl), -ord(c1.char), -ord(c2.char))


# 各維上界（含 clamp）：文化 ≤ 60+10+6+8+4+2+2 = 92，五行 ≤ 100，生肖 ≤ 94，音韻 ≤ 97
_MAX_WENHUA, _MAX_WUXING, _MAX_SHENGXIAO, _MAX_YINYUN = 92.0, 100.0, 94.0, 97.0


def generate(l1: int, l2: int, fate: FateData | None, opt: Options) -> list[Candidate]:
    combos = lucky_combos(l1, l2, opt)
    combos.sort(key=lambda c: -c.wuge_score)  # 好的組合先算，門檻早升高
    buckets = by_stroke(opt.max_level)
    pre_cache: dict[str, Pre] = {}

    def pres(stroke: int, fixed: str | None) -> list[Pre]:
        if fixed:
            ci = all_chars().get(fixed)
            return [pre_cache.setdefault(fixed, precompute(ci, fate))] if ci and ci.stroke == stroke else []
        out = []
        for c in buckets.get(stroke, []):
            if c.char in opt.avoid_chars:
                continue
            p = pre_cache.get(c.char)
            if p is None:
                p = pre_cache[c.char] = precompute(c, fate)
            out.append(p)
        return out

    heap: list[tuple[tuple, Candidate]] = []
    for combo in combos:
        if len(heap) >= opt.top_n:
            bound = total_of(_MAX_WENHUA, _MAX_WUXING, _MAX_SHENGXIAO, combo.wuge_score, _MAX_YINYUN)
            if bound < heap[0][0][0]:
                continue
        firsts = pres(combo.f1, opt.fixed_first)
        seconds = pres(combo.f2, opt.fixed_second)
        for a in firsts:
            for b in seconds:
                if opt.require_chars and a.c.char not in opt.require_chars and b.c.char not in opt.require_chars:
                    continue
                scores = fast_scores(a, b, combo, fate)
                total = total_of(*scores)
                key = _heap_key(total, a.c, b.c)
                if len(heap) < opt.top_n:
                    heapq.heappush(heap, (key, Candidate(a.c, b.c, combo, scores, total, grade(total))))
                elif key > heap[0][0]:
                    heapq.heapreplace(heap, (key, Candidate(a.c, b.c, combo, scores, total, grade(total))))
    return sorted((c for _, c in heap), key=_sort_key)
