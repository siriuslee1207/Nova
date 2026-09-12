"""筆畫組合選字：36 吉數表、謝達輝三才表、列舉不變量、CLI。"""
import json
from collections import Counter

import pytest

from nova_core import dayan, sancai
from nova_core.cli import main as cli_main
from nova_core.combos import GRADE_GRIDS, GRIDS, ComboFilter, char_lists, combo_row, enumerate_combos, group_by_first, tian_of, tian_ok
from nova_core.rating import rate_wuge


def pairs(rows):
    return {(r.f1, r.f2) for r in rows}


def test_jishu_table():
    nums = sancai.tables.jishu()['numbers']
    assert len(nums) == 36 and nums == sorted(set(nums)) and all(1 <= n <= 81 for n in nums)
    fate_lucky = {n for n in range(1, 82) if dayan.find(n).lucky == '吉'}
    assert dayan.jishu() == fate_lucky | {8, 17, 18, 25, 39, 55}
    assert dayan.is_jishu(17) and dayan.is_jishu(81) and not dayan.is_jishu(73) and not dayan.is_jishu(9)
    assert dayan.is_jishu(82) == dayan.is_jishu(1) and dayan.is_jishu(81 + 17)
    with pytest.raises(ValueError):
        dayan.is_jishu(0)


def test_jishu_grade_table():
    t = sancai.tables.jishu_grade()
    assert tuple(t['grades']) == dayan.GRADES and set(t['jishu_grades']) == dayan.JISHU_GRADES
    assert len(t['grade']) == len(t['cdi']) == 81
    counts = Counter(t['grade'])
    assert counts == {'大吉': 28, '吉': 8, '半吉': 6, '半凶': 14, '凶': 25} == t['counts']
    assert Counter(t['cdi']) == {'吉': 34, '吉帶凶': 15, '凶帶吉': 4, '凶': 28}
    # 大吉＋吉 恰為 36 吉數；分級規則可由 dayan81 的 lucky × 謝達輝 81 劃表重新導出
    assert {n for n in range(1, 82) if dayan.grade(n) in dayan.JISHU_GRADES} == dayan.jishu()
    for n in range(1, 82):
        fate, cdi = dayan.find(n).lucky, dayan.cdi_grade(n)
        if fate == '吉' and cdi == '吉':
            expect = '大吉'
        elif dayan.is_jishu(n):
            expect = '吉'
        elif fate == '半吉' and cdi in ('吉', '吉帶凶'):
            expect = '半吉'
        elif fate == '半吉' or cdi in ('吉帶凶', '凶帶吉'):
            expect = '半凶'
        else:
            expect = '凶'
        assert dayan.grade(n) == expect, n
    assert dayan.grade(41) == '大吉' and dayan.grade(17) == '吉' and dayan.grade(73) == '半吉'
    assert dayan.grade(26) == '半凶' and dayan.grade(9) == '凶' and dayan.cdi_grade(57) == '凶帶吉'
    assert dayan.grade(82) == dayan.grade(1) and dayan.cdi_grade(81 + 17) == dayan.cdi_grade(17)
    with pytest.raises(ValueError):
        dayan.grade(0)
    with pytest.raises(ValueError):
        dayan.cdi_grade(-1)


def test_cdi_table():
    t = sancai.tables.sancai_cdi()
    assert set(t['combos']) == set(sancai.tables.sancai()['combos'])
    assert Counter(v['grade'] for v in t['combos'].values()) == {'最吉': 16, '吉': 9, '平吉': 12, '半吉': 2, '凶': 67, '最凶': 19}
    e = '木火土金水'
    assert all(v['no'] == 25 * e.index(k[0]) + 5 * e.index(k[1]) + e.index(k[2]) + 1 for k, v in t['combos'].items())
    assert tuple(t['grades']) == sancai.CDI_GRADES and sancai.CDI_SELECTABLE == ('最吉', '吉', '平吉', '半吉')
    assert sancai.cdi_grade('金土土') == '最吉' and sancai.cdi_grade('木木木') == '吉' and sancai.cdi_grade('水水水') == '平吉'
    assert sancai.cdi_grade('木火火') == '半吉' and sancai.cdi_grade('木土水') == '最凶' and sancai.cdi_grade('金金土') == '吉'
    assert sancai.cdi_no('木木木') == 1 and sancai.cdi_no('水水水') == 125


