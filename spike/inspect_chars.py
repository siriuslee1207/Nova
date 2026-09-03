"""M0 spike: inspect fate's character.json to decide ETL thresholds."""
import collections, json, statistics, unicodedata

data = json.load(open('data/raw/character.json', encoding='utf-8'))
print('records', len(data))
keys = collections.Counter()
for r in data:
    keys.update(r.keys())
print('keys', keys.most_common())

def cnt(pred):
    return sum(1 for r in data if pred(r))

for k in ['is_simplified', 'is_traditional', 'is_kangxi', 'is_variant', 'is_ancient', 'nameable', 'regular',
          'wu_xing', 'pinyin', 'meaning', 'science_stroke', 'kangxi_stroke', 'traditional_stroke',
          'simplified_stroke', 'radical', 'simplified_of_char', 'variant_of_char', 'traditional_chars',
          'simplified_chars', 'variant_chars', 'gender_hint', 'source']:
    print(f'  has {k}:', cnt(lambda r, k=k: r.get(k)))
print('common_level dist', sorted(collections.Counter(r.get('common_level') for r in data).items(), key=str))
print('gender_hint dist', collections.Counter(r.get('gender_hint') for r in data))
print('wu_xing dist', collections.Counter(r.get('wu_xing') for r in data))
print('source dist', collections.Counter(r.get('source') for r in data).most_common(8))

def trad_ok(r):
    return r.get('is_traditional') or r.get('is_kangxi') or (r.get('is_simplified') and not r.get('simplified_of_char'))

pool = [r for r in data if r.get('nameable') and r.get('wu_xing') and r.get('pinyin')
        and not r.get('is_variant') and not r.get('is_ancient')]
print('pool nameable+wuxing+pinyin-variant-ancient', len(pool))
pool2 = [r for r in pool if trad_ok(r)]
print('pool2 +trad_ok', len(pool2))
pool3 = [r for r in pool2 if r.get('regular')]
print('pool3 +regular', len(pool3))
print('pool2 common_level dist', sorted(collections.Counter(r.get('common_level') for r in pool2).items(), key=str))
print('pool2 is_simplified&is_traditional both', sum(1 for r in pool2 if r.get('is_simplified') and r.get('is_traditional')))
print('pool2 only simplified (same-form)', sum(1 for r in pool2 if r.get('is_simplified') and not r.get('is_traditional')))

agree = dis = miss = 0
ex = []
for r in pool2:
    s, k = r.get('science_stroke'), r.get('kangxi_stroke')
    if not s or not k:
        miss += 1
        continue
    if s == k:
        agree += 1
    else:
        dis += 1
        if len(ex) < 40:
            ex.append((r['char'], 'sci', s, 'kx', k, 'trad', r.get('traditional_stroke'), r.get('radical')))
print('science vs kangxi agree/dis/miss', agree, dis, miss)
print('  disagree samples', ex)
print('stroke>30 in pool2', sum(1 for r in pool2 if (r.get('science_stroke') or r.get('kangxi_stroke') or 0) > 30))
print('stroke dist pool2', sorted(collections.Counter(r.get('science_stroke') or r.get('kangxi_stroke') for r in pool2).items(), key=lambda x: (x[0] is None, x[0])))

tone_digit = sum(1 for r in pool2 if r['pinyin'][0] and r['pinyin'][0][-1].isdigit())
diacritic = sum(1 for r in pool2 if any(unicodedata.decomposition(c) for c in r['pinyin'][0]))
print('pinyin: digit-tone', tone_digit, 'diacritic', diacritic, 'sample', [r['pinyin'] for r in pool2[:10]])
print('pinyin count dist', collections.Counter(len(r['pinyin']) for r in pool2))

ml = [len(r['meaning']) for r in pool2 if r.get('meaning')]
print('meaning count', len(ml), 'mean', round(statistics.mean(ml), 1), 'median', statistics.median(ml), 'max', max(ml))
print('meaning >40 chars', sum(1 for x in ml if x > 40), '>80', sum(1 for x in ml if x > 80))
print('meaning samples', [(r['char'], r['meaning'][:70]) for r in pool2[:6] if r.get('meaning')])

byc = {r['char']: r for r in data}
for ch in ['陳', '陈', '冠', '宇', '歐', '陽', '欧', '阳', '俊', '萱', '浩', '然', '淼', '藝']:
    r = byc.get(ch)
    print(ch, json.dumps({k: v for k, v in r.items() if k not in ('comment',)}, ensure_ascii=False) if r else 'NOT FOUND')

est = sum(3 + len(','.join(r['pinyin'][:2])) + 14 + min(len(r.get('meaning') or ''), 40) * 3 + 3 for r in pool2)
print('est bytes pool2 compact (meaning<=40)', est)

surnames = '陳林黃張李王吳劉蔡楊許鄭謝郭洪邱曾廖賴徐周葉蘇莊呂江何蕭羅高潘簡朱鍾游彭詹胡施沈余盧梁趙顏柯翁魏孫戴范方宋鄧杜傅侯曹薛丁卓阮馬董溫唐藍蔣石古紀姚連馮歐程湯黎韓姜'
for ch in surnames:
    r = byc.get(ch)
    if not r or not (r.get('science_stroke') or r.get('kangxi_stroke')):
        print('surname missing/no-stroke:', ch, r and {k: r.get(k) for k in ('science_stroke', 'kangxi_stroke', 'is_traditional')})
print('surname check done')
