"""M0 spike: can Unihan (kRSUnicode + Kangxi radical strokes) reproduce 康熙 stroke counts?"""
import io, json, zipfile, collections

# Kangxi radical number -> stroke count of the radical (ranges by radical index)
RANGES = [(1, 6, 1), (7, 29, 2), (30, 60, 3), (61, 94, 4), (95, 117, 5), (118, 146, 6), (147, 166, 7),
          (167, 175, 8), (176, 186, 9), (187, 194, 10), (195, 200, 11), (201, 204, 12), (205, 208, 13),
          (209, 210, 14), (211, 211, 15), (212, 213, 16), (214, 214, 17)]
RAD_STROKES = {}
for a, b, s in RANGES:
    for r in range(a, b + 1):
        RAD_STROKES[r] = s

z = zipfile.ZipFile('data/raw/Unihan.zip')
uni = collections.defaultdict(dict)
for fn in ('Unihan_IRGSources.txt', 'Unihan_Readings.txt', 'Unihan_OtherMappings.txt', 'Unihan_Variants.txt', 'Unihan_DictionaryLikeData.txt'):
    with z.open(fn) as f:
        for line in io.TextIOWrapper(f, encoding='utf-8'):
            if line.startswith('#') or not line.strip():
                continue
            cp, fld, val = line.rstrip('\n').split('\t', 2)
            if fld in ('kRSUnicode', 'kTotalStrokes', 'kMandarin', 'kDefinition', 'kBigFive', 'kTraditionalVariant', 'kSimplifiedVariant', 'kGradeLevel'):
                uni[chr(int(cp[2:], 16))][fld] = val

def kx_total(ch):
    rs = uni.get(ch, {}).get('kRSUnicode')
    if not rs:
        return None
    first = rs.split()[0]
    rad, res = first.split('.')
    rad = int(rad.rstrip("'"))
    return RAD_STROKES[rad] + int(res)

def total(ch):
    t = uni.get(ch, {}).get('kTotalStrokes')
    return int(t.split()[0]) if t else None

data = json.load(open('data/raw/character.json', encoding='utf-8'))
byc = {r['char']: r for r in data}

want = '成城余曲岳陳謝藝泛回四七十陽遲以延俊然冠宇歐萱浩于台合云系征咸乃卜么尸升吊帚垮坑附隊'
print('char | unihan kRSUnicode kTotalStrokes kx_total(rad+res) | fate kangxi trad science | kMandarin')
for c in want:
    u = uni.get(c, {})
    r = byc.get(c, {})
    print(c, '|', u.get('kRSUnicode'), u.get('kTotalStrokes'), kx_total(c), '|', r.get('kangxi_stroke'), r.get('traditional_stroke'), r.get('science_stroke'), '|', u.get('kMandarin'))

# Big5 level-1 set
lvl1 = []
for hi in range(0xA4, 0xC7):
    for lo in list(range(0x40, 0x7F)) + list(range(0xA1, 0xFF)):
        code = hi << 8 | lo
        if not (0xA440 <= code <= 0xC67E):
            continue
        try:
            ch = bytes([hi, lo]).decode('big5')
        except UnicodeDecodeError:
            continue
        if len(ch) == 1 and '一' <= ch <= '鿿':
            lvl1.append(ch)
present = [c for c in lvl1 if c in byc]
agree_kx = agree_tot = agree_tr_tot = both = 0
dis = []
for c in present:
    r = byc[c]
    k = kx_total(c); t = total(c); fk = r.get('kangxi_stroke'); ft = r.get('traditional_stroke')
    if k is None:
        continue
    both += 1
    if k == fk: agree_kx += 1
    if t == fk: agree_tot += 1
    if t == ft: agree_tr_tot += 1
    if k != fk:
        dis.append((c, 'uni_kx', k, 'uni_tot', t, 'fate_kx', fk, 'fate_tr', ft))
print(f'level1 present={len(present)} with unihan={both}; unihan_kx==fate_kx {agree_kx}; unihan_total==fate_kx {agree_tot}; unihan_total==fate_trad {agree_tr_tot}')
print('disagreements unihan_kx vs fate_kx:', len(dis))
print(dis[:120])
# how do kTotalStrokes and rad+res differ among level1?
d2 = [(c, kx_total(c), total(c)) for c in present if kx_total(c) != total(c)]
print('unihan rad+res != kTotalStrokes count:', len(d2), d2[:60])
# missing 88: do they have unihan data?
missing = [c for c in lvl1 if c not in byc]
print('missing level1 with kRSUnicode:', sum(1 for c in missing if uni.get(c, {}).get('kRSUnicode')), 'with kMandarin:', sum(1 for c in missing if uni.get(c, {}).get('kMandarin')), 'with kDefinition:', sum(1 for c in missing if uni.get(c, {}).get('kDefinition')))
print([(c, kx_total(c), uni[c].get('kMandarin'), (uni[c].get('kDefinition') or '')[:30]) for c in missing[:20]])
# kTraditionalVariant sample for simplified surname chars
for c in '陈欧谢艺才后干于万':
    print(c, uni.get(c, {}).get('kTraditionalVariant'), uni.get(c, {}).get('kSimplifiedVariant'))
