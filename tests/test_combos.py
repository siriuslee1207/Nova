"""筆畫組合選字：36 吉數表、謝達輝三才表、列舉不變量、CLI。"""
import json
from collections import Counter

import pytest

from nova_core import dayan, sancai
from nova_core.cli import main as cli_main
from nova_core.combos import GRIDS, ComboFilter, char_lists, combo_row, enumerate_combos, group_by_first, tian_of, tian_ok
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
    cli_main(['陳', '--combos', '--json'])
    data = json.loads(capsys.readouterr().out)
    assert data['count'] == 16 and data['tian'] == {'n': 17, 'lucky': '半吉', 'title': '剛強', 'jishu': True}
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
        cli_main(['陳', '--combo', '19'])
