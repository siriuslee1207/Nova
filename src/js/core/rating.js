// 五維評分（對應 nova_core/rating.py）。運算順序與 Python 完全一致，分數逐位相等。
(function (Nova) {
  'use strict';
  const WEIGHTS = { wenhua: 0.20, wuxing: 0.25, shengxiao: 0.10, wuge: 0.30, yinyun: 0.15 };
  const GE_WEIGHTS = [['tian', 0.15], ['ren', 0.30], ['di', 0.20], ['wai', 0.15], ['zong', 0.20]];
  const GE_NAMES = { tian: '天格', ren: '人格', di: '地格', wai: '外格', zong: '總格' };
  const SHENG = { 木: '火', 火: '土', 土: '金', 金: '水', 水: '木' };
  const KE = { 木: '土', 土: '水', 水: '火', 火: '金', 金: '木' };

  const round1 = (x) => Math.floor(x * 10 + 0.5) / 10;
  const clamp100 = (x) => (x > 100 ? 100 : x < 0 ? 0 : x);
  const isSheng = (a, b) => SHENG[a] === b;
  const isKe = (a, b) => KE[a] === b;

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

  // 加權總分；與 Python total_of 同一運算順序
  function totalOf(wh, wx, sx, wg, yy) {
    return round1(wh * WEIGHTS.wenhua + wx * WEIGHTS.wuxing + sx * WEIGHTS.shengxiao + wg * WEIGHTS.wuge + yy * WEIGHTS.yinyun);
  }

  function rateName(l1, l2, c1, c2, fate) {
    const [wh, d1] = rateWenhua(c1, c2);
    const [wx, d2] = rateWuxing(c1, c2, fate);
    const [sx, d3] = rateShengxiao(c1, c2, fate);
    const [wg, d4, ge, sancaiKey] = rateWuge(l1, l2, c1.stroke, c2.stroke);
    const [yy, d5] = rateYinyun(c1, c2);
    const total = totalOf(wh, wx, sx, wg, yy);
    return { wenhua: wh, wuxing: wx, shengxiao: sx, wuge: wg, yinyun: yy, total, grade: grade(total), ge, sancaiKey,
      details: { wenhua: d1, wuxing: d2, shengxiao: d3, wuge: d4, yinyun: d5 } };
  }

  Nova.rating = { WEIGHTS, GE_WEIGHTS, GE_NAMES, SHENG, KE, round1, clamp100, isSheng, isKe, grade,
    rateWenhua, rateWuxing, rateShengxiao, rateWuge, rateYinyun, totalOf, rateName };
})(globalThis.Nova = globalThis.Nova || {});
