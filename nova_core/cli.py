"""命令列：python -m nova_core.cli 陳 --born 2026-09-03T10:30 --gender girl [--top 10] [--json]

亦可對單一名字出報告：python -m nova_core.cli 陳 --explain 冠宇 --born 2026-09-03T10:30
自訂評分權重：python -m nova_core.cli 陳 --weights '三才五格=1,其他=0'
筆畫組合選字：python -m nova_core.cli 陳 --combos；python -m nova_core.cli 陳 --combo 19,6 --level 1
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, replace
from datetime import datetime

from . import bazi as bazi_mod
from . import chars, sancai
from .combos import GRIDS, ComboFilter, char_lists, combo_row, enumerate_combos, group_by_first, tian_of
from .dayan import GRADES as JISHU_GRADES
from .dayan import cdi_grade as jishu_cdi_grade
from .dayan import find as find_dayan
from .dayan import grade as jishu_grade
from .dayan import is_jishu
from .generator import Options, generate
from .rating import DIM_NAMES, DIMS, GE_NAMES, PRESETS, PRESET_NAMES, is_default_weights, normalize_weights, parse_weights, rate_name, weights_text
from .wuge import MAX_STROKE, element_of, yinyang_of


def parse_born(s: str | None) -> tuple[int, int, int, int | None, int]:
    if not s:
        raise ValueError
    if 'T' in s or ' ' in s:
        dt = datetime.fromisoformat(s.replace(' ', 'T'))
        return dt.year, dt.month, dt.day, dt.hour, dt.minute
    dt = datetime.fromisoformat(s)
    return dt.year, dt.month, dt.day, None, 0


def surname_strokes(surname: str) -> tuple[int, int, list[str]]:
    notes = []
    strokes = []
    for ch in surname:
        ci = chars.lookup(ch)
        if ci is None:
            raise SystemExit(f'查無姓氏用字「{ch}」的筆畫；請用 --surname-strokes 手動指定（如 16 或 15,17）')
        strokes.append(ci.stroke)
        notes.append(f'{ch}={ci.stroke}畫')
    if len(strokes) == 1:
        return strokes[0], 0, notes
    if len(strokes) == 2:
        return strokes[0], strokes[1], notes
    raise SystemExit('姓氏須為 1–2 字')


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog='nova', description='Nova 取名（繁體、五格/三才/八字喜用/生肖/音韻）')
    p.add_argument('surname', help='姓氏（1–2 字，簡體自動轉繁）')
    p.add_argument('--born', help='出生時間 ISO 格式，如 2026-09-03T10:30；只給日期表示時辰不詳')
    p.add_argument('--gender', choices=['boy', 'girl'], default='boy')
    p.add_argument('--method', choices=list(bazi_mod.METHODS), default='balance', help='喜用神方法')
    p.add_argument('--strictness', choices=['strict', 'moderate', 'relaxed'], default='moderate')
    p.add_argument('--level', type=int, choices=[1, 2, 3], default=2,
                   help='字集：1 僅常見取名用字、2 含常用字（預設）、3 含次常用字')
    p.add_argument('--top', type=int, default=10)
    p.add_argument('--per-first', type=int, default=2, help='同一第一字最多出現次數（0 不限制，預設 2）')
    p.add_argument('--avoid', default='', help='排除字，如 死病')
    p.add_argument('--require', default='', help='名字至少含其一的字')
    p.add_argument('--first', help='指定第一字（輩字）')
    p.add_argument('--second', help='指定第二字')
    p.add_argument('--surname-strokes', help='手動指定姓氏筆畫，如 16 或 15,17')
    p.add_argument('--female-caution', dest='female_caution', action=argparse.BooleanOptionalAction, default=None,
                   help='排除女性不宜之總格（預設：女生開、男生關）')
    p.add_argument('--weights', default='', metavar='SPEC',
                   help='自訂評分權重（會正規化成總和 1）：預設名稱 '
                        + '／'.join(f'{k}（{v}）' for k, v in PRESET_NAMES.items())
                        + '，或「三才五格=1,其他=0」「wuge=2」（未列到的維持預設），或五個數字「0,0,0,1,0」'
                          '（順序：文化,五行,生肖,五格,音韻）')
    p.add_argument('--explain', metavar='NAME', help='只對此名字（2 字）輸出完整評分報告')
    c = p.add_argument_group('筆畫組合選字（謝達輝三才吉凶表＋36 吉數＋吉數等級；與 --strictness 無關）')
    c.add_argument('--combos', action='store_true', help='列出所有合格的（第一字,第二字）筆畫組合，依第一字筆畫分組')
    c.add_argument('--combo', metavar='F1,F2', help='列出此筆畫組合的兩份字表（配合 --level、--avoid），如 19,6')
    c.add_argument('--sancai-grades', default='最吉,吉', metavar='GRADES',
                   help='三才等級（謝達輝表），可選 ' + ','.join(sancai.CDI_SELECTABLE) + '；預設 最吉,吉')
    c.add_argument('--grids', default=','.join(GRIDS), metavar='GRIDS',
                   help='須為吉數的格，預設五格全部（tian,ren,di,wai,zong 或 天格,人格,地格,外格,總格）；'
                        '天格由姓氏決定，天格非吉數時可去掉 tian')
    c.add_argument('--jishu-grades', default=','.join(JISHU_GRADES), metavar='GRADES',
                   help='吉數等級（人格,地格,外格,總格 四格都要落在其中；天格由姓氏決定不納入），可選 '
                        + ','.join(JISHU_GRADES)
                        + '；預設全收＝不限制。大吉＋吉 即 36 吉數，例如 --jishu-grades 大吉 只留兩表皆吉的數')
    p.add_argument('--json', action='store_true', help='以 JSON 輸出')
    g = p.add_argument_group('AI 顧問')
    g.add_argument('--ai', choices=['recommend', 'explain'],
                   help='recommend：請 AI 從合格字池挑名（由 Nova 評分）；explain：對 --explain 的名字生成解說')
    g.add_argument('--provider', choices=['gemini', 'copilot'], default='gemini')
    g.add_argument('--model', help='模型名稱（預設 gemini-3.5-flash-lite / gpt-5-mini）')
    g.add_argument('--prefs', default='', help='給 AI 的偏好說明')
    g.add_argument('--ai-n', type=int, default=8, help='請 AI 推薦幾個名字')
    g.add_argument('--ai-dump', action='store_true', help='只印出送給 AI 的提示，不呼叫（不需 key）')
    return p


def fate_from_args(args) -> bazi_mod.FateData | None:
    if not args.born:
        return None
    y, m, d, h, mi = parse_born(args.born)
    return bazi_mod.compute(y, m, d, h, mi, method=args.method)


def explain(surname: str, l1: int, l2: int, name: str, fate, as_json: bool, weights=None) -> None:
    if len(name) != 2:
        raise SystemExit('--explain 需為 2 字名')
    c1, c2 = chars.lookup(name[0]), chars.lookup(name[1])
    if not c1 or not c2:
        raise SystemExit(f'字典中查無「{name}」的用字')
    r = rate_name(l1, l2, c1, c2, fate, weights)
    ge = r.ge
    report = {
        'name': surname + name, 'total': r.total, 'grade': r.grade,
        'weights': {DIM_NAMES[k]: v for k, v in zip(DIMS, r.weights)},
        'scores': {'文化': r.wenhua, '五行': r.wuxing, '生肖': r.shengxiao, '五格': r.wuge, '音韻': r.yinyun},
        'chars': [asdict(c1), asdict(c2)],
        'wuge': {GE_NAMES[k]: {'數': n, '數理': find_dayan(n).lucky, '名': find_dayan(n).title,
                               '陰陽五行': yinyang_of(n) + element_of(n), '解': find_dayan(n).comment}
                 for k, n in ge.as_dict().items()} if ge else None,
        'sancai': {'配置': r.sancai_key, '吉凶': sancai.verdict(r.sancai_key), '解': sancai.detail(r.sancai_key),
                   '基礎運': sancai.jichu(element_of(ge.ren), element_of(ge.di)),
                   '成功運': sancai.chenggong(element_of(ge.ren), element_of(ge.tian)),
                   '人際': sancai.renji(element_of(ge.ren), element_of(ge.wai))} if ge else None,
        'bazi': asdict(fate) if fate else None,
        'details': r.details,
    }
    if as_json:
        print(json.dumps(report, ensure_ascii=False, indent=1))
        return
    print(f"{report['name']}  總分 {r.total}（{r.grade}）  文化{r.wenhua} 五行{r.wuxing} 生肖{r.shengxiao} 五格{r.wuge} 音韻{r.yinyun}")
    if not is_default_weights(r.weights):
        print(f"  評分權重 {weights_text(r.weights)}")
    for c in (c1, c2):
        print(f"  {c.char}  {'/'.join(c.py)}  {c.stroke}畫 {c.wx}  {c.meaning}")
    if ge:
        for k, v in report['wuge'].items():
            print(f"  {k} {v['數']}（{v['名']}·{v['數理']}·{v['陰陽五行']}）{v['解']}")
        s = report['sancai']
        print(f"  三才 {s['配置']} {s['吉凶']}：{s['解']}")
        print(f"  基礎運：{s['基礎運']}\n  成功運：{s['成功運']}\n  人際：{s['人際']}")
    if fate:
        print(f"  八字 {' '.join(fate.sizhu)}{'' if fate.hour_known else '（時辰不詳，未計時柱）'}  日主{fate.day_gan}{fate.day_wx}（{fate.qiangruo}）"
              f"  生肖{fate.zodiac}  用{fate.yong} 喜{fate.xi} 忌{fate.ji} 仇{fate.chou}  {fate.geju or ''} {fate.note}")
    for k, lines in r.details.items():
        if lines:
            print(f"  [{k}] " + '；'.join(lines))


def _provider(args):
    from .llm.base import get_provider
    return get_provider(args.provider, args.model)


def ai_explain(args, surname: str, l1: int, l2: int, name: str, fate, weights=None) -> None:
    from .llm.advisor import build_explain
    c1, c2 = chars.lookup(name[0]), chars.lookup(name[1])
    system, user = build_explain(surname, c1, c2, rate_name(l1, l2, c1, c2, fate, weights), fate)
    if args.ai_dump:
        print('--- system ---\n' + system + '\n--- user ---\n' + user)
        return
    print(f'\n[AI 解說・{args.provider}]')
    _provider(args).stream_text(system, user, on_delta=lambda t: print(t, end='', flush=True))
    print()


def ai_recommend(args, surname: str, l1: int, l2: int, fate, opt: Options) -> None:
    from .generator import lucky_combos
    from .llm.advisor import PICKS_SCHEMA, build_recommend, validate_picks
    combos = lucky_combos(l1, l2, opt)
    if not combos:
        raise SystemExit('沒有合格的筆畫組合，請放寬嚴格度')
    req = build_recommend(surname, l1, l2, args.gender, fate, combos, chars.by_stroke(opt.max_level),
                          n=args.ai_n, preferences=args.prefs, weights=opt.weights)
    if args.ai_dump:
        print('--- system ---\n' + req.system + '\n--- user ---\n' + req.user)
        return
    data = _provider(args).generate_json(req.system, req.user, PICKS_SCHEMA)
    ok, rejected = validate_picks(data.get('picks'), req)
    print(f'[AI 推薦・{args.provider}] {len(ok)} 個合格' + (f'，{len(rejected)} 個不合格已略過' if rejected else ''))
    for c1, c2, reason in ok:
        r = rate_name(l1, l2, c1, c2, fate, opt.weights)
        print(f'  {surname}{c1.char}{c2.char}  {r.total:>5}（{r.grade}）  {c1.py[0]} {c2.py[0]}  {c1.wx}{c2.wx}  — {reason}')
    for rj in rejected:
        print(f'  ✗ {rj["first"]}{rj["second"]}：{rj["why"]}')


def _split_list(s: str) -> list[str]:
    return [x for x in re.split(r'[,，、\s]+', (s or '').strip()) if x]


def combo_filter_from_args(args, female: bool) -> ComboFilter:
    grades = _split_list(args.sancai_grades)
    if not grades or any(g not in sancai.CDI_SELECTABLE for g in grades):
        raise SystemExit('--sancai-grades 只能選 ' + ','.join(sancai.CDI_SELECTABLE) + '（逗號分隔）')
    aliases = {v: k for k, v in GE_NAMES.items()}
    grids = [aliases.get(g, g) for g in _split_list(args.grids)]
    if not grids or any(g not in GRIDS for g in grids):
        raise SystemExit('--grids 只能選 ' + ','.join(GRIDS) + '（或 ' + ','.join(GE_NAMES.values()) + '）')
    jgrades = _split_list(args.jishu_grades)
    if not jgrades or any(g not in JISHU_GRADES for g in jgrades):
        raise SystemExit('--jishu-grades 只能選 ' + ','.join(JISHU_GRADES) + '（逗號分隔）')
    return ComboFilter(sancai_grades=frozenset(grades), grids=tuple(k for k in GRIDS if k in grids),
                       jishu_grades=frozenset(jgrades), exclude_female_caution=female)


def _combo_line(r) -> str:
    g = r.ge
    marks = ' '.join(GE_NAMES[k][0] + ('✓' if r.jishu[k] else '✗') + r.grades[k] for k in GRIDS)
    return (f'{r.f1} + {r.f2} 畫  五格 {g.tian}/{g.ren}/{g.di}/{g.wai}/{g.zong}（吉數 {marks}）'
            f'  三才 {r.sancai_key} {r.cdi_grade}（原表 {r.fate_verdict}）  五格分 {r.wuge_score}')


def combos_cmd(args, surname: str, l1: int, l2: int, filt: ComboFilter) -> None:
    rows = enumerate_combos(l1, l2, filt)
    tian = tian_of(l1, l2)
    td = find_dayan(tian)
    tian_info = {'n': tian, 'lucky': td.lucky, 'title': td.title, 'jishu': is_jishu(tian),
                 'grade': jishu_grade(tian), 'cdi_grade': jishu_cdi_grade(tian)}
    filt_out = {'sancai_grades': [g for g in sancai.CDI_SELECTABLE if g in filt.sancai_grades], 'grids': list(filt.grids),
                'jishu_grades': [g for g in JISHU_GRADES if g in filt.jishu_grades],
                'exclude_female_caution': filt.exclude_female_caution}
    head = {'surname': surname, 'l1': l1, 'l2': l2, 'tian': tian_info, 'filter': filt_out}
    if args.combo:
        try:
            parts = [int(x) for x in re.split(r'[,，+＋\s]+', args.combo.strip()) if x]
        except ValueError:
            parts = []
        if len(parts) != 2 or not all(1 <= x <= MAX_STROKE for x in parts):
            raise SystemExit(f'--combo 需為「第一字筆畫,第二字筆畫」（1–{MAX_STROKE}），如 19,6')
        f1, f2 = parts
        row = combo_row(l1, l2, f1, f2)
        inside = any(r.f1 == f1 and r.f2 == f2 for r in rows)
        first, second = char_lists(f1, f2, args.level, frozenset(args.avoid))
        if args.json:
            print(json.dumps({**head, 'combo': row.as_dict(), 'in_filter': inside,
                              'first': [asdict(c) for c in first], 'second': [asdict(c) for c in second]},
                             ensure_ascii=False, indent=1))
            return
        print(_combo_line(row) + ('' if inside else '  （不在目前篩選內）'))
        for label, s, lst in (('第一字', f1, first), ('第二字', f2, second)):
            print(f'{label} {s} 畫（{len(lst)} 字）：')
            for i in range(0, len(lst), 20):
                print('  ' + ' '.join(f'{c.char}[{c.py[0]},{c.wx}]' for c in lst[i:i + 20]))
        return
    if args.json:
        print(json.dumps({**head, 'count': len(rows),
                          'groups': [{'f1': f1, 'rows': [r.as_dict() for r in rs]} for f1, rs in group_by_first(rows)]},
                         ensure_ascii=False, indent=1))
        return
    print(f"姓 {surname} {l1}{'+' + str(l2) if l2 else ''} 畫  天格 {tian}（{td.title}・{td.lucky}）"
          f"{'吉數' if tian_info['jishu'] else '非吉數'}・{tian_info['grade']}")
    if not rows and 'tian' in filt.grids and not tian_info['jishu']:
        rest = tuple(k for k in filt.grids if k != 'tian')
        alt = enumerate_combos(l1, l2, replace(filt, grids=rest))
        print(f'天格 {tian} 不在吉數內；天格由姓氏決定，加 --grids {",".join(rest)} 即可列出其他各格皆吉數的組合（{len(alt)} 組）')
        return
    grades_txt = ','.join(filt_out['sancai_grades'])
    grids_txt = ''.join(GE_NAMES[k][0] for k in filt.grids) + ' 皆吉數' if filt.grids else '不限吉數'
    jg_txt = '' if filt.jishu_grades >= frozenset(JISHU_GRADES) else '；人地外總等級限 ' + ','.join(filt_out['jishu_grades'])
    print(f'符合 {len(rows)} 組（三才 {grades_txt}；{grids_txt}{jg_txt}）')
    if not rows:
        print('  試著加入 平吉、放寬吉數等級或減少須為吉數的格')
        return
    for f1, rs in group_by_first(rows):
        print(f'第一字 {f1:>2} 畫：' + '  '.join(f'{r.f2}({r.sancai_key} {r.cdi_grade} {r.wuge_score})' for r in rs))


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    surname, notes = chars.normalize_surname(args.surname)
    if args.surname_strokes:
        parts = [int(x) for x in args.surname_strokes.split(',')]
        l1, l2 = parts[0], (parts[1] if len(parts) > 1 else 0)
    else:
        l1, l2, snotes = surname_strokes(surname)
        notes += snotes
    fate = fate_from_args(args)
    try:
        weights = parse_weights(args.weights)
    except ValueError as e:
        raise SystemExit(f'--weights {e}（預設名稱：' + '、'.join(PRESETS) + '）')
    if not args.json and notes:
        print('；'.join(notes))
    if args.explain:
        explain(surname, l1, l2, args.explain, fate, args.json, weights)
        if args.ai == 'explain':
            ai_explain(args, surname, l1, l2, args.explain, fate, weights)
        return
    female = args.female_caution if args.female_caution is not None else (args.gender == 'girl')
    if args.combos or args.combo:
        combos_cmd(args, surname, l1, l2, combo_filter_from_args(args, female))
        return
    opt = Options(strictness=args.strictness, exclude_female_caution=female, max_level=args.level,
                  avoid_chars=frozenset(args.avoid), require_chars=frozenset(args.require),
                  fixed_first=args.first, fixed_second=args.second, top_n=args.top, per_first_char=args.per_first,
                  weights=weights)
    if args.ai == 'recommend':
        ai_recommend(args, surname, l1, l2, fate, opt)
        return
    results = generate(l1, l2, fate, opt)
    if args.json:
        out = [{'rank': i + 1, 'name': surname + c.name, 'total': c.total, 'grade': c.grade,
                'scores': dict(zip(('文化', '五行', '生肖', '五格', '音韻'), c.scores)),
                'strokes': [l1, l2, c.combo.f1, c.combo.f2], 'wuge': c.combo.ge.as_dict(),
                'sancai': c.combo.sancai_key, 'wuxing': c.c1.wx + c.c2.wx,
                'pinyin': [c.c1.py[0], c.c2.py[0]]} for i, c in enumerate(results)]
        print(json.dumps({'surname': surname, 'fate': asdict(fate) if fate else None,
                          'weights': {DIM_NAMES[k]: v for k, v in zip(DIMS, normalize_weights(weights))},
                          'results': out}, ensure_ascii=False, indent=1))
        return
    if fate:
        print(f"八字 {' '.join(fate.sizhu)}  日主{fate.day_gan}{fate.day_wx}（{fate.qiangruo}） 生肖{fate.zodiac}"
              f"  用{fate.yong} 喜{fate.xi} 忌{fate.ji} 仇{fate.chou}  {fate.note}")
    nw = normalize_weights(weights)
    if not is_default_weights(nw):
        print(f'評分權重 {weights_text(nw)}')
    print(f"{'#':>2} {'姓名':<6} {'總分':>5} 等級  文化 五行 生肖 五格  音韻  筆畫        五格(天人地外總)   三才   五行  拼音")
    for i, c in enumerate(results, 1):
        wh, wx, sx, wg, yy = c.scores
        g = c.combo.ge
        print(f"{i:>2} {surname + c.name:<6} {c.total:>5} {c.grade}  {wh:>4.0f} {wx:>4.0f} {sx:>4.0f} {wg:>5.2f} {yy:>4.0f}"
              f"  {l1}{'+' + str(l2) if l2 else ''}+{c.combo.f1}+{c.combo.f2:<4} {g.tian:>2} {g.ren:>2} {g.di:>2} {g.wai:>2} {g.zong:>2}"
              f"  {c.combo.sancai_key} {c.c1.wx}{c.c2.wx}  {c.c1.py[0]} {c.c2.py[0]}")


if __name__ == '__main__':
    main(sys.argv[1:])
