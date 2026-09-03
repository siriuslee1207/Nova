"""ETL: fate character.json + Unihan → data/gen/chars.json, data/gen/chars.gen.js, data/gen/etl_report.md.

Policies (see docs/spike-notes.md):
- Universe = Big5 常用區 (level 1) + 次常用區 (level 2), enumerated via Python's big5 codec.
  Pure simplified forms are therefore excluded by construction; same-form characters (台 云 于) stay.
- 姓名學筆畫 = Unihan kRSUnicode (康熙 radical strokes + residual, negative residual allowed)
  → data/tables/stroke_overrides.json → fallback fate kangxi_stroke. fate science_stroke is ignored.
- Pinyin: Taiwan reading first (kMandarin second value when present), then fate readings; numbered tones.
- 五行: fate wu_xing; unihan-only characters get radical→element, else 數理五行 by stroke digit.
- Meaning: fate text → OpenCC s2twp → short gloss (本義 extraction / first clause); else Unihan kDefinition.
- simp2trad: for pure simplified characters (Unihan kTraditionalVariant present, not in universe),
  OpenCC s2tw single-char result when it lands in the universe.

Run: .venv/Scripts/python tools/build_chars.py
"""
from __future__ import annotations

import io
import json
import re
import sys
import zipfile
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from nova_core.yinyun import to_numbered  # noqa: E402

RAW = ROOT / 'data' / 'raw'
GEN = ROOT / 'data' / 'gen'
TABLES = ROOT / 'data' / 'tables'

try:
    from opencc import OpenCC
except ImportError:  # pragma: no cover
    sys.exit('need opencc-python-reimplemented in the venv')

_s2twp = OpenCC('s2twp')
_s2tw = OpenCC('s2tw')

# 214 康熙部首 (index = radical number - 1)
KANGXI_RADICALS = (
    '一丨丶丿乙亅'
    '二亠人儿入八冂冖冫几凵刀力勹匕匚匸十卜卩厂厶又'
    '口囗土士夂夊夕大女子宀寸小尢尸屮山巛工己巾干幺广廴廾弋弓彐彡彳'
    '心戈戶手支攴文斗斤方无日曰月木欠止歹殳毋比毛氏气水火爪父爻爿片牙牛犬'
    '玄玉瓜瓦甘生用田疋疒癶白皮皿目矛矢石示禸禾穴立'
    '竹米糸缶网羊羽老而耒耳聿肉臣自至臼舌舛舟艮色艸虍虫血行衣襾'
    '見角言谷豆豕豸貝赤走足身車辛辰辵邑酉釆里'
    '金長門阜隶隹雨靑非'
    '面革韋韭音頁風飛食首香'
    '馬骨高髟鬥鬯鬲鬼'
    '魚鳥鹵鹿麥麻'
    '黃黍黑黹'
    '黽鼎鼓鼠'
    '鼻齊'
    '齒'
    '龍龜'
    '龠'
)
assert len(KANGXI_RADICALS) == 214
_RADICAL_STROKE_RANGES = [(1, 6, 1), (7, 29, 2), (30, 60, 3), (61, 94, 4), (95, 117, 5), (118, 146, 6),
                          (147, 166, 7), (167, 175, 8), (176, 186, 9), (187, 194, 10), (195, 200, 11),
                          (201, 204, 12), (205, 208, 13), (209, 210, 14), (211, 211, 15), (212, 213, 16),
                          (214, 214, 17)]
RADICAL_STROKES = {r: s for a, b, s in _RADICAL_STROKE_RANGES for r in range(a, b + 1)}

# radical → 五行 for characters fate lacks (conventional, unambiguous radicals only)
RADICAL_WUXING = {'木': '木', '艸': '木', '竹': '木', '禾': '木',
                  '火': '火', '日': '火',
                  '土': '土', '山': '土', '石': '土', '田': '土', '阜': '土',
                  '金': '金', '刀': '金',
                  '水': '水', '雨': '水', '冫': '水'}
DIGIT_WUXING = '水木木火火土土金金水'  # 數理五行 by stroke % 10

# 等級：1 常見取名用字（name_common.json）、2 Big5 常用區、3 Big5 次常用區（對應 fate common_level 語意）
MEANING_MAX = {1: 40, 2: 40, 3: 16}   # Chinese gloss length by level
DEF_MAX = {1: 60, 2: 60, 3: 30}       # English (Unihan kDefinition) length by level


