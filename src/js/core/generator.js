// 候選產生（對應 nova_core/generator.py）：合格筆畫組合 → 字對交叉 → 快速評分 → Top-N（有界堆 + 上界剪枝）。
(function (Nova) {
  'use strict';
  const DAYAN_NEED = { strict: ['ren', 'di', 'wai', 'zong'], moderate: ['ren', 'di', 'zong'], relaxed: ['ren', 'zong'] };
  const MAX_WENHUA = 92, MAX_WUXING = 100, MAX_SHENGXIAO = 94, MAX_YINYUN = 97;

  function defaultOptions() {
    return {
      strictness: 'moderate', zongAccept: Nova.dayan.LUCKY_ACCEPT_DEFAULT, excludeFemaleCaution: false,
      maxLevel: 2, avoidChars: new Set(), requireChars: new Set(), fixedFirst: null, fixedSecond: null,
      topN: 10, minStroke: 1, maxStroke: Nova.wuge.MAX_STROKE,
    };
  }

  function luckyCombos(l1, l2, opt) {
    const need = DAYAN_NEED[opt.strictness];
    const out = [];
    for (let f1 = opt.minStroke; f1 <= opt.maxStroke; f1++) {
      for (let f2 = opt.minStroke; f2 <= opt.maxStroke; f2++) {
        const g = Nova.wuge.calcWuge(l1, l2, f1, f2);
        const zd = Nova.dayan.find(g.zong);
        if (!opt.zongAccept.has(zd.lucky)) continue;
        if (opt.excludeFemaleCaution && zd.female_caution) continue;
        if (need.some((k) => !opt.zongAccept.has(Nova.dayan.find(g[k]).lucky))) continue;
        const key = Nova.sancai.keyOf(g.tian, g.ren, g.di);
        if (!Nova.sancai.passes(key, opt.strictness)) continue;
        const [score, details] = Nova.rating.rateWuge(l1, l2, f1, f2);
        out.push({ f1, f2, ge: g, sancaiKey: key, wugeScore: score, wugeDetails: details });
      }
    }
    return out;
  }

  // 單字預算分（整數），與 rating.rate* 逐字加項一致
  function precompute(c, fate) {
    const R = Nova.rating, Y = Nova.yinyun;
    let wh = c.regular && c.nameable ? 5 : c.regular ? 2 : 0;
    wh += c.lvl > 0 && c.lvl <= 2 ? 3 : c.lvl === 3 ? 1 : 0;
    wh += c.meaning ? 4 : 0;
    wh += c.stroke >= 5 && c.stroke <= 15 ? 2 : 0;
    let wx = 0, sx = 0;
    if (fate && c.wx) {
      wx = c.wx === fate.yong ? 12 : c.wx === fate.ji ? -8 : 0;
      const zwx = globalThis.NOVA_TABLES.bazi.zodiac_wuxing[fate.zodiac] || '';
      if (zwx) {
        if (R.isSheng(zwx, c.wx) || R.isSheng(c.wx, zwx)) sx += 7;
        if (R.isKe(zwx, c.wx) || R.isKe(c.wx, zwx)) sx -= 5;
      }
    }
    const p = c.py.length ? c.py[0] : '';
    return { c, wenhua: wh, wuxing: wx, shengxiao: sx, tone: Y.tone(p), sm: Y.shengmu(p), ym: Y.yunmu(p) };
  }

  // [文化, 五行, 生肖, 五格, 音韻]，與 rateName 逐項相等
  function fastScores(a, b, combo, fate) {
    const R = Nova.rating;
    let wh = 60 + a.wenhua + b.wenhua;
    if (a.c.stroke > 0 && b.c.stroke > 0 && Math.abs(a.c.stroke - b.c.stroke) <= 5) wh += 2;
    if (a.c.py.length && b.c.py.length) wh += 2;
    let wx, sx;
    if (!fate) { wx = 80; sx = 80; } else {
      wx = 70 + a.wuxing + b.wuxing;
      if (a.c.wx && b.c.wx) {
        if (R.isSheng(a.c.wx, b.c.wx) || R.isSheng(b.c.wx, a.c.wx)) wx += 8;
        if (R.isKe(a.c.wx, b.c.wx) || R.isKe(b.c.wx, a.c.wx)) wx -= 5;
      }
      sx = 80 + a.shengxiao + b.shengxiao;
    }
    let yy = 80;
    if (a.c.py.length && b.c.py.length) {
      if (a.tone !== b.tone && a.tone && b.tone) yy += 8; else if (a.tone === b.tone && a.tone) yy -= 5;
      if (a.sm !== b.sm && a.sm && b.sm) yy += 5; else if (a.sm === b.sm && a.sm) yy -= 3;
      if (a.ym !== b.ym && a.ym && b.ym) yy += 4; else if (a.ym === b.ym && a.ym) yy -= 3;
    }
    return [R.clamp100(wh), R.clamp100(wx), R.clamp100(sx), combo.wugeScore, R.clamp100(yy)];
  }

  // 堆鍵：[total, -(lvl1+lvl2), -cp1, -cp2]；越大越好（最差在堆頂）
  const heapKey = (total, c1, c2) => [total, -(c1.lvl + c2.lvl), -c1.char.codePointAt(0), -c2.char.codePointAt(0)];
  function cmpKey(a, b) {
    for (let i = 0; i < 4; i++) if (a[i] !== b[i]) return a[i] < b[i] ? -1 : 1;
    return 0;
  }
  // 最小堆（元素 {key, cand}）
  class MinHeap {
    constructor() { this.a = []; }
    get size() { return this.a.length; }
    top() { return this.a[0]; }
    push(x) { this.a.push(x); this._up(this.a.length - 1); }
    replaceTop(x) { this.a[0] = x; this._down(0); }
    _up(i) { const a = this.a; while (i > 0) { const p = (i - 1) >> 1; if (cmpKey(a[i].key, a[p].key) < 0) { [a[i], a[p]] = [a[p], a[i]]; i = p; } else break; } }
    _down(i) {
      const a = this.a, n = a.length;
      for (;;) {
        let m = i; const l = 2 * i + 1, r = l + 1;
        if (l < n && cmpKey(a[l].key, a[m].key) < 0) m = l;
        if (r < n && cmpKey(a[r].key, a[m].key) < 0) m = r;
        if (m === i) break;
        [a[i], a[m]] = [a[m], a[i]]; i = m;
      }
    }
  }

  // 排名：總分降冪 → 等級和升冪 → 第一字碼位 → 第二字碼位
  function sortCandidates(list) {
    return list.sort((x, y) => y.total - x.total || (x.c1.lvl + x.c2.lvl) - (y.c1.lvl + y.c2.lvl)
      || x.c1.char.codePointAt(0) - y.c1.char.codePointAt(0) || x.c2.char.codePointAt(0) - y.c2.char.codePointAt(0));
  }

  // onProgress(i, n) 每處理一個筆畫組合呼叫一次
  function generate(l1, l2, fate, options, onProgress) {
    const opt = Object.assign(defaultOptions(), options || {});
    const R = Nova.rating;
    const combos = luckyCombos(l1, l2, opt).sort((a, b) => b.wugeScore - a.wugeScore);
    const buckets = Nova.chars.byStroke(opt.maxLevel);
    const preCache = new Map();
    const pres = (stroke, fixed) => {
      if (fixed) {
        const ci = Nova.chars.lookup(fixed);
        if (!ci || ci.stroke !== stroke) return [];
        if (!preCache.has(fixed)) preCache.set(fixed, precompute(ci, fate));
        return [preCache.get(fixed)];
      }
      const out = [];
      for (const c of buckets.get(stroke) || []) {
        if (opt.avoidChars.has(c.char)) continue;
        let p = preCache.get(c.char);
        if (!p) { p = precompute(c, fate); preCache.set(c.char, p); }
        out.push(p);
      }
      return out;
    };
    const heap = new MinHeap();
    combos.forEach((combo, i) => {
      if (onProgress) onProgress(i, combos.length);
      if (heap.size >= opt.topN) {
        const bound = R.totalOf(MAX_WENHUA, MAX_WUXING, MAX_SHENGXIAO, combo.wugeScore, MAX_YINYUN);
        if (bound < heap.top().key[0]) return;
      }
      const firsts = pres(combo.f1, opt.fixedFirst), seconds = pres(combo.f2, opt.fixedSecond);
      for (const a of firsts) {
        for (const b of seconds) {
          if (opt.requireChars.size && !opt.requireChars.has(a.c.char) && !opt.requireChars.has(b.c.char)) continue;
          const scores = fastScores(a, b, combo, fate);
          const total = R.totalOf(scores[0], scores[1], scores[2], scores[3], scores[4]);
          const key = heapKey(total, a.c, b.c);
          if (heap.size < opt.topN) heap.push({ key, cand: { c1: a.c, c2: b.c, combo, scores, total, grade: R.grade(total) } });
          else if (cmpKey(key, heap.top().key) > 0) heap.replaceTop({ key, cand: { c1: a.c, c2: b.c, combo, scores, total, grade: R.grade(total) } });
        }
      }
    });
    return sortCandidates(heap.a.map((x) => x.cand));
  }

  Nova.generator = { DAYAN_NEED, defaultOptions, luckyCombos, precompute, fastScores, generate, sortCandidates };
})(globalThis.Nova = globalThis.Nova || {});
