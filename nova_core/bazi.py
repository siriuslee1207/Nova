"""八字與喜用神（移植 fate internal/chronosfate；農曆/四柱由 lunar_python 計算，與瀏覽器端 lunar-javascript 同作者同演算法）。

Nova 修正：評分讀取使用者選定方法（balance / geju）算出的用神與忌神；fate 的方法切換只影響報告。
Nova 修正：五行分數以「十分之一」整數累加（藏干權重皆為 0.1 的倍數），避免浮點雜訊影響強弱判斷，
           Python 與 JS 結果必然一致。
Nova 新增：時辰不詳時只以年、月、日三柱計五行強弱，時柱留空。
Nova 修正：晚子時（23:00–23:59）日柱以次日計（lunar 的 sect=1）；時柱本來就以次日日干起算，不受影響。
Nova 修正：用、喜、忌、仇四神必互不相同。fate 原版平衡法「身弱取全盤最弱五行為用神」「身強以缺的五行為仇神」
           會讓用神撞上忌神或仇神（例：日主木身弱而土最少 → 用神土、仇神土），改為依致強／致弱之因取用
           （規則表 bazi_tables.json fuyi_rules）；格局法的八正格喜忌改依子平順用／逆用（geju_rules）。
           兩張規則表都附 why 說明文字，放進 FateData.note 供畫面與 CLI 顯示。
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
REL_KEYS = ('yong', 'xi', 'ji', 'chou')


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
    geju: str | None          # 格局名（月令主氣十神所定；兩種方法都會算出來供顯示）
    note: str                 # 取用說明（規則表 why；geju 法退回平衡法時含原因）
    hidden: list[list[str]]   # 各柱藏干


def _bt() -> dict:
    return tables.bazi()


def four_pillars(year: int, month: int, day: int, hour: int, minute: int) -> list[str]:
    if Solar is None:
        raise ImportError('lunar_python 未安裝：pip install lunar_python')
    ec = Solar.fromYmdHms(year, month, day, hour, minute, 0).getLunar().getEightChar()
    ec.setSect(1)   # 晚子時（23:00 起）日柱算次日；預設 sect=2 會算當天
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


def relations(day_wx: str) -> dict[str, str]:
    """日主五行 → 各十神的五行：self 比劫、sheng_wo 印、ke_wo 官殺、wo_sheng 食傷、wo_ke 財。"""
    bt = _bt()
    return {'self': day_wx, 'sheng_wo': bt['sheng_wo'][day_wx], 'ke_wo': bt['ke_wo'][day_wx],
            'wo_sheng': bt['sheng'][day_wx], 'wo_ke': bt['ke'][day_wx]}


def apply_rule(rule: dict, day_wx: str) -> tuple[str, str, str, str]:
    """規則表的一列（十神關係名）→ (用, 喜, 忌, 仇) 五行。"""
    rel = relations(day_wx)
    return tuple(rel[rule[k]] for k in REL_KEYS)


def balance(tenths: dict[str, int], day_wx: str, qiangruo: str) -> tuple[str, str, str, str, str]:
    """平衡法（扶抑）→ (用, 喜, 忌, 仇, 說明)。
    身強：忌＝印、比劫中較旺者（致強之因），仇＝另一者；印旺→用財破印、喜食傷；比劫旺→用官殺制身、喜財。
    身弱：忌＝官殺、財、食傷中最旺者（致弱之因，同分依此序）；官殺旺／食傷旺→用印、喜比劫、仇財；財旺→用比劫、喜印、仇食傷。
    規則表：bazi_tables.json fuyi_rules。"""
    rel = relations(day_wx)
    if qiangruo == '強':
        cause = '印旺' if tenths[rel['sheng_wo']] > tenths[rel['self']] else '比劫旺'
    else:
        drains = (('官殺旺', rel['ke_wo']), ('財旺', rel['wo_ke']), ('食傷旺', rel['wo_sheng']))
        cause = max(drains, key=lambda d: tenths[d[1]])[0]   # max 取序中第一個最大者
    rule = _bt()['fuyi_rules'][cause]
    return (*apply_rule(rule, day_wx), rule['why'])


def geju(pillars: list[str], day_gan: str) -> tuple[str | None, tuple[str, str, str, str] | None, str, str]:
    """格局法：月令主氣 → 十神 → 八正格 → (格名, (用, 喜, 忌, 仇), 十神, 說明)。
    比肩/劫財 月令不在八正格內 → (None, None, 十神, '')。規則表：bazi_tables.json geju_rules。"""
    bt = _bt()
    main_qi = bt['hidden_stems'][pillars[1][1]][0][0]
    ss = bt['shishen'][day_gan][main_qi]
    name = bt['shishen_to_geju'].get(ss)
    if not name:
        return None, None, ss, ''
    rule = bt['geju_rules'][name]
    return name, apply_rule(rule, bt['tiangan_wuxing'][day_gan]), ss, rule['why']


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
    yong, xi, ji, chou, note = balance(tenths, day_wx, qiangruo)
    gname, gelems, ss, gwhy = geju(pillars, day_gan)
    if method == 'geju':
        if gelems:
            yong, xi, ji, chou = gelems
            note = gwhy
        else:
            note = f'月令主氣十神為{ss}，不在八正格內，改用平衡法：{note}'
    hidden = [[s for s, _ in bt['hidden_stems'][gz[1]]] if gz else [] for gz in pillars]
    return FateData(pillars, hour_known, day_gan, day_wx, zodiac, fen, total, qiangruo,
                    method, yong, xi, ji, chou, gname, note, hidden)