def load_charset(name: str) -> set[str]:
    """Load a data/tables/*.json whose non-_comment values are strings of characters; return their union."""
    d = json.load(open(TABLES / name, encoding='utf-8'))
    return {ch for k, v in d.items() if k != '_comment' for ch in v if not ch.isspace()}


# ------------------------------------------------------------------ inputs
def big5_universe() -> dict[str, int]:
    levels = {}
    for hi in range(0xA4, 0xFA):
        for lo in list(range(0x40, 0x7F)) + list(range(0xA1, 0xFF)):
            code = hi << 8 | lo
            lvl = 1 if 0xA440 <= code <= 0xC67E else 2 if 0xC940 <= code <= 0xF9D5 else None
            if lvl is None:
                continue
            try:
                ch = bytes([hi, lo]).decode('big5')
            except UnicodeDecodeError:
                continue
            if len(ch) == 1 and ('一' <= ch <= '鿿' or '㐀' <= ch <= '䶿'):
                levels[ch] = lvl
    return levels


def load_unihan() -> dict[str, dict]:
    fields = {'kRSUnicode', 'kTotalStrokes', 'kMandarin', 'kDefinition', 'kTraditionalVariant', 'kSimplifiedVariant'}
    uni: dict[str, dict] = defaultdict(dict)
    with zipfile.ZipFile(RAW / 'Unihan.zip') as z:
        for name in ('Unihan_IRGSources.txt', 'Unihan_Readings.txt', 'Unihan_Variants.txt'):
            with z.open(name) as f:
                for line in io.TextIOWrapper(f, encoding='utf-8'):
                    if line.startswith('#') or not line.strip():
                        continue
                    cp, fld, val = line.rstrip('\n').split('\t', 2)
                    if fld in fields:
                        uni[chr(int(cp[2:], 16))][fld] = val
    return uni


def load_fate() -> dict[str, dict]:
    with open(RAW / 'character.json', encoding='utf-8') as f:
        return {r['char']: r for r in json.load(f)}


# ------------------------------------------------------------------ per-field rules
def unihan_stroke(u: dict) -> tuple[int | None, int | None]:
    """(radical number, 康熙 total) from kRSUnicode's first value; None if absent."""
    rs = u.get('kRSUnicode')
    if not rs:
        return None, None
    rad, res = rs.split()[0].split('.')
    rad = int(rad.rstrip("'"))
    return rad, RADICAL_STROKES[rad] + int(res)


def choose_stroke(ch: str, u: dict, fr: dict | None, overrides: dict) -> tuple[int | None, str]:
    if ch in overrides['digits']:
        return overrides['digits'][ch], 'digit-rule'
    if ch in overrides['kangxi']:
        return overrides['kangxi'][ch], 'kangxi-override'
    _, uni = unihan_stroke(u)
    if uni:
        return uni, 'unihan'
    if fr and fr.get('kangxi_stroke'):
        return fr['kangxi_stroke'], 'fate'
    return None, 'none'


def choose_pinyin(u: dict, fr: dict | None) -> list[str]:
    out: list[str] = []
    km = (u.get('kMandarin') or '').split()
    if len(km) == 2:            # CN TW → Taiwan reading first
        out.append(km[1])
    for p in (fr or {}).get('pinyin') or []:
        out.append(p)
    for p in km:
        out.append(p)
    seen, uniq = set(), []
    for p in out:
        n = to_numbered(p.strip().lower())
        if n and n not in seen:
            seen.add(n)
            uniq.append(n)
    return uniq[:3]


def choose_wuxing(fr: dict | None, radical: str, stroke: int | None) -> tuple[str, str]:
    if fr and fr.get('wu_xing'):
        return fr['wu_xing'], 'fate'
    if radical in RADICAL_WUXING:
        return RADICAL_WUXING[radical], 'radical-rule'
    if stroke:
        return DIGIT_WUXING[stroke % 10], 'digit-rule'
    return '', 'none'


# 新華字典文字有三種格式：(a) "(會意。從X。本義Y)；同本義；…"  (b) "字pīnyīn 1.釋義。 2.釋義"  (c) 英文 kDefinition
_BENYI = re.compile(r'本義[:：]?\s*([^)）；;。]{1,40})')
_FMT_B = re.compile(r'^\S[a-zA-Züāáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜńňǹ]+\s*1\.\s*(.+?)(?:\s*2\.|[。；;]|$)')
_CLAUSE_SPLIT = re.compile(r'[；;。]')
_BAD_CLAUSE = re.compile(r'--|《|》|\?|？|^從|聲$|^同本義|^本義|^(會意|形聲|象形|指事|轉注|假借)|^\d')
_UNHELPFUL = {'未明', '未詳', '不詳'}


