"""自訂評分權重：解析、正規化、加權總分與產生器（含「三才五格=1、其他=0」這種只看單一維度的用法）。"""
import pytest

from nova_core import bazi, chars, generator, rating

pytest.importorskip('lunar_python')


@pytest.fixture(scope='module')
def fate():
    return bazi.compute(2026, 9, 3, 10, 30, method='balance')


def test_default_weights_unchanged():
    assert rating.DEFAULT_WEIGHTS == (0.20, 0.25, 0.10, 0.30, 0.15)
    assert sum(rating.DEFAULT_WEIGHTS) == 1.0            # 正規化時不會改動任何一位
    assert rating.normalize_weights(None) == rating.DEFAULT_WEIGHTS
    assert rating.is_default_weights(rating.normalize_weights(rating.DEFAULT_WEIGHTS))


@pytest.mark.parametrize('spec,expected', [
    ('', None),
    ('wuge', (0.0, 0.0, 0.0, 1.0, 0.0)),
    ('三才五格=1,其他=0', (0.0, 0.0, 0.0, 1.0, 0.0)),
    ('五格:1、其他:0', (0.0, 0.0, 0.0, 1.0, 0.0)),
    ('0,0,0,1,0', (0.0, 0.0, 0.0, 1.0, 0.0)),
    ('wuge=2', (0.20, 0.25, 0.10, 2.0, 0.15)),           # 沒點到的維持預設
    ('其他=0,音韻=1,文化=1', (1.0, 0.0, 0.0, 0.0, 1.0)),
    ('equal', (1.0, 1.0, 1.0, 1.0, 1.0)),
])
def test_parse_weights(spec, expected):
    assert rating.parse_weights(spec) == expected


@pytest.mark.parametrize('spec', ['文化=一', '長相=1', '1,2,3', 'wuge=inf'])
def test_parse_weights_rejects_nonsense(spec):
    with pytest.raises(ValueError):
        rating.parse_weights(spec)


def test_normalize_weights_scales_and_clamps():
    assert rating.normalize_weights((1, 1, 1, 1, 1)) == (0.2, 0.2, 0.2, 0.2, 0.2)
    assert rating.normalize_weights((3, 0, 0, 7, 0)) == (0.3, 0.0, 0.0, 0.7, 0.0)
    assert rating.normalize_weights((-5, 0, 0, 1, 0)) == (0.0, 0.0, 0.0, 1.0, 0.0)   # 負數當 0
    assert rating.normalize_weights((0, 0, 0, 0, 0)) == rating.DEFAULT_WEIGHTS        # 全 0 退回預設
    assert sum(rating.normalize_weights((1, 2, 3, 4, 5))) == pytest.approx(1.0)


def test_weights_text():
    assert rating.weights_text(rating.DEFAULT_WEIGHTS) == '文化 20%、五行 25%、生肖 10%、五格三才 30%、音韻 15%'
    assert rating.weights_text(rating.normalize_weights(rating.parse_weights('wuge'))) == '五格三才 100%'


def test_total_follows_weights(fate):
    c1, c2 = chars.lookup('冠'), chars.lookup('宇')
    ref = rating.rate_name(16, 0, c1, c2, fate)
    only_wuge = rating.rate_name(16, 0, c1, c2, fate, rating.parse_weights('三才五格=1,其他=0'))
    # 各維分數不受權重影響，只有總分改變
    assert only_wuge.scores == ref.scores
    assert only_wuge.total == rating.round1(ref.wuge)
    assert only_wuge.weights == (0.0, 0.0, 0.0, 1.0, 0.0)
    equal = rating.rate_name(16, 0, c1, c2, fate, (1, 1, 1, 1, 1))
    assert equal.total == rating.round1(sum(ref.scores) / 5)
    assert equal.grade == rating.grade(equal.total)


def test_generate_ranks_by_custom_weights(fate):
    opt = generator.Options(top_n=10, per_first_char=2, weights=rating.parse_weights('wuge'))
    res = generator.generate(16, 0, fate, opt)
    assert len(res) == 10
    totals = [c.total for c in res]
    assert totals == sorted(totals, reverse=True)
    for c in res:
        # 快速路徑與完整評分一致，且總分就是五格分
        assert c.full_rating(16, 0, fate, opt.weights).total == c.total
        assert c.total == rating.round1(c.combo.wuge_score)


def test_generate_weights_change_the_ranking(fate):
    base = generator.generate(16, 0, fate, generator.Options(top_n=10, per_first_char=2))
    sound = generator.generate(16, 0, fate, generator.Options(top_n=10, per_first_char=2,
                                                              weights=rating.parse_weights('sound')))
    assert [c.name for c in base] != [c.name for c in sound]
