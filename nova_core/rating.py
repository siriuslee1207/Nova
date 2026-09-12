"""五維評分（移植 fate internal/rating/rating.go）：文化 20%、五行 25%、生肖 10%、五格 30%、音韻 15%。

權重可自訂（`weights`）：各維分數照算，只有加權總分改變；權重先正規化成總和 1，
所以「三才五格=1、其他=0」的總分就等於五格維度的分數，等級門檻（上上/上吉…）仍然適用。
正規化只做一次（見 normalize_weights），Python 與 JS 兩邊的呼叫點必須對齊，否則浮點結果會差一位。

Nova 修正（相對 fate）：
- 五格：半吉 依序先判，給 8×權重（fate 因判斷順序永遠走到 吉 的 15×權重）。
- 五行：用神/忌神取自使用者選定的喜用神方法（fate 只讀簡化版且方法切換無效）。
- 音韻：聲調由數字調尾碼讀取（ETL 已轉換），韻母比較不含聲調。
- 四捨五入：round1 = floor(x*10+0.5)/10，Python 與 JS 一致。
文化維度中 fate 的 gender_hint 加分因資料全空而移除；common_level 由 Big5 等級推得。
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

from . import dayan, sancai, tables, yinyun
from .bazi import FateData
from .chars import CharInfo
from .wuge import WuGe, calc_wuge

DIMS = ('wenhua', 'wuxing', 'shengxiao', 'wuge', 'yinyun')
DIM_NAMES = {'wenhua': '文化', 'wuxing': '五行', 'shengxiao': '生肖', 'wuge': '五格三才', 'yinyun': '音韻'}
WEIGHTS = {'wenhua': 0.20, 'wuxing': 0.25, 'shengxiao': 0.10, 'wuge': 0.30, 'yinyun': 0.15}
DEFAULT_WEIGHTS = tuple(WEIGHTS[k] for k in DIMS)   # 和恰為 1.0，正規化不會改動任何一位
# 預設組合（未正規化；數值只是相對比例）
PRESETS = {
    'default': DEFAULT_WEIGHTS,
    'wuge': (0.0, 0.0, 0.0, 1.0, 0.0),          # 只看三才五格
    'bazi': (0.1, 0.5, 0.2, 0.1, 0.1),          # 八字喜用與生肖為主
    'sound': (0.3, 0.1, 0.05, 0.15, 0.4),       # 音韻、字義為主
    'equal': (1.0, 1.0, 1.0, 1.0, 1.0),         # 五維等重
}
PRESET_NAMES = {'default': '預設五維', 'wuge': '只看三才五格', 'bazi': '八字五行為主',
                'sound': '音韻字義為主', 'equal': '五維等重'}
# 權重項目別名（CLI 與網址參數用）
WEIGHT_ALIASES = {'文化': 'wenhua', '字義': 'wenhua', '五行': 'wuxing', '八字': 'wuxing', '喜用': 'wuxing',
                  '生肖': 'shengxiao', '五格': 'wuge', '三才': 'wuge', '三才五格': 'wuge', '五格三才': 'wuge',
                  '音韻': 'yinyun', '讀音': 'yinyun'}
WEIGHT_OTHER = ('其他', '其它', 'other', 'rest', '*')
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


def normalize_weights(w) -> tuple[float, float, float, float, float]:
    """權重（None／dict／五元序列）→ 總和為 1 的五元組，順序同 DIMS。

    負數視為 0；全為 0 或 None 時回預設。**同一份權重只能正規化一次**：正規化後的值再除一次
    可能差 1 ulp，Python 與 JS 的呼叫點必須一一對應。
    """
    if w is None:
        return DEFAULT_WEIGHTS
    if isinstance(w, dict):
        vals = [float(w.get(k, WEIGHTS[k])) for k in DIMS]
    else:
        vals = [float(x) for x in w]
        if len(vals) != 5:
            raise ValueError('權重需為 5 個數值（文化 五行 生肖 五格 音韻）')
    vals = [v if math.isfinite(v) and v > 0 else 0.0 for v in vals]
    s = 0.0
    for v in vals:
        s += v
    if s <= 0:
        return DEFAULT_WEIGHTS
    if s == 1.0:
        return tuple(vals)
    return tuple(v / s for v in vals)


def _weight_num(k: str, v: str) -> float:
    try:
        x = float(v)
    except ValueError:
        raise ValueError(f'權重「{k}」需為數字，收到「{v}」') from None
    if not math.isfinite(x):
        raise ValueError(f'權重「{k}」需為數字，收到「{v}」')
    return x


def parse_weights(text: str | None) -> tuple[float, ...] | None:
    """字串 → 未正規化的五元組；空字串回 None（＝預設）。接受三種寫法：

    - 預設名稱：`default` `wuge` `bazi` `sound` `equal`
    - 項目＝權重：`三才五格=1,其他=0`、`wuge=2`（沒點到的項目維持預設值，除非給了「其他」）
    - 五個數字：`0,0,0,1,0`（順序：文化 五行 生肖 五格 音韻）
    """
    s = (text or '').strip()
    if not s:
        return None
    if s in PRESETS:
        return PRESETS[s]
    parts = [p.strip() for p in re.split(r'[,;、\s]+', s) if p.strip()]
    if all('=' not in p and ':' not in p for p in parts):
        if len(parts) != 5:
            raise ValueError('位置式權重需為 5 個數字：文化,五行,生肖,五格,音韻')
        return tuple(_weight_num(DIM_NAMES[k], p) for k, p in zip(DIMS, parts))
    named: dict[str, float] = {}
    other: float | None = None
    for p in parts:
        k, _, v = p.replace(':', '=').partition('=')
        k = k.strip()
        if k in WEIGHT_OTHER:
            other = _weight_num(k, v.strip())
            continue
        key = k if k in DIMS else WEIGHT_ALIASES.get(k)
        if key is None:
            raise ValueError(f'未知的權重項目「{k}」（可用：' + '、'.join(DIM_NAMES.values()) + '、其他）')
        named[key] = _weight_num(k, v.strip())
    return tuple(named.get(k, WEIGHTS[k] if other is None else other) for k in DIMS)


def weights_text(w: tuple[float, ...]) -> str:
    """正規化後的權重 → 「文化 20%、五行 25%…」；只列權重不為 0 的項目。"""
    parts = [f'{DIM_NAMES[k]} {round1(v * 100):g}%' for k, v in zip(DIMS, w) if v > 0]
    return '、'.join(parts) if parts else '（無）'


def is_default_weights(w: tuple[float, ...]) -> bool:
    return tuple(w) == DEFAULT_WEIGHTS


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
    weights: tuple[float, ...] = field(default=DEFAULT_WEIGHTS)  # 已正規化

    @property
    def scores(self) -> tuple[float, ...]:
        return (self.wenhua, self.wuxing, self.shengxiao, self.wuge, self.yinyun)


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


def total_of(wenhua: float, wuxing: float, shengxiao: float, wuge: float, yinyun_: float,
             w: tuple[float, ...] = DEFAULT_WEIGHTS) -> float:
    """加權總分；w 必須是 normalize_weights 的輸出。JS 端必須使用相同的運算順序。"""
    return round1(wenhua * w[0] + wuxing * w[1] + shengxiao * w[2] + wuge * w[3] + yinyun_ * w[4])


def rate_name(l1: int, l2: int, c1: CharInfo, c2: CharInfo, fate: FateData | None, weights=None) -> Rating:
    w = normalize_weights(weights)
    wh, d1 = rate_wenhua(c1, c2)
    wx, d2 = rate_wuxing(c1, c2, fate)
    sx, d3 = rate_shengxiao(c1, c2, fate)
    wg, d4, g, key = rate_wuge(l1, l2, c1.stroke, c2.stroke)
    yy, d5 = rate_yinyun(c1, c2)
    total = total_of(wh, wx, sx, wg, yy, w)
    return Rating(wh, wx, sx, wg, yy, total, grade(total), g, key,
                  {'wenhua': d1, 'wuxing': d2, 'shengxiao': d3, 'wuge': d4, 'yinyun': d5}, w)
