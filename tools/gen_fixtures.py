"""Generate tests/fixtures/golden.json (+ golden.gen.js) from the Python reference implementation.

The JS engine must reproduce every value exactly (see tests/parity_core.js, run via
`node tests/parity.mjs` or by opening tests/parity.html).

Run: .venv/Scripts/python tools/gen_fixtures.py
"""
from __future__ import annotations

import json
import random
import sys
from dataclasses import asdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from nova_core import bazi, chars, rating  # noqa: E402
from nova_core.generator import Options, generate, lucky_combos  # noqa: E402

OUT = ROOT / 'tests' / 'fixtures'
SEED = 20260903

SURNAMES = ['陳', '林', '黃', '張', '李', '王', '吳', '劉', '蔡', '楊', '謝', '戴', '余', '成', '歐陽', '司徒', '張簡']
# 含節氣邊界（2026 立春 2/4）、跨年、晚子時、閏日、時辰不詳
BIRTHS = [
    (2026, 9, 3, 10, 30), (2026, 2, 3, 23, 59), (2026, 2, 4, 0, 0), (2026, 2, 4, 12, 0), (2026, 2, 5, 6, 0),
    (2025, 1, 15, 8, 0), (2024, 12, 31, 23, 30), (2024, 12, 31, 0, 10), (2000, 2, 29, 12, 0), (1999, 12, 31, 23, 45),
    (2012, 6, 21, 0, 0), (2018, 11, 7, 1, 30), (1985, 8, 8, 8, 8), (2031, 5, 5, 17, 20), (2026, 9, 3, None, 0),
    (2025, 1, 15, None, 0), (1990, 3, 21, None, 0),
]


def fate_input(b, method):
    y, m, d, h, mi = b
    return {'year': y, 'month': m, 'day': d, 'hour': h, 'minute': mi, 'method': method}


def fate_expect(f: bazi.FateData) -> dict:
    d = asdict(f)
    d.pop('hidden')
    return d


def char_out(c: chars.CharInfo) -> dict:
    return {'char': c.char, 'stroke': c.stroke, 'wx': c.wx, 'lvl': c.lvl}


def surname_strokes(s: str) -> tuple[int, int]:
    st = [chars.lookup(ch).stroke for ch in s]
    return (st[0], st[1] if len(st) > 1 else 0)


