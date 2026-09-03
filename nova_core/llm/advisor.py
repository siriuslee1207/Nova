"""AI 顧問（對應 src/js/llm/advisor.js）：組提示、驗證模型輸出。推薦用字只能從合格筆畫組合與候選字池中選。"""
from __future__ import annotations

from dataclasses import dataclass

from .. import dayan, sancai
from ..bazi import ELEMENTS, FateData
from ..chars import CharInfo, lookup
from ..generator import StrokeCombo
from ..rating import Rating
from .base import render

PICKS_SCHEMA = {
    'type': 'object',
    'properties': {
        'picks': {
            'type': 'array',
            'items': {
                'type': 'object',
                'properties': {'first': {'type': 'string'}, 'second': {'type': 'string'}, 'reason': {'type': 'string'}},
                'required': ['first', 'second', 'reason'],
            },
        },
    },
    'required': ['picks'],
}
MAX_COMBOS = 12
MAX_PER_STROKE = 40


def num(x) -> str:
    """數字轉字串，與 JS String(x) 一致（90.0 → '90'，86.8 → '86.8'）。"""
    if isinstance(x, float):
        s = repr(x)
        return s[:-2] if s.endswith('.0') else s
    return str(x)


def bazi_summary(fate: FateData | None) -> str:
    if fate is None:
        return '無（未提供出生時間）'
    sz = ' '.join(gz or ('時辰不詳' if i == 3 else '') for i, gz in enumerate(fate.sizhu) if gz or i == 3)
    method = '格局法' if fate.method == 'geju' else '平衡法'
    return (f'{sz}；日主 {fate.day_gan}{fate.day_wx}（{fate.qiangruo}）；五行分佈 '
            + ' '.join(f'{e}{num(fate.fen[e])}' for e in ELEMENTS)
            + f'；{method}{"（" + fate.geju + "）" if fate.geju else ""}{"，" + fate.note if fate.note else ""}')


@dataclass
class RecommendRequest:
    system: str
    user: str
    allowed: dict[int, set[str]]
    combo_set: set[tuple[int, int]]
    top_combos: list[StrokeCombo]


def build_recommend(surname: str, l1: int, l2: int, gender: str, fate: FateData | None,
                    combos: list[StrokeCombo], buckets: dict[int, list[CharInfo]],
                    n: int = 8, preferences: str = '') -> RecommendRequest:
    top = sorted(combos, key=lambda c: -c.wuge_score)[:MAX_COMBOS]
    strokes = sorted({s for c in top for s in (c.f1, c.f2)})
    allowed: dict[int, set[str]] = {}
    pool_lines = []
    for s in strokes:
        lst = buckets.get(s, [])[:MAX_PER_STROKE]
        allowed[s] = {c.char for c in lst}
        if lst:
            pool_lines.append(f'{s}畫：' + ' '.join(f'{c.char}[{c.py[0]},{c.wx}]' for c in lst))
    user = render('recommend_chars', n=n, surname=surname, surname_strokes=f'{l1}+{l2}' if l2 else str(l1),
                  gender='女' if gender == 'girl' else '男', bazi_summary=bazi_summary(fate),
                  yong=fate.yong if fate else '無', xi=fate.xi if fate else '無', ji=fate.ji if fate else '無',
                  chou=fate.chou if fate else '無', zodiac=fate.zodiac if fate else '無',
                  combos='；'.join(f'{c.f1}+{c.f2}：{num(c.wuge_score)}' for c in top),
                  pools='\n'.join(pool_lines), preferences=preferences or '無特別偏好')
    return RecommendRequest(render('system'), user, allowed, {(c.f1, c.f2) for c in top}, top)


def validate_picks(picks, req: RecommendRequest) -> tuple[list[tuple[CharInfo, CharInfo, str]], list[dict]]:
    ok, rejected = [], []
    seen: set[str] = set()
    for p in picks if isinstance(picks, list) else []:
        first, second = str(p.get('first', '')).strip(), str(p.get('second', '')).strip()
        c1, c2 = lookup(first), lookup(second)
        if not c1 or not c2:
            why = '字典查無此字'
        elif first not in req.allowed.get(c1.stroke, set()) or second not in req.allowed.get(c2.stroke, set()):
            why = '不在候選字池'
        elif (c1.stroke, c2.stroke) not in req.combo_set:
            why = '筆畫組合不合格'
        elif first + second in seen:
            why = '重複'
        else:
            why = ''
        if why:
            rejected.append({'first': first, 'second': second, 'reason': p.get('reason', ''), 'why': why})
        else:
            seen.add(first + second)
            ok.append((c1, c2, str(p.get('reason', ''))))
    return ok, rejected


def build_explain(surname: str, c1: CharInfo, c2: CharInfo, r: Rating, fate: FateData | None) -> tuple[str, str]:
    g = r.ge
    wuge_detail = '，'.join(f'{n}{v}（{dayan.find(v).title}・{dayan.find(v).lucky}）' for n, v in
                          (('天格', g.tian), ('人格', g.ren), ('地格', g.di), ('外格', g.wai), ('總格', g.zong))) if g else '無'
    user = render('explain_name', fullname=surname + c1.char + c2.char, pinyin=f'{c1.py[0]} {c2.py[0]}',
                  char_info='\n'.join(f'- {c.char}：{"/".join(c.py)}，{c.stroke}畫，五行{c.wx}，釋義「{c.meaning or "無"}」' for c in (c1, c2)),
                  total=num(r.total), grade=r.grade, wenhua=num(r.wenhua), wuxing=num(r.wuxing), shengxiao=num(r.shengxiao),
                  wuge=num(r.wuge), yinyun=num(r.yinyun), wuge_detail=wuge_detail,
                  sancai=f'{r.sancai_key} {sancai.verdict(r.sancai_key)}：{sancai.detail(r.sancai_key)}' if r.sancai_key else '無',
                  bazi_summary=bazi_summary(fate))
    return render('system'), user