def _clean(s: str) -> str:
    return s.strip().strip('()（）,，、:：;；。 "”“').strip()


def _has_cjk(s: str) -> bool:
    return any('一' <= c <= '鿿' for c in s[:20])


def chinese_gloss(text: str, limit: int) -> str:
    t = _s2twp.convert(text).replace('”', '').replace('“', '').replace('"', '')
    m = _FMT_B.match(t)
    if m:
        g = _clean(m.group(1))
        return g[:limit] if g else ''
    benyi = ''
    m = _BENYI.search(t)
    if m:
        benyi = _clean(m.group(1))
        if benyi in _UNHELPFUL:
            benyi = ''
    if benyi and len(benyi) <= 10:                # 短本義多為可用釋義（冠=帽子、宇=屋簷）
        return benyi
    body = _strip_leading_paren(t)               # drop leading (nested) etymology parenthetical
    for sense in re.split(r'[；;]', body):       # 新華格式：釋義；釋義。例句。--出處
        if '《' in sense or '》' in sense:       # 引文/例句
            continue
        sense = sense.split('--')[0]
        for clause in sense.split('。'):
            g = _clean(clause)
            if (len(g) >= 2 and not _BAD_CLAUSE.search(g) and not re.search(r'[A-Za-z]', g)
                    and g not in _UNHELPFUL):
                return g[:limit]
    return benyi[:limit]                          # 長本義最後才用（常為字源義）


def _strip_leading_paren(t: str) -> str:
    if not t or t[0] not in '(（':
        return t
    depth = 0
    for i, ch in enumerate(t):
        if ch in '(（':
            depth += 1
        elif ch in ')）':
            depth -= 1
            if depth == 0:
                return t[i + 1:]
    return ''  # unbalanced: the whole text is etymology


def gloss(texts: list[str], u: dict, lvl: int) -> str:
    """texts: candidate meaning strings (own record first, then its simplified twin); Chinese preferred."""
    for text in texts:
        if text and _has_cjk(text):
            g = chinese_gloss(text, MEANING_MAX[lvl])
            if g:
                return g
    for text in texts:
        if text and not _has_cjk(text):
            return text.split(';')[0].strip()[:DEF_MAX[lvl]]
    return (u.get('kDefinition') or '').split(';')[0].strip()[:DEF_MAX[lvl]]


