"""八字與喜用神（移植 fate internal/chronosfate；農曆/四柱由 lunar_python 計算，與瀏覽器端 lunar-javascript 同作者同演算法）。

Nova 修正：評分讀取使用者選定方法（balance / geju）算出的用神與忌神；fate 的方法切換只影響報告。
Nova 修正：五行分數以「十分之一」整數累加（藏干權重皆為 0.1 的倍數），避免浮點雜訊影響強弱判斷，
           Python 與 JS 結果必然一致。
Nova 新增：時辰不詳時只以年、月、日三柱計五行強弱，時柱留空。
"""
from __future__ import annotations

from dataclasses import dataclass

from . import tables

try:
    from lunar_python import Solar
except ImportError:  # pragma: no cover
    Solar = None

GAN = '甲乙丙丁戊己庚辛壬癸'
ZHI = '子丑寅卯辰巳午未申酉戌亥'
ZODIAC = '鼠牛虎兔龍蛇馬羊猴雞狗豬'   # 依年柱地支（立春為界），與八字一致
ELEMENTS = '木火土金水'
METHODS = ('balance', 'geju')


@dataclass
class FateData:
    sizhu: list[str]          # 年柱 月柱 日柱 時柱（干支；時辰不詳時時柱為空字串）
    hour_known: bool
    day_gan: str
    day_wx: str
    zodiac: str
    fen: dict[str, float]     # 五行分數（天干 1.0 + 藏干加權），供顯示
    total: float
    qiangruo: str             # 強 | 弱
    method: str               # balance | geju
    yong: str                 # 用神（評分 +12）
    xi: str                   # 喜神
    ji: str                   # 忌神（評分 -8）
    chou: str                 # 仇神
    geju: str | None          # 格局名（geju 法）
    note: str                 # 例如 geju 法退回 balance 的原因
    hidden: list[list[str]]   # 各柱藏干


def _bt() -> dict:
    return tables.bazi()


def four_pillars(year: int, month: int, day: int, hour: int, minute: int) -> list[str]:
    if Solar is None:
        raise ImportError('lunar_python 未安裝：pip install lunar_python')
    ec = Solar.fromYmdHms(year, month, day, hour, minute, 0).getLunar().getEightChar()
    return [ec.getYear(), ec.getMonth(), ec.getDay(), ec.getTime()]


def wuxing_tenths(pillars: list[str]) -> dict[str, int]:
    """五行分數 ×10（整數）：每柱天干 +10，地支藏干依權重（0.6 → 6）。"""
    bt = _bt()
    t = {e: 0 for e in ELEMENTS}
    for gz in pillars:
        gan, zhi = gz[0], gz[1]
        t[bt['tiangan_wuxing'][gan]] += 10
        for stem, w in bt['hidden_stems'][zhi]:
            t[bt['tiangan_wuxing'][stem]] += round(w * 10)
    return t


def judge_strength(tenths: dict[str, int], day_wx: str) -> str:
    """同類（自身 + 生我）分數 > 總分/2 為強。"""
    total = sum(tenths[e] for e in ELEMENTS)
    mine = tenths[day_wx] + tenths[_bt()['sheng_wo'][day_wx]]
    return '強' if mine * 2 > total else '弱'


def balance(tenths: dict[str, int], day_wx: str, qiangruo: str) -> tuple[str, str, str, str]:
    """平衡法（chronosfate/xiyong_balance.go）→ (用, 喜, 忌, 仇)。"""
    bt = _bt()
    if qiangruo == '強':
        yong, xi, ji, chou = bt['ke_wo'][day_wx], bt['sheng'][day_wx], day_wx, bt['sheng_wo'][day_wx]
    else:
        yong, xi, ji, chou = day_wx, bt['sheng_wo'][day_wx], bt['ke_wo'][day_wx], bt['ke'][day_wx]
    weakest = min(ELEMENTS, key=lambda e: tenths[e])         # 木火土金水 序中第一個最小者
    if qiangruo == '弱' and weakest != day_wx:
        yong = weakest
    xian = next((e for e in ELEMENTS if tenths[e] == 0), '')  # 缺的五行
    if xian and qiangruo == '強':
        chou = xian
    return yong, xi, ji, chou


def geju(pillars: list[str], day_gan: str) -> tuple[str | None, tuple[str, str, str, str] | None, str]:
    """格局法（chronosfate/xiyong_geju.go）：月令主氣 → 十神 → 八正格 → (用, 喜, 忌, 仇)。
    比肩/劫財 月令不在八正格內 → 回 (None, None, 十神)。"""
    bt = _bt()
    main_qi = bt['hidden_stems'][pillars[1][1]][0][0]
    ss = bt['shishen'][day_gan][main_qi]
    name = bt['shishen_to_geju'].get(ss)
    if not name:
        return None, None, ss
    day_wx = bt['tiangan_wuxing'][day_gan]
    rel = {'self': day_wx, 'sheng_wo': bt['sheng_wo'][day_wx], 'ke_wo': bt['ke_wo'][day_wx],
           'wo_sheng': bt['sheng'][day_wx], 'wo_ke': bt['ke'][day_wx]}
    rule = bt['geju_rules'][name]
    return name, tuple(rel[rule[k]] for k in ('yong', 'xi', 'ji', 'chou')), ss


def compute(year: int, month: int, day: int, hour: int | None = None, minute: int = 0,
            method: str = 'balance') -> FateData:
    if method not in METHODS:
        raise ValueError(f'method 必須為 {METHODS}')
    hour_known = hour is not None
    pillars = four_pillars(year, month, day, hour if hour_known else 12, minute if hour_known else 0)
    if not hour_known:
        pillars[3] = ''
    used = pillars if hour_known else pillars[:3]
    bt = _bt()
    day_gan = pillars[2][0]
    day_wx = bt['tiangan_wuxing'][day_gan]
    tenths = wuxing_tenths(used)
    fen = {e: tenths[e] / 10 for e in ELEMENTS}
    total = sum(tenths[e] for e in ELEMENTS) / 10
    qiangruo = judge_strength(tenths, day_wx)
    zodiac = ZODIAC[ZHI.index(pillars[0][1])]
    yong, xi, ji, chou = balance(tenths, day_wx, qiangruo)
    gname, gelems, ss = geju(pillars, day_gan)
    note = ''
    if method == 'geju':
        if gelems:
            yong, xi, ji, chou = gelems
        else:
            note = f'月令主氣十神為{ss}，不在八正格內，改用平衡法'
    hidden = [[s for s, _ in bt['hidden_stems'][gz[1]]] if gz else [] for gz in pillars]
    return FateData(pillars, hour_known, day_gan, day_wx, zodiac, fen, total, qiangruo,
                    method, yong, xi, ji, chou, gname, note, hidden)
