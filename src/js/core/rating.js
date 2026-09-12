// 五維評分（對應 nova_core/rating.py）。運算順序與 Python 完全一致，分數逐位相等。
(function (Nova) {
  'use strict';
  const DIMS = ['wenhua', 'wuxing', 'shengxiao', 'wuge', 'yinyun'];
  const DIM_NAMES = { wenhua: '文化', wuxing: '五行', shengxiao: '生肖', wuge: '五格三才', yinyun: '音韻' };
  const WEIGHTS = { wenhua: 0.20, wuxing: 0.25, shengxiao: 0.10, wuge: 0.30, yinyun: 0.15 };
  const DEFAULT_WEIGHTS = DIMS.map((k) => WEIGHTS[k]);   // 和恰為 1，正規化不會改動任何一位
  // 預設組合（未正規化；數值只是相對比例）
  const PRESETS = {
    default: DEFAULT_WEIGHTS.slice(),
    wuge: [0, 0, 0, 1, 0],
    bazi: [0.1, 0.5, 0.2, 0.1, 0.1],
    sound: [0.3, 0.1, 0.05, 0.15, 0.4],
    equal: [1, 1, 1, 1, 1],
  };
  const PRESET_NAMES = { default: '預設五維', wuge: '只看三才五格', bazi: '八字五行為主', sound: '音韻字義為主', equal: '五維等重' };
  const WEIGHT_ALIASES = { 文化: 'wenhua', 字義: 'wenhua', 五行: 'wuxing', 八字: 'wuxing', 喜用: 'wuxing',
    生肖: 'shengxiao', 五格: 'wuge', 三才: 'wuge', 三才五格: 'wuge', 五格三才: 'wuge', 音韻: 'yinyun', 讀音: 'yinyun' };
  const WEIGHT_OTHER = ['其他', '其它', 'other', 'rest', '*'];
  const GE_WEIGHTS = [['tian', 0.15], ['ren', 0.30], ['di', 0.20], ['wai', 0.15], ['zong', 0.20]];
  const GE_NAMES = { tian: '天格', ren: '人格', di: '地格', wai: '外格', zong: '總格' };
  const SHENG = { 木: '火', 火: '土', 土: '金', 金: '水', 水: '木' };
  const KE = { 木: '土', 土: '水', 水: '火', 火: '金', 金: '木' };

  const round1 = (x) => Math.floor(x * 10 + 0.5) / 10;
  const clamp100 = (x) => (x > 100 ? 100 : x < 0 ? 0 : x);
  const isSheng = (a, b) => SHENG[a] === b;
  const isKe = (a, b) => KE[a] === b;

  // 權重（null／物件／五元陣列）→ 總和為 1 的五元陣列，順序同 DIMS。
  // 負數視為 0；全 0 或 null 回預設。同一份權重只能正規化一次（對應 Python normalize_weights）。
  function normalizeWeights(w) {
    if (w === null || w === undefined) return DEFAULT_WEIGHTS.slice();
    let vals;
    if (Array.isArray(w)) {
      if (w.length !== 5) throw new Error('權重需為 5 個數值（文化 五行 生肖 五格 音韻）');
      vals = w.map(Number);
    } else {
      vals = DIMS.map((k) => (w[k] === undefined ? WEIGHTS[k] : Number(w[k])));
    }
    vals = vals.map((v) => (!Number.isFinite(v) || v < 0 ? 0 : v));
    let s = 0;
    for (const v of vals) s += v;
    if (s <= 0) return DEFAULT_WEIGHTS.slice();
    if (s === 1) return vals;
    return vals.map((v) => v / s);
  }

  const has = (o, k) => Object.prototype.hasOwnProperty.call(o, k);

  function weightNum(k, v) {
    const t = String(v).trim();
    const n = t === '' ? NaN : Number(t);
    if (!Number.isFinite(n)) throw new Error('權重「' + k + '」需為數字，收到「' + v + '」');
    return n;
  }

  // 字串 → 未正規化的五元陣列；空字串回 null。接受：預設名稱／「三才五格=1,其他=0」／「0,0,0,1,0」
  function parseWeights(text) {
    const s = String(text == null ? '' : text).trim();
    if (!s) return null;
    if (has(PRESETS, s)) return PRESETS[s].slice();
    const parts = s.split(/[,;、\s]+/).filter(Boolean);
    if (parts.every((p) => !p.includes('=') && !p.includes(':'))) {
      if (parts.length !== 5) throw new Error('位置式權重需為 5 個數字：文化,五行,生肖,五格,音韻');
      return parts.map((p, i) => weightNum(DIM_NAMES[DIMS[i]], p));
    }
    const named = {};
    let other = null;
    for (const p of parts) {
      const q = p.replace(/:/g, '='), i = q.indexOf('=');
      const k = q.slice(0, i).trim(), v = q.slice(i + 1);
      if (WEIGHT_OTHER.includes(k)) { other = weightNum(k, v); continue; }
      const key = DIMS.includes(k) ? k : (has(WEIGHT_ALIASES, k) ? WEIGHT_ALIASES[k] : null);
      if (!key) throw new Error('未知的權重項目「' + k + '」（可用：' + DIMS.map((d) => DIM_NAMES[d]).join('、') + '、其他）');
      named[key] = weightNum(k, v);
    }
    return DIMS.map((k) => (named[k] !== undefined ? named[k] : (other === null ? WEIGHTS[k] : other)));
  }

  // 正規化後的權重 → 「文化 20%、五行 25%…」；只列不為 0 的項目
  function weightsText(w) {
    const parts = DIMS.map((k, i) => [k, w[i]]).filter(([, v]) => v > 0).map(([k, v]) => DIM_NAMES[k] + ' ' + round1(v * 100) + '%');
    return parts.length ? parts.join('、') : '（無）';
  }

  const isDefaultWeights = (w) => DEFAULT_WEIGHTS.every((v, i) => v === w[i]);

  function grade(total) {
    if (total >= 90) return '上上';
    if (total >= 80) return '上吉';
    if (total >= 70) return '中吉';
    if (total >= 60) return '中平';
    if (total >= 50) return '中下';
    return '下下';
  }

  function rateWenhua(c1, c2) {
    let s = 60, d = [];
    for (const c of [c1, c2]) {
      if (c.regular && c.nameable) { s += 5; d.push('「' + c.char + '」為常用取名用字'); }
      else if (c.regular) s += 2;
    }
    for (const c of [c1, c2]) { if (c.lvl > 0 && c.lvl <= 2) s += 3; else if (c.lvl === 3) s += 1; }
    for (const c of [c1, c2]) if (c.meaning) s += 4;
    for (const c of [c1, c2]) if (c.stroke >= 5 && c.stroke <= 15) s += 2;
    if (c1.stroke > 0 && c2.stroke > 0 && Math.abs(c1.stroke - c2.stroke) <= 5) { s += 2; d.push('筆畫搭配勻稱'); }
    if (c1.py.length && c2.py.length) s += 2;
    return [clamp100(s), d];
  }

  function rateWuxing(c1, c2, fate) {
    if (!fate) return [80, ['無生辰資料，五行以中性計']];
    let s = 70, d = [];
    for (const c of [c1, c2]) {
      if (!c.wx) continue;
      if (c.wx === fate.yong) { s += 12; d.push('「' + c.char + '」五行屬' + c.wx + '，為用神，加分'); }
      else if (c.wx === fate.ji) { s -= 8; d.push('「' + c.char + '」五行屬' + c.wx + '，為忌神，減分'); }
      else d.push('「' + c.char + '」五行屬' + c.wx + '，中性');
    }
    if (c1.wx && c2.wx) {
      if (isSheng(c1.wx, c2.wx) || isSheng(c2.wx, c1.wx)) { s += 8; d.push('兩字五行相生，搭配協調'); }
      if (isKe(c1.wx, c2.wx) || isKe(c2.wx, c1.wx)) { s -= 5; d.push('兩字五行相剋，需注意'); }
    }
    return [clamp100(s), d];
  }

  function rateShengxiao(c1, c2, fate) {
    let s = 80;
    if (!fate) return [s, []];
    const zwx = globalThis.NOVA_TABLES.bazi.zodiac_wuxing[fate.zodiac] || '';
    const d = [];
    if (zwx) {
      d.push('生肖' + fate.zodiac + '，五行屬' + zwx);
      for (const c of [c1, c2]) if (c.wx && (isSheng(zwx, c.wx) || isSheng(c.wx, zwx))) { s += 7; d.push('「' + c.char + '」與生肖五行相生'); }
      for (const c of [c1, c2]) if (c.wx && (isKe(zwx, c.wx) || isKe(c.wx, zwx))) { s -= 5; d.push('「' + c.char + '」與生肖五行相剋'); }
    }
    return [clamp100(s), d];
  }

  // 只依賴筆畫。順序：天→人→地→外→總→總格最大好運→三才。回傳 [score, details, ge, sancaiKey]
  function rateWuge(l1, l2, f1, f2) {
    if (l1 === 0) return [70, ['無姓氏筆畫'], null, ''];
    const g = Nova.wuge.calcWuge(l1, l2, f1, f2);
    let s = 60, d = [];
    for (const [name, w] of GE_WEIGHTS) {
      const n = g[name], dy = Nova.dayan.find(n);
      if (dy.lucky === '半吉') s += 8 * w;
      else if (dy.lucky === '吉') s += 15 * w;
      else s -= 5 * w;
      d.push(GE_NAMES[name] + n + '（' + dy.title + '）' + dy.lucky);
    }
    if (Nova.dayan.find(g.zong).max_luck) { s += 5; d.push('總格為最大好運數'); }
    const key = Nova.sancai.keyOf(g.tian, g.ren, g.di);
    const v = Nova.sancai.verdict(key);
    if (v === '大吉') s += 12;
    else if (v === '吉' || v === '吉多於凶') s += 8;
    else if (v === '中吉') s += 5;
    else if (v === '凶多於吉' || v === '吉凶參半') s -= 2;
    else if (v === '凶' || v === '大凶') s -= 6;
    d.push('三才' + key + v);
    return [clamp100(s), d, g, key];
  }

  function rateYinyun(c1, c2) {
    let s = 80, d = [];
    if (!c1.py.length || !c2.py.length) return [s, d];
    const Y = Nova.yinyun, p1 = c1.py[0], p2 = c2.py[0];
    const t1 = Y.tone(p1), t2 = Y.tone(p2);
    if (t1 !== t2 && t1 && t2) { s += 8; d.push('兩字聲調不同，抑揚頓挫'); }
    else if (t1 === t2 && t1) { s -= 5; d.push('兩字聲調相同'); }
    const s1 = Y.shengmu(p1), s2 = Y.shengmu(p2);
    if (s1 !== s2 && s1 && s2) { s += 5; d.push('聲母不同，發音清晰'); }
    else if (s1 === s2 && s1) { s -= 3; d.push('聲母相同'); }
    const y1 = Y.yunmu(p1), y2 = Y.yunmu(p2);
    if (y1 !== y2 && y1 && y2) { s += 4; d.push('韻母不同，朗朗上口'); }
    else if (y1 === y2 && y1) { s -= 3; d.push('韻母相同'); }
    return [clamp100(s), d];
  }

  // 加權總分；w 必須是 normalizeWeights 的輸出。與 Python total_of 同一運算順序
  function totalOf(wh, wx, sx, wg, yy, w) {
    const q = w || DEFAULT_WEIGHTS;
    return round1(wh * q[0] + wx * q[1] + sx * q[2] + wg * q[3] + yy * q[4]);
  }

  function rateName(l1, l2, c1, c2, fate, weights) {
    const w = normalizeWeights(weights === undefined ? null : weights);
    const [wh, d1] = rateWenhua(c1, c2);
    const [wx, d2] = rateWuxing(c1, c2, fate);
    const [sx, d3] = rateShengxiao(c1, c2, fate);
    const [wg, d4, ge, sancaiKey] = rateWuge(l1, l2, c1.stroke, c2.stroke);
    const [yy, d5] = rateYinyun(c1, c2);
    const total = totalOf(wh, wx, sx, wg, yy, w);
    return { wenhua: wh, wuxing: wx, shengxiao: sx, wuge: wg, yinyun: yy, total, grade: grade(total), ge, sancaiKey,
      details: { wenhua: d1, wuxing: d2, shengxiao: d3, wuge: d4, yinyun: d5 }, weights: w };
  }

  Nova.rating = { DIMS, DIM_NAMES, WEIGHTS, DEFAULT_WEIGHTS, PRESETS, PRESET_NAMES, GE_WEIGHTS, GE_NAMES, SHENG, KE,
    round1, clamp100, isSheng, isKe, grade, normalizeWeights, parseWeights, weightsText, isDefaultWeights,
    rateWenhua, rateWuxing, rateShengxiao, rateWuge, rateYinyun, totalOf, rateName };
})(globalThis.Nova = globalThis.Nova || {});
