"""評分與八字：手算案例（陳冠宇，2026-09-03 10:30）。依賴 data/gen/chars.json 與 lunar_python。"""
import random

import pytest

from nova_core import bazi, chars, generator, rating

pytest.importorskip('lunar_python')


@pytest.fixture(scope='module')
def fate():
    return bazi.compute(2026, 9, 3, 10, 30, method='balance')


def test_bazi_pillars_and_strength(fate):
    assert fate.sizhu == ['丙午', '丙申', '庚辰', '辛巳']
    assert fate.day_gan == '庚' and fate.day_wx == '金' and fate.zodiac == '馬'
    # 天干各 1.0；藏干：午 丁.7己.3、申 庚.6壬.3戊.1、辰 戊.6乙.2癸.2、巳 丙.6庚.3戊.1
    assert fate.fen == {'木': 0.2, '火': 3.3, '土': 1.1, '金': 2.9, '水': 0.5}
    assert fate.total == 8.0
    assert fate.qiangruo == '弱'  # 同類 金+土 = 4.0，不大於 8.0/2
    # 平衡法（弱）：用=自身→但最弱且非日主者取代 → 木；喜=生我 土；忌=克我 火；仇=我克 木
    assert (fate.yong, fate.xi, fate.ji, fate.chou) == ('木', '土', '火', '木')


def test_bazi_geju_and_hour_unknown():
    g = bazi.compute(2026, 9, 3, 10, 30, method='geju')
    # 月支申 主氣庚，日主庚 → 比肩，不在八正格 → 退回平衡法
    assert g.geju is None and '比肩' in g.note and (g.yong, g.ji) == ('木', '火')
    h = bazi.compute(2026, 9, 3)
    assert h.hour_known is False and h.sizhu[:3] == ['丙午', '丙申', '庚辰']
    assert h.fen == {'木': 0.2, '火': 2.7, '土': 1.0, '金': 1.6, '水': 0.5}


def test_rate_name_no_fate():
    c1, c2 = chars.lookup('冠'), chars.lookup('宇')
    assert c1.stroke == 9 and c2.stroke == 6 and c1.py[0] == 'guan4' and c2.py[0] == 'yu3'
    r = rating.rate_name(16, 0, c1, c2, None)
    assert (r.ge.tian, r.ge.ren, r.ge.di, r.ge.wai, r.ge.zong) == (17, 25, 15, 7, 31)
    assert r.sancai_key == '金土土'
    assert r.wenhua == 92 and r.wuxing == 80 and r.shengxiao == 80 and r.yinyun == 97
    # 天17半吉 8×.15、人25半吉 8×.30、地15吉 15×.20、外7吉 15×.15、總31吉 15×.20、三才大吉 +12
    assert r.wuge == pytest.approx(83.85)
    assert r.total == 86.1 and r.grade == '上吉'


def test_rate_name_with_fate(fate):
    c1, c2 = chars.lookup('冠'), chars.lookup('宇')
    r = rating.rate_name(16, 0, c1, c2, fate)
    assert r.wuxing == 77   # 冠木=用神 +12；木克土 -5
    assert r.shengxiao == 94  # 馬火：木生火 +7、火生土 +7
    assert r.total == 86.8


def test_char_levels_and_exclusions():
    assert chars.lookup('冠').lvl == 1 and chars.lookup('宇').lvl == 1          # 常見取名用字
    assert chars.lookup('嚥').lvl == 2 and chars.lookup('嚥').regular            # Big5 常用
    assert chars.lookup('淼').lvl == 1                                          # 次常用區但在取名用字表
    assert chars.lookup('七').nameable is False and chars.lookup('的').nameable is False  # 排除字
    assert chars.lookup('謝').stroke == 17 and chars.lookup('戴').stroke == 18


def test_fast_path_matches_reference(fate):
    pool = [c for c in chars.all_chars().values() if c.lvl <= 2 and c.nameable]
    rnd = random.Random(7)
    for f in (None, fate):
        for _ in range(300):
            a, b = rnd.choice(pool), rnd.choice(pool)
            combo = generator.StrokeCombo(a.stroke, b.stroke, None, '', rating.rate_wuge(16, 0, a.stroke, b.stroke)[0], ())
            fast = generator.fast_scores(generator.precompute(a, f), generator.precompute(b, f), combo, f)
            ref = rating.rate_name(16, 0, a, b, f)
            assert fast == (ref.wenhua, ref.wuxing, ref.shengxiao, ref.wuge, ref.yinyun), (a.char, b.char)
            assert rating.total_of(*fast) == ref.total


def test_generate_top10_is_deterministic_and_sorted(fate):
    opt = generator.Options(top_n=10)
    res1 = generator.generate(16, 0, fate, opt)
    res2 = generator.generate(16, 0, fate, opt)
    assert [c.name for c in res1] == [c.name for c in res2] and len(res1) == 10
    totals = [c.total for c in res1]
    assert totals == sorted(totals, reverse=True)
    for c in res1:
        assert c.full_rating(16, 0, fate).total == c.total


def test_generate_fixed_first_and_avoid(fate):
    res = generator.generate(16, 0, fate, generator.Options(top_n=5, fixed_first='冠', avoid_chars=frozenset('宇')))
    assert res and all(c.c1.char == '冠' and c.c2.char != '宇' for c in res)


def test_generate_per_first_char_diversity(fate):
    res = generator.generate(16, 0, fate, generator.Options(top_n=10, per_first_char=2))
    assert len(res) == 10
    firsts = [c.c1.char for c in res]
    assert max(firsts.count(ch) for ch in set(firsts)) <= 2
    totals = [c.total for c in res]
    assert totals == sorted(totals, reverse=True)