# ------------------------------------------------------------------ build
def main() -> None:
    overrides = json.load(open(TABLES / 'stroke_overrides.json', encoding='utf-8'))
    meaning_overrides = json.load(open(TABLES / 'meaning_overrides.json', encoding='utf-8'))
    meaning_overrides.pop('_comment', None)
    name_common = load_charset('name_common.json')
    name_exclude = load_charset('name_exclude.json')
    levels = big5_universe()
    uni = load_unihan()
    fate = load_fate()
    universe = sorted(levels, key=lambda c: (levels[c], c))
    # 繁體記錄常只有英文釋義，而其簡體記錄有中文：陈.simplified_of_char == 陳 → twin[陳] = 陈 record
    twin = {r['simplified_of_char']: r for r in fate.values()
            if r.get('simplified_of_char') and r['simplified_of_char'] != r['char'] and r.get('meaning')}

    rows = []
    stats = Counter()
    stroke_dis = []      # (char, unihan, fate, chosen)
    missing_fate = []
    wx_rule = []
    no_stroke = []
    for ch in universe:
        lvl = 1 if ch in name_common else levels[ch] + 1
        u = uni.get(ch, {})
        fr = fate.get(ch)
        stats[f'level{lvl}'] += 1
        if fr is None:
            missing_fate.append(ch)
            stats['from_unihan_only'] += 1
        stroke, ssrc = choose_stroke(ch, u, fr, overrides)
        stats[f'stroke_src:{ssrc}'] += 1
        if stroke is None or not 1 <= stroke <= 30:
            no_stroke.append((ch, stroke))
            continue
        _, uni_total = unihan_stroke(u)
        if fr and fr.get('kangxi_stroke') and uni_total and fr['kangxi_stroke'] != uni_total:
            stroke_dis.append((ch, uni_total, fr['kangxi_stroke'], stroke))
        rad_no, _ = unihan_stroke(u)
        radical = (fr or {}).get('radical') or (KANGXI_RADICALS[rad_no - 1] if rad_no else '')
        wx, wsrc = choose_wuxing(fr, radical, stroke)
        if wsrc != 'fate':
            wx_rule.append((ch, wx, wsrc))
        py = choose_pinyin(u, fr)
        if not py or not wx:
            stats['skipped_no_pinyin_or_wx'] += 1
            continue
        nameable = 1 if (fr is None or fr.get('nameable')) and ch not in name_exclude else 0
        meaning = meaning_overrides.get(ch) or gloss(
            [(fr or {}).get('meaning') or '', (twin.get(ch) or {}).get('meaning') or ''], u, lvl)
        rows.append([ch, '/'.join(py), stroke, wx, lvl, nameable, meaning, radical])
        stats['rows'] += 1
        stats[f'nameable_l{lvl}'] += nameable

    # 姓氏簡→繁：chars with a traditional variant that are not themselves Big5 常用 (level 1) characters.
    # Level-1 chars (于 干 后 云 台) are legitimate traditional characters and stay; level-2 variants (庄 万 体) convert.
    simp2trad = {}
    inset = set(levels)
    for ch, u in uni.items():
        tv = u.get('kTraditionalVariant')
        if not tv or levels.get(ch) == 1 or not ('一' <= ch <= '鿿'):
            continue
        cand = _s2tw.convert(ch)
        if len(cand) != 1 or cand == ch or cand not in inset:
            variants = [chr(int(v[2:].split('<')[0], 16)) for v in tv.split()]
            cand = next((v for v in variants if v in inset and v != ch), None)
        if cand:
            simp2trad[ch] = cand

    GEN.mkdir(parents=True, exist_ok=True)
    payload = {
        'version': 1,
        'generated': date.today().isoformat(),
        'fields': ['char', 'py', 'stroke', 'wx', 'lvl', 'nameable', 'meaning', 'radical'],
        'rows': rows,
        'simp2trad': simp2trad,
    }
    compact = json.dumps(payload, ensure_ascii=False, separators=(',', ':'))
    (GEN / 'chars.json').write_text(compact, encoding='utf-8')
    (GEN / 'chars.gen.js').write_text('globalThis.NOVA_CHARS = ' + compact + ';\n', encoding='utf-8')

    size = len(compact.encode('utf-8'))
    report = [
        f'# ETL report ({date.today().isoformat()})', '',
        f'- rows: {stats["rows"]} (level1 常見取名 {stats["level1"]}, level2 常用 {stats["level2"]}, level3 次常用 {stats["level3"]}); '
        f'nameable l1 {stats["nameable_l1"]}, l2 {stats["nameable_l2"]}, l3 {stats["nameable_l3"]}',
        f'- name_common chars not in Big5 universe (ignored): {"".join(sorted(name_common - set(levels)))}',
        f'- from Unihan only (missing in fate): {stats["from_unihan_only"]}',
        f'- stroke sources: ' + ', '.join(f'{k.split(":")[1]}={v}' for k, v in sorted(stats.items()) if k.startswith('stroke_src:')),
        f'- skipped (no pinyin/五行): {stats["skipped_no_pinyin_or_wx"]}; no/out-of-range stroke: {len(no_stroke)}',
        f'- simp2trad entries: {len(simp2trad)}',
        f'- chars.json size: {size} bytes ({size / 1024:.0f} KB)', '',
        '## Unihan ≠ fate kangxi_stroke (char, unihan, fate, chosen) — review list', '',
        ' '.join(f'{c}:{u}/{f}→{s}' for c, u, f, s in stroke_dis), '',
        '## 五行 by rule (unihan-only chars)', '',
        ' '.join(f'{c}:{w}({s[0]})' for c, w, s in wx_rule), '',
        '## Missing in fate (filled from Unihan)', '',
        ''.join(missing_fate), '',
        '## Dropped (no stroke)', '',
        ' '.join(f'{c}:{s}' for c, s in no_stroke), '',
    ]
    (GEN / 'etl_report.md').write_text('\n'.join(report), encoding='utf-8')
    print('\n'.join(report[:8]))


if __name__ == '__main__':
    main()