def test_enumerate_chen_default():
    rows = enumerate_combos(16, 0)
    assert len(rows) == 16
    ps = [(r.f1, r.f2) for r in rows]
    assert ps == sorted(ps) and ps[0] == (1, 4)
    r = next(r for r in rows if (r.f1, r.f2) == (19, 28))
    assert r.ge.as_dict() == {'tian': 17, 'ren': 35, 'di': 47, 'wai': 29, 'zong': 63}
    assert r.sancai_key == '金土金' and r.cdi_grade == '最吉' and r.fate_verdict == '大吉' and r.cdi_no == 89
    assert combo_row(16, 0, 19, 28) == r and r.as_dict()['ge'] == r.ge.as_dict()
    for r in rows:
        assert r.cdi_grade in {'最吉', '吉'} and all(r.jishu[k] for k in GRIDS)
        assert r.wuge_score == rate_wuge(16, 0, r.f1, r.f2)[0]


def test_tian_fail_and_uncheck():
    assert tian_of(8, 0) == 9 and not tian_ok(8, 0) and tian_ok(16, 0) and tian_of(15, 17) == 32
    assert enumerate_combos(8, 0) == []
    rows = enumerate_combos(8, 0, ComboFilter(grids=('ren', 'di', 'wai', 'zong')))
    assert len(rows) == 14 and all(r.jishu['tian'] is False for r in rows)


@pytest.mark.parametrize('l1,l2,grids', [(16, 0, GRIDS), (4, 0, GRIDS), (15, 17, GRIDS), (8, 0, GRIDS[1:])])
def test_supersets(l1, l2, grids):
    base = pairs(enumerate_combos(l1, l2, ComboFilter(grids=grids)))
    plus = pairs(enumerate_combos(l1, l2, ComboFilter(sancai_grades=frozenset({'最吉', '吉', '平吉'}), grids=grids)))
    full = pairs(enumerate_combos(l1, l2, ComboFilter(sancai_grades=frozenset(sancai.CDI_SELECTABLE), grids=grids)))
    assert base and base <= plus <= full
    fewer = pairs(enumerate_combos(l1, l2, ComboFilter(grids=tuple(k for k in grids if k not in ('tian', 'wai')))))
    assert base <= fewer


def test_jishu_grade_filter():
    # 預設（五級全收）＝沒有這條件；逐級收緊必為子集
    every = pairs(enumerate_combos(4, 0))
    assert every == pairs(enumerate_combos(4, 0, ComboFilter(jishu_grades=frozenset(dayan.GRADES))))
    prev = every
    for keep in (('大吉', '吉', '半吉', '半凶'), ('大吉', '吉', '半吉'), ('大吉', '吉'), ('大吉',)):
        got = pairs(enumerate_combos(4, 0, ComboFilter(jishu_grades=frozenset(keep))))
        assert got <= prev
        prev = got
    rows = enumerate_combos(4, 0, ComboFilter(jishu_grades=frozenset({'大吉'})))
    assert len(rows) == 11 and all(r.grades[k] == '大吉' for r in rows for k in GRADE_GRIDS)
    assert all(r.grades[k] == dayan.grade(getattr(r.ge, k)) for r in rows for k in GRIDS)
    # 天格撇除：陳 天格 17 是「吉」不是「大吉」，只留大吉時仍要列得出組合（天格不受等級條件管）
    assert GRADE_GRIDS == tuple(k for k in GRIDS if k != 'tian') and dayan.grade(tian_of(16, 0)) == '吉'
    chen = enumerate_combos(16, 0, ComboFilter(jishu_grades=frozenset({'大吉'})))
    assert chen and all(r.grades['tian'] == '吉' and r.grades[k] == '大吉' for r in chen for k in GRADE_GRIDS)
    # 等級看四格、吉數只看勾選的格：不勾任何格時仍受等級限制，且可留下 36 吉數以外的「半吉」數
    loose = enumerate_combos(16, 0, ComboFilter(grids=(), jishu_grades=frozenset({'大吉', '吉', '半吉'})))
    assert loose and any(not all(r.jishu[k] for k in GRIDS) for r in loose)
    assert all(r.grades[k] in {'大吉', '吉', '半吉'} for r in loose for k in GRADE_GRIDS)


