// 筆畫組合選字（對應 nova_core/combos.py）：列出姓氏筆畫下所有合格的名字筆畫組合 (f1, f2)。
// 篩選鏈與 generator.luckyCombos 獨立：三才等級（謝達輝表 NOVA_TABLES.sancaiCdi）→ 勾選的格皆為 36 吉數（NOVA_TABLES.jishu，
// 含天格）→（可選）排除女性不宜總格。迭代 f1 升冪、f2 升冪，與 Python 逐列相同。
(function (Nova) {
  'use strict';
  const GRIDS = ['tian', 'ren', 'di', 'wai', 'zong'];
  const DEFAULT_GRADES = ['最吉', '吉'];

  function defaultFilter() {
    return { sancaiGrades: new Set(DEFAULT_GRADES), grids: GRIDS.slice(), excludeFemaleCaution: false,
      minStroke: 1, maxStroke: Nova.wuge.MAX_STROKE };
  }

  // filt 可只給部分欄位（陣列也收）；缺的補預設，避免部分選項造成迴圈不跑（見 generator.luckyCombos 的註解）
  function normFilter(filt) {
    const o = defaultFilter();
    for (const k in (filt || {})) if (filt[k] !== undefined) o[k] = filt[k];
    if (!(o.sancaiGrades instanceof Set)) o.sancaiGrades = new Set(o.sancaiGrades);
    o.grids = GRIDS.filter((k) => [...o.grids].includes(k));
    return o;
  }

  // 天格只看姓氏筆畫（單姓 l1+1、複姓 l1+l2）
  function tianOf(l1, l2) { return Nova.wuge.calcWuge(l1, l2, 1, 1).tian; }
  function tianOk(l1, l2) { return Nova.dayan.isJishu(tianOf(l1, l2)); }

  // 不過濾，直接描述一組筆畫組合
  function comboRow(l1, l2, f1, f2) {
    const S = Nova.sancai, D = Nova.dayan;
    const g = Nova.wuge.calcWuge(l1, l2, f1, f2);
    const key = S.keyOf(g.tian, g.ren, g.di);
    const jishu = {};
    for (const k of GRIDS) jishu[k] = D.isJishu(g[k]);
    return { f1, f2, ge: g, sancaiKey: key, cdiGrade: S.cdiGrade(key), cdiNo: S.cdiNo(key), fateVerdict: S.verdict(key),
      jishu, wugeScore: Nova.rating.rateWuge(l1, l2, f1, f2)[0] };
  }

  function enumerateCombos(l1, l2, filt) {
    const o = normFilter(filt);
    if (o.grids.includes('tian') && !tianOk(l1, l2)) return [];
    const S = Nova.sancai, D = Nova.dayan, out = [];
    for (let f1 = o.minStroke; f1 <= o.maxStroke; f1++) {
      for (let f2 = o.minStroke; f2 <= o.maxStroke; f2++) {
        const g = Nova.wuge.calcWuge(l1, l2, f1, f2);
        const key = S.keyOf(g.tian, g.ren, g.di);
        const grade = S.cdiGrade(key);
        if (!o.sancaiGrades.has(grade)) continue;
        const jishu = {};
        for (const k of GRIDS) jishu[k] = D.isJishu(g[k]);
        if (!o.grids.every((k) => jishu[k])) continue;
        if (o.excludeFemaleCaution && D.find(g.zong).female_caution) continue;
        out.push({ f1, f2, ge: g, sancaiKey: key, cdiGrade: grade, cdiNo: S.cdiNo(key), fateVerdict: S.verdict(key),
          jishu, wugeScore: Nova.rating.rateWuge(l1, l2, f1, f2)[0] });
      }
    }
    return out;
  }

  // 依第一字筆畫分組（f1 升冪，沿用 rows 順序）→ [[f1, rows], …]
  function groupByFirst(rows) {
    const groups = [];
    for (const r of rows) {
      if (groups.length && groups[groups.length - 1][0] === r.f1) groups[groups.length - 1][1].push(r);
      else groups.push([r.f1, [r]]);
    }
    return groups;
  }

  // byStroke 會全掃 13k 字，依字集等級快取一次
  const bucketCache = new Map();
  function buckets(maxLevel) {
    maxLevel = maxLevel == null ? 2 : maxLevel;
    if (!bucketCache.has(maxLevel)) bucketCache.set(maxLevel, Nova.chars.byStroke(maxLevel, true));
    return bucketCache.get(maxLevel);
  }

  // 兩個筆畫各自的候選字（byStroke 順序），去掉排除字 → [list1, list2]
  function charLists(f1, f2, maxLevel, avoid) {
    const b = buckets(maxLevel);
    const pick = (s) => (b.get(s) || []).filter((c) => !avoid || !avoid.has(c.char));
    return [pick(f1), pick(f2)];
  }

  Nova.combos = { GRIDS, DEFAULT_GRADES, defaultFilter, normFilter, tianOf, tianOk, comboRow, enumerateCombos, groupByFirst, buckets, charLists };
})(globalThis.Nova = globalThis.Nova || {});
