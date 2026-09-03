"""命令列：python -m nova_core.cli 陳 --born 2026-09-03T10:30 --gender girl [--top 10] [--json]

亦可對單一名字出報告：python -m nova_core.cli 陳 --explain 冠宇 --born 2026-09-03T10:30
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from datetime import datetime

from . import bazi as bazi_mod
from . import chars, sancai
from .dayan import find as find_dayan
from .generator import Options, generate
from .rating import GE_NAMES, rate_name
from .wuge import element_of, yinyang_of


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
    p.add_argument('--avoid', default='', help='排除字，如 死病')
    p.add_argument('--require', default='', help='名字至少含其一的字')
    p.add_argument('--first', help='指定第一字（輩字）')
    p.add_argument('--second', help='指定第二字')
    p.add_argument('--surname-strokes', help='手動指定姓氏筆畫，如 16 或 15,17')
    p.add_argument('--female-caution', dest='female_caution', action=argparse.BooleanOptionalAction, default=None,
                   help='排除女性不宜之總格（預設：女生開、男生關）')
    p.add_argument('--explain', metavar='NAME', help='只對此名字（2 字）輸出完整評分報告')
    p.add_argument('--json', action='store_true', help='以 JSON 輸出')
    return p


def fate_from_args(args) -> bazi_mod.FateData | None:
    if not args.born:
        return None
    y, m, d, h, mi = parse_born(args.born)
    return bazi_mod.compute(y, m, d, h, mi, method=args.method)


def explain(surname: str, l1: int, l2: int, name: str, fate, as_json: bool) -> None:
    if len(name) != 2:
        raise SystemExit('--explain 需為 2 字名')
    c1, c2 = chars.lookup(name[0]), chars.lookup(name[1])
    if not c1 or not c2:
        raise SystemExit(f'字典中查無「{name}」的用字')
    r = rate_name(l1, l2, c1, c2, fate)
    ge = r.ge
    report = {
        'name': surname + name, 'total': r.total, 'grade': r.grade,
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
    if not args.json and notes:
        print('；'.join(notes))
    if args.explain:
        explain(surname, l1, l2, args.explain, fate, args.json)
        return
    female = args.female_caution if args.female_caution is not None else (args.gender == 'girl')
    opt = Options(strictness=args.strictness, exclude_female_caution=female, max_level=args.level,
                  avoid_chars=frozenset(args.avoid), require_chars=frozenset(args.require),
                  fixed_first=args.first, fixed_second=args.second, top_n=args.top)
    results = generate(l1, l2, fate, opt)
    if args.json:
        out = [{'rank': i + 1, 'name': surname + c.name, 'total': c.total, 'grade': c.grade,
                'scores': dict(zip(('文化', '五行', '生肖', '五格', '音韻'), c.scores)),
                'strokes': [l1, l2, c.combo.f1, c.combo.f2], 'wuge': c.combo.ge.as_dict(),
                'sancai': c.combo.sancai_key, 'wuxing': c.c1.wx + c.c2.wx,
                'pinyin': [c.c1.py[0], c.c2.py[0]]} for i, c in enumerate(results)]
        print(json.dumps({'surname': surname, 'fate': asdict(fate) if fate else None, 'results': out},
                         ensure_ascii=False, indent=1))
        return
    if fate:
        print(f"八字 {' '.join(fate.sizhu)}  日主{fate.day_gan}{fate.day_wx}（{fate.qiangruo}） 生肖{fate.zodiac}"
              f"  用{fate.yong} 喜{fate.xi} 忌{fate.ji} 仇{fate.chou}  {fate.note}")
    print(f"{'#':>2} {'姓名':<6} {'總分':>5} 等級  文化 五行 生肖 五格  音韻  筆畫        五格(天人地外總)   三才   五行  拼音")
    for i, c in enumerate(results, 1):
        wh, wx, sx, wg, yy = c.scores
        g = c.combo.ge
        print(f"{i:>2} {surname + c.name:<6} {c.total:>5} {c.grade}  {wh:>4.0f} {wx:>4.0f} {sx:>4.0f} {wg:>5.2f} {yy:>4.0f}"
              f"  {l1}{'+' + str(l2) if l2 else ''}+{c.combo.f1}+{c.combo.f2:<4} {g.tian:>2} {g.ren:>2} {g.di:>2} {g.wai:>2} {g.zong:>2}"
              f"  {c.combo.sancai_key} {c.c1.wx}{c.c2.wx}  {c.c1.py[0]} {c.c2.py[0]}")


if __name__ == '__main__':
    main(sys.argv[1:])
