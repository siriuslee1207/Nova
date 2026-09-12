"""筆畫組合選字（對應 src/js/core/combos.js）：列出姓氏筆畫下所有合格的名字筆畫組合 (f1, f2)。

篩選鏈與 generator.lucky_combos 獨立（那邊看「嚴格度」）：
三才等級（謝達輝表 data/tables/sancai_cdi.json，預設 最吉／吉）→ 勾選的格（預設五格全部，含天格）皆為 36 吉數
（data/tables/jishu36.json）→ 人地外總四格的吉數等級（data/tables/jishu_grade.json，預設五級全收＝不限制）→
（可選）排除女性不宜總格。迭代 f1 升冪、f2 升冪，Python 與 JS 逐列相同。
吉數與等級是兩條獨立的條件：吉數看勾選的格（可含天格），等級一律只看名字改得動的人、地、外、總四格
（GRADE_GRIDS）——天格由姓氏決定，不納入等級條件，只在列表中標示供參考。
天格只由姓氏決定：勾了天格而天格不是吉數時結果必為空，enumerate_combos 直接回空列表。
"""
from __future__ import annotations

from dataclasses import dataclass

from . import dayan, sancai
from .chars import CharInfo, by_stroke
from .rating import rate_wuge
from .wuge import MAX_STROKE, WuGe, calc_wuge

GRIDS = ('tian', 'ren', 'di', 'wai', 'zong')
GRADE_GRIDS = ('ren', 'di', 'wai', 'zong')              # 吉數等級只管這四格（天格由姓氏決定，撇除）
DEFAULT_GRADES = frozenset({'最吉', '吉'})
DEFAULT_JISHU_GRADES = frozenset(dayan.GRADES)          # 預設五級全收＝不加限制（結果與沒有這條件時相同）


@dataclass(frozen=True)
class ComboFilter:
    sancai_grades: frozenset[str] = DEFAULT_GRADES     # 子集合 ⊂ sancai.CDI_SELECTABLE
    grids: tuple[str, ...] = GRIDS                      # 須為吉數的格（依 GRIDS 順序）
    jishu_grades: frozenset[str] = DEFAULT_JISHU_GRADES  # 人地外總四格都要落在這些吉數等級內 ⊂ dayan.GRADES
    exclude_female_caution: bool = False                # 排除 女性不宜 總格（21 23 28 33）
    min_stroke: int = 1
    max_stroke: int = MAX_STROKE


@dataclass(frozen=True)
class ComboRow:
    f1: int
    f2: int
    ge: WuGe
    sancai_key: str
    cdi_grade: str            # 謝達輝表等級（過濾依據）
    cdi_no: int               # 該站組別 1..125
    fate_verdict: str         # 原表（sancai125）吉凶，僅供對照
    jishu: dict[str, bool]    # 五格各格是否為吉數 {'tian':…, 'ren':…, 'di':…, 'wai':…, 'zong':…}
    grades: dict[str, str]    # 五格各格的吉數等級（大吉／吉／半吉／半凶／凶）
    wuge_score: float         # rating.rate_wuge 的五格分（原評分，供排序／顯示）

    def as_dict(self) -> dict:
        return {'f1': self.f1, 'f2': self.f2, 'ge': self.ge.as_dict(), 'sancai_key': self.sancai_key,
                'cdi_grade': self.cdi_grade, 'cdi_no': self.cdi_no, 'fate_verdict': self.fate_verdict,
                'jishu': dict(self.jishu), 'grades': dict(self.grades), 'wuge_score': self.wuge_score}


def tian_of(l1: int, l2: int) -> int:
    """天格只看姓氏筆畫（單姓 l1+1、複姓 l1+l2）。"""
    return calc_wuge(l1, l2, 1, 1).tian


def tian_ok(l1: int, l2: int) -> bool:
    return dayan.is_jishu(tian_of(l1, l2))


def combo_row(l1: int, l2: int, f1: int, f2: int) -> ComboRow:
    """不過濾，直接描述一組筆畫組合。"""
    g = calc_wuge(l1, l2, f1, f2)
    key = sancai.key_of(g.tian, g.ren, g.di)
    js = {k: dayan.is_jishu(getattr(g, k)) for k in GRIDS}
    gr = {k: dayan.grade(getattr(g, k)) for k in GRIDS}
    score, _, _, _ = rate_wuge(l1, l2, f1, f2)
    return ComboRow(f1, f2, g, key, sancai.cdi_grade(key), sancai.cdi_no(key), sancai.verdict(key), js, gr, score)


def enumerate_combos(l1: int, l2: int, filt: ComboFilter = ComboFilter()) -> list[ComboRow]:
    if 'tian' in filt.grids and not tian_ok(l1, l2):
        return []
    out: list[ComboRow] = []
    for f1 in range(filt.min_stroke, filt.max_stroke + 1):
        for f2 in range(filt.min_stroke, filt.max_stroke + 1):
            g = calc_wuge(l1, l2, f1, f2)
            key = sancai.key_of(g.tian, g.ren, g.di)
            grade = sancai.cdi_grade(key)
            if grade not in filt.sancai_grades:
                continue
            js = {k: dayan.is_jishu(getattr(g, k)) for k in GRIDS}
            if not all(js[k] for k in filt.grids):
                continue
            gr = {k: dayan.grade(getattr(g, k)) for k in GRIDS}
            if not all(gr[k] in filt.jishu_grades for k in GRADE_GRIDS):
                continue
            if filt.exclude_female_caution and dayan.find(g.zong).female_caution:
                continue
            score, _, _, _ = rate_wuge(l1, l2, f1, f2)
            out.append(ComboRow(f1, f2, g, key, grade, sancai.cdi_no(key), sancai.verdict(key), js, gr, score))
    return out


def group_by_first(rows: list[ComboRow]) -> list[tuple[int, list[ComboRow]]]:
    """依第一字筆畫分組（f1 升冪，沿用 rows 的順序）。"""
    groups: list[tuple[int, list[ComboRow]]] = []
    for r in rows:
        if groups and groups[-1][0] == r.f1:
            groups[-1][1].append(r)
        else:
            groups.append((r.f1, [r]))
    return groups


def char_lists(f1: int, f2: int, max_level: int = 2, avoid: frozenset[str] = frozenset()) -> tuple[list[CharInfo], list[CharInfo]]:
    """兩個筆畫各自的候選字（by_stroke 順序：等級、字元），去掉排除字。"""
    buckets = by_stroke(max_level)

    def pick(s: int) -> list[CharInfo]:
        return [c for c in buckets.get(s, []) if c.char not in avoid]

    return pick(f1), pick(f2)
