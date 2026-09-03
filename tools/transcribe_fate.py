"""Transcribe fate's Go constant tables into data/tables/*.json (single source of truth).

Reads the reference copies under ref/fate (MIT, github.com/babyname/fate), parses the Go
literals with regexes, converts simplified text to Taiwan traditional with OpenCC s2twp,
applies Nova's documented fixes, and asserts completeness.

Run: .venv/Scripts/python tools/transcribe_fate.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REF = ROOT / 'ref' / 'fate' / 'internal'
OUT = ROOT / 'data' / 'tables'

try:
    from opencc import OpenCC
except ImportError:  # pragma: no cover
    sys.exit('need opencc-python-reimplemented in the venv: pip install opencc-python-reimplemented')

_cc = OpenCC('s2twp')
# OpenCC phrase ambiguities seen in fortune text; applied after conversion.
_POSTFIX = {'生髮': '生發', '髮達': '發達', '髮展': '發展', '兇': '凶'}  # 吉凶 用 凶，非 兇


def tw(text: str) -> str:
    out = _cc.convert(text)
    for a, b in _POSTFIX.items():
        out = out.replace(a, b)
    return out


def read(rel: str) -> str:
    return (REF / rel).read_text(encoding='utf-8-sig')


def parse_go_string_map(src: str, var_name: str) -> dict[str, str]:
    """Parse a Go `var NAME = map[string]string{ "k": "v", ... }` literal into a dict."""
    m = re.search(r'var\s+' + re.escape(var_name) + r'\s*=\s*map\[string\]string\{(.*?)\n\}', src, re.S)
    if not m:
        raise ValueError(f'{var_name} not found')
    return dict(re.findall(r'"([^"]+)"\s*:\s*"([^"]*)"', m.group(1)))


# ---------------------------------------------------------------- 八十一數理
def build_dayan() -> list[dict]:
    src = read('wuge/dayan.go')
    rows = []
    for line in src.splitlines():
        n = re.search(r'\{Number:\s*(\d+),', line)
        if not n:
            continue
        lucky = re.search(r'Lucky:\s*"([^"]+)"', line).group(1)
        title = re.search(r'SkyNine:\s*"([^"]*)"', line).group(1)
        comment = re.search(r'Comment:\s*"([^"]*)"', line).group(1)
        rows.append({
            'number': int(n.group(1)),
            'lucky': lucky,                         # 吉 | 凶 | 半吉
            'max_luck': 'Max: true' in line,        # 最大好運數
            'female_caution': 'Sex: true' in line,  # 女性不宜
            'title': tw(title),
            'comment': tw(comment),
        })
    assert [r['number'] for r in rows] == list(range(1, 82)), 'dayan must be 1..81'
    assert {r['lucky'] for r in rows} == {'吉', '凶', '半吉'}
    return rows


# ---------------------------------------------------------------- 三才
# Nova's 7-level scale. fate's luckyPoint lacked 中吉 (and the typo 凶多吉少), which made
# GetLuckyPoint return -1 and filtered those 三才 out forever. Fixed here.
SANCAI_LEVELS = {'大凶': 1, '凶': 2, '凶多於吉': 3, '吉凶參半': 4, '中吉': 5, '吉多於凶': 5, '吉': 6, '大吉': 7}
# fate 判語（簡體，含筆誤 凶多吉少）→ Nova 判語；不經 OpenCC（它會把 凶 轉成 兇）
_VERDICT_MAP = {'大凶': '大凶', '凶': '凶', '凶多于吉': '凶多於吉', '凶多吉少': '凶多於吉',
                '吉凶参半': '吉凶參半', '中吉': '中吉', '吉多于凶': '吉多於凶', '吉': '吉', '大吉': '大吉'}
# 金金火 is absent from fate's 124-entry table; standard 三才 charts rate it 凶
# (地火克人金，成功運被壓抑). Filled by Nova and marked as such.
_FILL = {'金金火': '凶'}
ELEMENTS = '木火土金水'


def build_sancai() -> dict:
    src = read('wuxing/wu_xing.go')
    raw = parse_go_string_map(src, 'wuXing')
    table = {}
    for k, v in raw.items():
        table[k] = {'verdict': _VERDICT_MAP[v]}
    for k, v in _FILL.items():
        assert k not in table, f'{k} unexpectedly present; remove from _FILL'
        table[k] = {'verdict': v, 'source': 'nova-fill'}
    for a in ELEMENTS:
        for b in ELEMENTS:
            for c in ELEMENTS:
                key = a + b + c
                assert key in table, f'missing 三才 {key}'
                table[key]['level'] = SANCAI_LEVELS[table[key]['verdict']]
    assert len(table) == 125
    return {'levels': SANCAI_LEVELS, 'combos': table}


def build_sancai_text() -> dict:
    src = read('analysis/sancai_data.go')
    out = {}
    for name, key in (('sanCaiDetailMap', 'detail'), ('jiChuYunMap', 'jichu'),
                      ('chengGongYunMap', 'chenggong'), ('renJiGuanXiMap', 'renji')):
        out[key] = {k: tw(v) for k, v in parse_go_string_map(src, name).items()}
    out['detail_missing'] = [a + b + c for a in ELEMENTS for b in ELEMENTS for c in ELEMENTS
                             if a + b + c not in out['detail']]  # UI falls back to the verdict
    for key in ('jichu', 'chenggong', 'renji'):
        assert len(out[key]) == 25, f'{key} has {len(out[key])} entries'
    return out


# ---------------------------------------------------------------- 八字 / 喜用神 (from chronosfate/*.go)
def build_bazi_tables() -> dict:
    tiangan_wuxing = {'甲': '木', '乙': '木', '丙': '火', '丁': '火', '戊': '土', '己': '土',
                      '庚': '金', '辛': '金', '壬': '水', '癸': '水'}
    dizhi_wuxing = {'子': '水', '丑': '土', '寅': '木', '卯': '木', '辰': '土', '巳': '火',
                    '午': '火', '未': '土', '申': '金', '酉': '金', '戌': '土', '亥': '水'}
    hidden_stems = {  # 藏干加權 (chronosfate/wuxing_data.go)
        '子': [['癸', 1.0]],
        '丑': [['己', 0.6], ['癸', 0.2], ['辛', 0.2]],
        '寅': [['甲', 0.6], ['丙', 0.3], ['戊', 0.1]],
        '卯': [['乙', 1.0]],
        '辰': [['戊', 0.6], ['乙', 0.2], ['癸', 0.2]],
        '巳': [['丙', 0.6], ['庚', 0.3], ['戊', 0.1]],
        '午': [['丁', 0.7], ['己', 0.3]],
        '未': [['己', 0.6], ['丁', 0.2], ['乙', 0.2]],
        '申': [['庚', 0.6], ['壬', 0.3], ['戊', 0.1]],
        '酉': [['辛', 1.0]],
        '戌': [['戊', 0.6], ['辛', 0.2], ['丁', 0.2]],
        '亥': [['壬', 0.7], ['甲', 0.3]],
    }
    src = read('chronosfate/wuxing_data.go')
    m = re.search(r'var tianGanShiShenMap = map\[string\]map\[string\]string\{(.*?)\n\}', src, re.S)
    shishen = {}
    for line in m.group(1).strip().splitlines():
        head = re.match(r'\s*"(.)":\s*\{(.*)\},?', line)
        shishen[head.group(1)] = {k: tw(v) for k, v in re.findall(r'"(.)":\s*"([^"]+)"', head.group(2))}
    assert len(shishen) == 10 and all(len(v) == 10 for v in shishen.values())
    sheng = {'木': '火', '火': '土', '土': '金', '金': '水', '水': '木'}   # 我生
    ke = {'木': '土', '火': '金', '土': '水', '金': '木', '水': '火'}      # 我克
    sheng_wo = {v: k for k, v in sheng.items()}                            # 生我
    ke_wo = {v: k for k, v in ke.items()}                                  # 克我
    # 格局 → 用/喜/忌/仇 as relations to 日主 (chronosfate/xiyong_geju.go)
    geju_rules = {
        '正官格': {'yong': 'self', 'xi': 'sheng_wo', 'ji': 'ke_wo', 'chou': 'wo_ke'},
        '七殺格': {'yong': 'ke_wo', 'xi': 'self', 'ji': 'sheng_wo', 'chou': 'wo_sheng'},
        '正財格': {'yong': 'wo_sheng', 'xi': 'self', 'ji': 'ke_wo', 'chou': 'sheng_wo'},
        '偏財格': {'yong': 'wo_sheng', 'xi': 'self', 'ji': 'ke_wo', 'chou': 'sheng_wo'},
        '正印格': {'yong': 'sheng_wo', 'xi': 'self', 'ji': 'wo_ke', 'chou': 'wo_sheng'},
        '偏印格': {'yong': 'sheng_wo', 'xi': 'self', 'ji': 'wo_ke', 'chou': 'wo_sheng'},
        '食神格': {'yong': 'wo_sheng', 'xi': 'sheng_wo', 'ji': 'ke_wo', 'chou': 'self'},
        '傷官格': {'yong': 'wo_ke', 'xi': 'sheng_wo', 'ji': 'self', 'chou': 'wo_sheng'},
    }
    shishen_to_geju = {'正官': '正官格', '七殺': '七殺格', '偏官': '七殺格', '正財': '正財格',
                       '偏財': '偏財格', '正印': '正印格', '偏印': '偏印格', '食神': '食神格', '傷官': '傷官格'}
    yangren = {'甲': '卯', '乙': '寅', '丙': '午', '丁': '巳', '戊': '午', '己': '巳',
               '庚': '酉', '辛': '申', '壬': '子', '癸': '亥'}
    tiaohou = {'甲': '丙', '乙': '丙', '丙': '壬', '丁': '壬', '戊': '甲', '己': '甲',
               '庚': '丁', '辛': '丁', '壬': '戊', '癸': '戊'}
    zodiac_wuxing = {'鼠': '水', '牛': '土', '虎': '木', '兔': '木', '龍': '土', '蛇': '火',
                     '馬': '火', '羊': '土', '猴': '金', '雞': '金', '狗': '土', '豬': '水'}
    return {
        'tiangan_wuxing': tiangan_wuxing, 'dizhi_wuxing': dizhi_wuxing, 'hidden_stems': hidden_stems,
        'shishen': shishen, 'sheng': sheng, 'ke': ke, 'sheng_wo': sheng_wo, 'ke_wo': ke_wo,
        'geju_rules': geju_rules, 'shishen_to_geju': shishen_to_geju, 'yangren': yangren,
        'tiaohou': tiaohou, 'zodiac_wuxing': zodiac_wuxing,
    }


def dump(name: str, obj) -> None:
    path = OUT / name
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print(f'wrote {path.relative_to(ROOT)} ({path.stat().st_size} bytes)')


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    dump('dayan81.json', build_dayan())
    dump('sancai125.json', build_sancai())
    dump('sancai_text.json', build_sancai_text())
    dump('bazi_tables.json', build_bazi_tables())


if __name__ == '__main__':
    main()
