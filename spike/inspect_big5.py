"""M0 spike: measure Big5 常用/次常用 coverage of fate character.json."""
import collections, json

data = json.load(open('data/raw/character.json', encoding='utf-8'))
byc = {r['char']: r for r in data}

lvl = {1: [], 2: []}
for hi in range(0xA4, 0xFA):
    for lo in list(range(0x40, 0x7F)) + list(range(0xA1, 0xFF)):
        code = hi << 8 | lo
        L = 1 if 0xA440 <= code <= 0xC67E else 2 if 0xC940 <= code <= 0xF9D5 else None
        if not L:
            continue
        try:
            ch = bytes([hi, lo]).decode('big5')
        except UnicodeDecodeError:
            continue
        if len(ch) == 1 and ('一' <= ch <= '鿿' or '㐀' <= ch <= '䶿'):
            lvl[L].append(ch)
print('big5 常用', len(lvl[1]), '次常用', len(lvl[2]))

for L in (1, 2):
    present = [c for c in lvl[L] if c in byc]
    missing = [c for c in lvl[L] if c not in byc]
    print(f'level {L}: present {len(present)} missing {len(missing)}')
    print('  missing sample:', ''.join(missing[:300]))
    p = [byc[c] for c in present]
    print('  nameable', sum(1 for r in p if r.get('nameable')),
          'pinyin', sum(1 for r in p if r.get('pinyin')),
          'wu_xing', sum(1 for r in p if r.get('wu_xing')),
          'kangxi_stroke', sum(1 for r in p if r.get('kangxi_stroke')),
          'meaning', sum(1 for r in p if r.get('meaning')),
          'regular', sum(1 for r in p if r.get('regular')),
          'is_variant', sum(1 for r in p if r.get('is_variant')),
          'simp_of!=self', sum(1 for r in p if r.get('simplified_of_char') and r['simplified_of_char'] != r['char']))
    pool = [r for r in p if r.get('nameable') and r.get('pinyin') and r.get('wu_xing') and 1 <= (r.get('kangxi_stroke') or 0) <= 30]
    print('  pool(nameable,pinyin,wuxing,kx1..30)', len(pool))
    no_name = [r['char'] for r in p if not r.get('nameable')]
    print('  not nameable sample:', ''.join(no_name[:150]))
    eng = sum(1 for r in pool if r.get('meaning') and all(ord(ch) < 128 for ch in r['meaning'][:20]))
    print('  meaning english-ish', eng, 'chinese', sum(1 for r in pool if r.get('meaning')) - eng, 'none', sum(1 for r in pool if not r.get('meaning')))
    print('  wu_xing dist', collections.Counter(r['wu_xing'] for r in pool))
    print('  kangxi==trad', sum(1 for r in pool if r.get('kangxi_stroke') == r.get('traditional_stroke')),
          'kangxi!=trad', sum(1 for r in pool if r.get('kangxi_stroke') != r.get('traditional_stroke')),
          'kangxi==science', sum(1 for r in pool if r.get('kangxi_stroke') == r.get('science_stroke')))
    diff = [(r['char'], 'kx', r['kangxi_stroke'], 'tr', r['traditional_stroke'], 'sci', r['science_stroke'], r['radical']) for r in pool if r.get('kangxi_stroke') != r.get('traditional_stroke')][:50]
    print('  kx!=trad samples', diff)
    est = sum(3 + len(','.join(r['pinyin'][:2])) + 16 + min(len(r.get('meaning') or ''), 30) * 3 for r in pool)
    print('  est bytes (meaning<=30)', est)

m = {r['char']: r['simplified_of_char'] for r in data if r.get('simplified_of_char') and r['simplified_of_char'] != r['char']}
print('simp->trad pairs (distinct)', len(m), 'sample', list(m.items())[:25])
multi = collections.Counter(m.values())
print('trad with multiple simp', [(t, c) for t, c in multi.items() if c > 1][:20])
print('targets missing from data', sum(1 for t in set(m.values()) if t not in byc))
# radical-based check of 阜 chars stroke
fu = [(r['char'], r['kangxi_stroke'], r['traditional_stroke'], r['science_stroke']) for r in data if r.get('radical') == '阜' and r['char'] in set(lvl[1])][:40]
print('阜 radical samples (kx,trad,sci)', fu)
