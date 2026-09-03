// 字典（對應 nova_core/chars.py）；資料來自 NOVA_CHARS（data/gen/chars.gen.js）。
(function (Nova) {
  'use strict';
  let cache = null;

  // row: [char, py, stroke, wx, lvl, nameable, meaning, radical]
  function parse() {
    const p = globalThis.NOVA_CHARS;
    const map = new Map();
    for (const r of p.rows) {
      map.set(r[0], {
        char: r[0], py: r[1].split('/'), stroke: r[2], wx: r[3], lvl: r[4],
        nameable: r[5] === 1, meaning: r[6], radical: r[7],
        regular: r[4] <= 2, // 常用字（等級 1–2）
      });
    }
    cache = { map, simp2trad: p.simp2trad, version: p.version, generated: p.generated };
    return cache;
  }
  function data() { return cache || parse(); }
  function allChars() { return data().map; }
  function lookup(ch) { return data().map.get(ch) || null; }

  // 簡體姓氏自動轉繁；回傳 {surname, notes}
  function normalizeSurname(surname) {
    const t = data().simp2trad;
    const notes = [];
    let out = '';
    for (const ch of surname.trim()) {
      if (t[ch]) { out += t[ch]; notes.push('「' + ch + '」已轉為繁體「' + t[ch] + '」'); } else out += ch;
    }
    return { surname: out, notes };
  }

  // 候選字依筆畫分桶；桶內依（等級、碼位）排序，與 Python 一致
  function byStroke(maxLevel, nameableOnly) {
    maxLevel = maxLevel == null ? 2 : maxLevel;
    nameableOnly = nameableOnly == null ? true : nameableOnly;
    const buckets = new Map();
    for (const c of data().map.values()) {
      if (c.lvl > maxLevel || (nameableOnly && !c.nameable)) continue;
      if (!buckets.has(c.stroke)) buckets.set(c.stroke, []);
      buckets.get(c.stroke).push(c);
    }
    for (const list of buckets.values()) {
      list.sort((a, b) => a.lvl - b.lvl || a.char.codePointAt(0) - b.char.codePointAt(0));
    }
    return buckets;
  }

  Nova.chars = { allChars, lookup, normalizeSurname, byStroke, data };
})(globalThis.Nova = globalThis.Nova || {});