def main() -> None:
    rnd = random.Random(SEED)
    pool = [c for c in chars.all_chars().values() if c.lvl <= 2 and c.nameable]
    pool.sort(key=lambda c: c.char)

    fates = []
    for b in BIRTHS:
        for method in bazi.METHODS:
            f = bazi.compute(*b, method=method)
            fates.append({'input': fate_input(b, method), 'expect': fate_expect(f)})

    ratings = []
    fate_objs = [None] + [bazi.compute(*b, method=m) for b in BIRTHS[:6] for m in bazi.METHODS]
    for _ in range(500):
        s = rnd.choice(SURNAMES)
        l1, l2 = surname_strokes(s)
        c1, c2 = rnd.choice(pool), rnd.choice(pool)
        fi = rnd.randrange(len(fate_objs))
        r = rating.rate_name(l1, l2, c1, c2, fate_objs[fi])
        ratings.append({
            'input': {'l1': l1, 'l2': l2, 'c1': c1.char, 'c2': c2.char, 'fate': fates_index(fate_objs[fi], fates) if fi else None},
            'expect': {'wenhua': r.wenhua, 'wuxing': r.wuxing, 'shengxiao': r.shengxiao, 'wuge': r.wuge, 'yinyun': r.yinyun,
                       'total': r.total, 'grade': r.grade, 'ge': r.ge.as_dict() if r.ge else None, 'sancai_key': r.sancai_key},
        })

    combos = []
    for s, strictness, female in [('陳', 'moderate', False), ('陳', 'strict', True), ('林', 'relaxed', False),
                                  ('歐陽', 'moderate', False), ('王', 'strict', False), ('謝', 'moderate', True)]:
        l1, l2 = surname_strokes(s)
        cs = lucky_combos(l1, l2, Options(strictness=strictness, exclude_female_caution=female))
        combos.append({'input': {'l1': l1, 'l2': l2, 'strictness': strictness, 'exclude_female_caution': female},
                       'expect': {'count': len(cs), 'pairs': [[c.f1, c.f2, c.wuge_score, c.sancai_key] for c in cs]}})

    gens = []
    configs = [
        ('陳', BIRTHS[0], 'balance', dict(exclude_female_caution=True)),
        ('陳', BIRTHS[0], 'geju', dict(per_first_char=2)),
        ('林', BIRTHS[5], 'balance', dict(max_level=1, per_first_char=2)),
        ('歐陽', None, None, dict()),
        ('歐陽', None, None, dict(per_first_char=1, strictness='strict')),
        ('黃', BIRTHS[6], 'balance', dict(strictness='relaxed', per_first_char=2, top_n=15)),
        ('李', BIRTHS[14], 'balance', dict(fixed_first='冠', per_first_char=0)),
        ('王', BIRTHS[8], 'geju', dict(avoid_chars=frozenset('宇冠'), require_chars=frozenset('安平和'), per_first_char=2)),
        ('謝', BIRTHS[15], 'balance', dict(max_level=3, per_first_char=3, top_n=8)),
        ('余', None, None, dict(fixed_second='安')),
    ]
    for s, b, method, kw in configs:
        l1, l2 = surname_strokes(s)
        f = bazi.compute(*b, method=method) if b else None
        opt = Options(**kw)
        res = generate(l1, l2, f, opt)
        gens.append({
            'input': {'surname': s, 'l1': l1, 'l2': l2, 'fate': fate_input(b, method) if b else None,
                      'options': {'strictness': opt.strictness, 'exclude_female_caution': opt.exclude_female_caution,
                                  'max_level': opt.max_level, 'avoid_chars': sorted(opt.avoid_chars),
                                  'require_chars': sorted(opt.require_chars), 'fixed_first': opt.fixed_first,
                                  'fixed_second': opt.fixed_second, 'top_n': opt.top_n, 'per_first_char': opt.per_first_char}},
            'expect': [{'name': c.name, 'total': c.total, 'grade': c.grade, 'scores': list(c.scores),
                        'f1': c.combo.f1, 'f2': c.combo.f2} for c in res],
        })

    # 提示字串：Python 與 JS 由同一模板產生，必須逐字相同
    from nova_core.llm.advisor import build_explain, build_recommend
    prompts = []
    for s, b, method, gender, name, kw in [('陳', BIRTHS[0], 'balance', 'girl', '冠宇', dict(exclude_female_caution=True)),
                                            ('歐陽', None, None, 'boy', '丞亮', dict(strictness='strict')),
                                            ('林', BIRTHS[15], 'geju', 'boy', '愉修', dict(max_level=1))]:
        l1, l2 = surname_strokes(s)
        f = bazi.compute(*b, method=method) if b else None
        opt = Options(**kw)
        req = build_recommend(s, l1, l2, gender, f, lucky_combos(l1, l2, opt), chars.by_stroke(opt.max_level), n=8, preferences='喜歡自然意象')
        c1, c2 = chars.lookup(name[0]), chars.lookup(name[1])
        system, user = build_explain(s, c1, c2, rating.rate_name(l1, l2, c1, c2, f), f)
        prompts.append({'input': {'surname': s, 'l1': l1, 'l2': l2, 'gender': gender, 'fate': fate_input(b, method) if b else None,
                                  'options': {'strictness': opt.strictness, 'exclude_female_caution': opt.exclude_female_caution,
                                              'max_level': opt.max_level}, 'name': name, 'preferences': '喜歡自然意象'},
                        'expect': {'system': req.system, 'recommend_user': req.user, 'explain_user': user,
                                   'allowed_strokes': sorted(req.allowed)}})

    golden = {
        'meta': {'generated': date.today().isoformat(), 'seed': SEED, 'chars_version': chars._payload()['version'],
                 'chars_generated': chars._payload()['generated']},
        'bazi': fates, 'rating': ratings, 'combos': combos, 'generate': gens, 'prompts': prompts,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    text = json.dumps(golden, ensure_ascii=False, separators=(',', ':'))
    (OUT / 'golden.json').write_text(text, encoding='utf-8')
    (OUT / 'golden.gen.js').write_text('globalThis.NOVA_GOLDEN = ' + text + ';\n', encoding='utf-8')
    print(f'golden: bazi {len(fates)}, rating {len(ratings)}, combos {len(combos)}, generate {len(gens)} '
          f'({len(text.encode("utf-8")) // 1024} KB)')


def fates_index(f: bazi.FateData, fates: list[dict]) -> dict:
    """Return the input spec for a FateData by matching its sizhu/method in the fates list."""
    for entry in fates:
        e = entry['expect']
        if e['sizhu'] == f.sizhu and e['method'] == f.method and e['hour_known'] == f.hour_known:
            return entry['input']
    raise KeyError('fate not found')


if __name__ == '__main__':
    main()
