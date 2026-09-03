"""五格 / 數理 / 三才 / 音韻 基礎行為（手算案例）。"""
import pytest

from nova_core import dayan, sancai, wuge, yinyun


def test_wuge_single_surname_two_char_name():
    # 陳(16) 冠(9) 宇(6)
    g = wuge.calc_wuge(16, 0, 9, 6)
    assert (g.tian, g.ren, g.di, g.wai, g.zong) == (17, 25, 15, 7, 31)


def test_wuge_compound_surname():
    # 歐陽(15,17) 冠(9) 宇(6)：天格 32、人格 17+9=26、地格 15、外格 15+6=21、總格 47
    g = wuge.calc_wuge(15, 17, 9, 6)
    assert (g.tian, g.ren, g.di, g.wai, g.zong) == (32, 26, 15, 21, 47)


def test_wuge_single_char_given_name():
    # 王(4) 力(2)：地格 2+1、外格 1+1
    g = wuge.calc_wuge(4, 0, 2, 0)
    assert (g.tian, g.ren, g.di, g.wai, g.zong) == (5, 6, 3, 2, 6)


def test_wuge_zong_wraps_to_1_81():
    g = wuge.calc_wuge(30, 30, 30, 30)  # 120 → 39
    assert g.zong == 39
    assert g.tian == 60  # 其餘四格不循環


def test_element_and_yinyang():
    assert [wuge.element_of(n) for n in range(1, 11)] == list('木木火火土土金金水水')
    assert wuge.yinyang_of(17) == '陽' and wuge.yinyang_of(16) == '陰'


def test_dayan_table_shape_and_flags():
    assert dayan.find(1).lucky == '吉'
    assert dayan.find(81).lucky == '吉'
    assert dayan.find(82).number == 1  # 循環
    assert dayan.find(41).max_luck is True
    assert {n for n in range(1, 82) if dayan.find(n).max_luck} == {41}  # fate dayan.go 僅 41 標 Max
    assert {n for n in range(1, 82) if dayan.find(n).female_caution} == {21, 23, 28, 33}
    assert {n for n in range(1, 82) if dayan.find(n).lucky == '半吉'} == {8, 17, 18, 25, 30, 36, 38, 39, 49, 50, 51, 55, 58, 71, 72, 73, 77}
    assert dayan.find(21).title == '明月中天'
    with pytest.raises(ValueError):
        dayan.find(0)


def test_dayan_is_lucky_default_accepts_half():
    assert dayan.is_lucky(dayan.find(8))          # 半吉
    assert not dayan.is_lucky(dayan.find(2))      # 凶
    assert not dayan.is_lucky(dayan.find(8), frozenset({'吉'}))


def test_sancai_complete_and_fixed():
    combos = sancai.tables.sancai()['combos']
    assert len(combos) == 125
    assert sancai.key_of(17, 25, 15) == '金土土'
    assert sancai.verdict('金土土') == '大吉' and sancai.level('金土土') == 7
    assert sancai.verdict('木木金') == '凶多於吉' and sancai.level('木木金') == 3   # fate 筆誤 凶多吉少
    assert sancai.verdict('水水水') == '中吉' and sancai.level('水水水') == 5       # fate 缺級 → -1
    assert sancai.verdict('金金火') == '凶' and sancai.level('金金火') == 2          # fate 缺項
    assert sancai.passes('水水水', 'moderate') and not sancai.passes('水水水', 'strict')
    assert sancai.passes('火金土', 'relaxed') and not sancai.passes('火金土', 'moderate')  # 吉凶參半=4


def test_sancai_text_traditional():
    assert '成功順調' in sancai.detail('木木木')
    assert sancai.jichu('木', '木').startswith('基礎堅實')
    assert sancai.chenggong('木', '木') and sancai.renji('木', '土')


@pytest.mark.parametrize('src,expected', [
    ('hào', 'hao4'), ('chén', 'chen2'), ('yǔ', 'yu3'), ('guān', 'guan1'), ('lǜ', 'lü4'),
    ('ma', 'ma'), ('hao4', 'hao4'), ('ēr', 'er1'), ('ǹg', 'ng4'),
])
def test_to_numbered(src, expected):
    assert yinyun.to_numbered(src) == expected


def test_tone_shengmu_yunmu():
    assert yinyun.tone('hao4') == 4 and yinyun.tone('ma') == 0
    assert yinyun.shengmu('zhang1') == 'zh' and yinyun.shengmu('an1') == ''
    assert yinyun.yunmu('zhang1') == 'ang' and yinyun.yunmu('an1') == 'an'
    assert yinyun.yunmu('hao4') == yinyun.yunmu('hao1')  # 韻母比較不含聲調
    assert yinyun.shengmu('yu3') == 'y' and yinyun.yunmu('yu3') == 'u'