def test_female_caution():
    every = enumerate_combos(4, 0)
    kept = enumerate_combos(4, 0, ComboFilter(exclude_female_caution=True))
    assert pairs(kept) <= pairs(every)
    assert all(r.ge.zong not in {21, 23, 28, 33} for r in kept)
    assert all(r.ge.zong in {21, 23, 28, 33} for r in every if (r.f1, r.f2) not in pairs(kept))


def test_group_and_char_lists():
    rows = enumerate_combos(16, 0)
    groups = group_by_first(rows)
    assert [f1 for f1, _ in groups] == sorted({r.f1 for r in rows})
    assert [r for _, rs in groups for r in rs] == rows
    first, second = char_lists(19, 6)
    assert first and second and all(c.stroke == 19 and c.lvl <= 2 and c.nameable for c in first)
    assert all(c.stroke == 6 for c in second)
    x = first[0].char
    again, _ = char_lists(19, 6, 2, frozenset(x))
    assert x not in {c.char for c in again} and len(again) == len(first) - 1
    assert all(c.lvl <= 1 for c in char_lists(19, 6, 1)[0])


def test_cli_combos(capsys):
    cli_main(['陳', '--combos'])
    out = capsys.readouterr().out
    assert '符合 16 組' in out and '第一字' in out and '天格 17' in out
    cli_main(['林', '--combos'])
    out = capsys.readouterr().out
    assert '天格 9 不在吉數內' in out and '14 組' in out
    cli_main(['林', '--combos', '--grids', '人格,地格,外格,總格'])
    assert '符合 14 組' in capsys.readouterr().out
    cli_main(['王', '--combos', '--jishu-grades', '大吉'])
    out = capsys.readouterr().out
    assert '符合 11 組' in out and '人地外總等級限 大吉' in out
    cli_main(['陳', '--combos', '--jishu-grades', '大吉'])   # 天格 17 是「吉」，撇除後仍有組合
    assert '符合 1 組' in capsys.readouterr().out
    cli_main(['陳', '--combos', '--json'])
    data = json.loads(capsys.readouterr().out)
    assert data['count'] == 16 and data['tian'] == {'n': 17, 'lucky': '半吉', 'title': '剛強', 'jishu': True,
                                                    'grade': '吉', 'cdi_grade': '吉'}
    assert data['filter']['jishu_grades'] == list(dayan.GRADES)
    assert data['groups'][0]['rows'][0]['grades'] == {k: dayan.grade(data['groups'][0]['rows'][0]['ge'][k]) for k in GRIDS}
    assert [g['f1'] for g in data['groups']] == sorted(g['f1'] for g in data['groups'])
    cli_main(['陳', '--combo', '19,6', '--json'])
    data = json.loads(capsys.readouterr().out)
    assert data['combo']['f1'] == 19 and data['combo']['cdi_grade'] == '最吉' and data['in_filter'] is True
    assert data['first'] and data['second'] and all(c['stroke'] == 6 for c in data['second'])
    cli_main(['陳', '--combo', '19+6', '--level', '1', '--avoid', data['first'][0]['char']])
    out = capsys.readouterr().out
    assert '19 + 6 畫' in out and '第一字 19 畫' in out and data['first'][0]['char'] not in out.split('第一字')[1]
    with pytest.raises(SystemExit):
        cli_main(['陳', '--combos', '--sancai-grades', '凶'])
    with pytest.raises(SystemExit):
        cli_main(['陳', '--combos', '--grids', 'xx'])
    with pytest.raises(SystemExit):
        cli_main(['陳', '--combos', '--jishu-grades', '最吉'])
    with pytest.raises(SystemExit):
        cli_main(['陳', '--combo', '19'])
