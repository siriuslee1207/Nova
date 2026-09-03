"""AI 顧問：提示組裝與輸出驗證（不呼叫網路）。"""
import pytest

from nova_core import bazi, chars, rating
from nova_core.cli import main as cli_main
from nova_core.generator import Options, lucky_combos
from nova_core.llm import advisor
from nova_core.llm.base import render

pytest.importorskip('lunar_python')


@pytest.fixture(scope='module')
def req():
    fate = bazi.compute(2026, 9, 3, 10, 30)
    combos = lucky_combos(16, 0, Options(exclude_female_caution=True))
    return advisor.build_recommend('陳', 16, 0, 'girl', fate, combos, chars.by_stroke(2), n=8, preferences='喜歡自然意象')


def test_render_template_and_num():
    assert render('system').startswith('你是「Nova 取名助手」')
    assert advisor.num(90.0) == '90' and advisor.num(86.8) == '86.8' and advisor.num(17) == '17'


def test_build_recommend_prompt(req):
    assert '## 合格筆畫組合' in req.user and '## 候選字池' in req.user and '喜歡自然意象' in req.user
    assert '姓氏：陳（姓名學筆畫 16）' in req.user and '性別：女' in req.user
    assert '用神 木、喜神 土、忌神 火、仇神 木；生肖 馬' in req.user
    assert len(req.top_combos) <= advisor.MAX_COMBOS
    assert all(len(v) <= advisor.MAX_PER_STROKE for v in req.allowed.values())
    assert req.combo_set == {(c.f1, c.f2) for c in req.top_combos}


def test_validate_picks(req):
    (f1, f2) = next(iter(req.combo_set))
    good_first = sorted(req.allowed[f1])[0]
    good_second = sorted(req.allowed[f2])[0]
    other_stroke = next(s for s in req.allowed if s != f1) if len(req.allowed) > 1 else f1
    picks = [
        {'first': good_first, 'second': good_second, 'reason': 'ok'},
        {'first': good_first, 'second': good_second, 'reason': 'dup'},
        {'first': '龘', 'second': good_second, 'reason': 'not in dict'},
        {'first': good_first, 'second': '的', 'reason': 'excluded char'},
    ]
    ok, rejected = advisor.validate_picks(picks, req)
    assert [(c1.char, c2.char) for c1, c2, _ in ok] == [(good_first, good_second)]
    assert [r['why'] for r in rejected] == ['重複', '字典查無此字', '不在候選字池']
    # 字在池內但筆畫組合不合格
    bad = [{'first': good_first, 'second': sorted(req.allowed[other_stroke])[0], 'reason': ''}]
    ok2, rej2 = advisor.validate_picks(bad, req)
    assert not ok2 or (f1, other_stroke) in req.combo_set
    if rej2:
        assert rej2[0]['why'] in ('筆畫組合不合格', '不在候選字池')


def test_build_explain_prompt():
    fate = bazi.compute(2026, 9, 3, 10, 30)
    c1, c2 = chars.lookup('冠'), chars.lookup('宇')
    system, user = advisor.build_explain('陳', c1, c2, rating.rate_name(16, 0, c1, c2, fate), fate)
    assert '陳冠宇（guan4 yu3）' in user and '總分 86.8（上吉）' in user
    assert '天格17（剛強・半吉）' in user and '三才：金土土 大吉' in user
    assert '丙午 丙申 庚辰 辛巳；日主 庚金（弱）' in user


def test_cli_ai_dump(capsys):
    cli_main(['陳', '--born', '2026-09-03T10:30', '--gender', 'girl', '--ai', 'recommend', '--ai-dump'])
    out = capsys.readouterr().out
    assert '--- system ---' in out and '## 候選字池' in out
    cli_main(['陳', '--born', '2026-09-03', '--explain', '冠宇', '--ai', 'explain', '--ai-dump'])
    out = capsys.readouterr().out
    assert '陳冠宇（guan4 yu3）' in out and '時辰不詳' in out
