// 八十一數理（對應 nova_core/dayan.py）；資料來自 NOVA_TABLES.dayan（data/tables/dayan81.json）。
// 另含「筆畫組合選字」用的 36 吉數（NOVA_TABLES.jishu）與吉數等級（NOVA_TABLES.jishuGrade：大吉／吉／半吉／半凶／凶），
// 以及可切換的吉數表（JISHU_TABLES：36／fate 吉／謝達輝 吉／自選）。
(function (Nova) {
  'use strict';
  const LUCKY_ACCEPT_DEFAULT = new Set(['吉', '半吉']);

  function table() { return globalThis.NOVA_TABLES.dayan; }

  // n 為任一正整數；超過 81 循環。回傳 {number, lucky, max_luck, female_caution, title, comment}
  function find(n) {
    if (!(n > 0)) throw new RangeError('數理必須為正整數: ' + n);
    return table()[(n - 1) % 81];
  }

  function isLucky(d, accept) { return (accept || LUCKY_ACCEPT_DEFAULT).has(d.lucky); }

  // 36 吉數（NOVA_TABLES.jishu，使用者指定表）；「筆畫組合選字」以此判定五格，與 lucky 分級無關
  let jishuSet = null;
  function jishu() { return jishuSet || (jishuSet = new Set(globalThis.NOVA_TABLES.jishu.numbers)); }
  // jishuSet 不給＝36 吉數，給了（Set，1..81）就以它判定
  function isJishu(n, jishuSet) {
    if (!(n > 0)) throw new RangeError('數理必須為正整數: ' + n);
    return (jishuSet || jishu()).has(((n - 1) % 81) + 1);
  }

  // 吉數表（對應 dayan.py）：「筆畫組合選字」的吉數可從既有的幾張表擇一，或自選一組數字（custom）
  const JISHU_TABLES = ['36', 'fate', 'cdi', 'custom'];
  const JISHU_TABLE_LABEL = { 36: '熊崎氏 36 吉數', fate: 'fate 81 數理「吉」', cdi: '謝達輝 81 劃表「吉」', custom: '自選' };
  const ALL81 = Array.from({ length: 81 }, (_, i) => i + 1);
  const tableCache = new Map();
  // 具名吉數表 → Set（共用快取，呼叫端不可改動它）：36＝jishu36；fate＝dayan81 的「吉」；cdi＝謝達輝 81 劃表的「吉」
  function jishuTable(name) {
    if (tableCache.has(name)) return tableCache.get(name);
    let s;
    if (name === '36') s = new Set(jishu());
    else if (name === 'fate') s = new Set(ALL81.filter((n) => find(n).lucky === '吉'));
    else if (name === 'cdi') s = new Set(ALL81.filter((n) => cdiGrade(n) === '吉'));
    else throw new RangeError('未知的吉數表: ' + name + '（可選 ' + JISHU_TABLES.join(',') + '）');
    tableCache.set(name, s);
    return s;
  }
  // 表名＋自選數字 → 實際判定用的 Set；custom 只在 table === 'custom' 時採用，超過 81 循環、0 以下丟掉
  function jishuOf(table, custom) {
    if (table === 'custom') return new Set([...(custom || [])].map(Number).filter((n) => n > 0).map((n) => ((n - 1) % 81) + 1));
    return jishuTable(table == null ? '36' : String(table));
  }

  // 吉數等級（NOVA_TABLES.jishuGrade，data/tables/jishu_grade.json）：大吉＋吉 恰為 36 吉數
  const GRADES = ['大吉', '吉', '半吉', '半凶', '凶'];
  const JISHU_GRADES = new Set(['大吉', '吉']);

  function grade(n) {
    if (!(n > 0)) throw new RangeError('數理必須為正整數: ' + n);
    return globalThis.NOVA_TABLES.jishuGrade.grade[(n - 1) % 81];
  }

  // 謝達輝「81 劃吉凶分類表」原級（吉／吉帶凶／凶帶吉／凶），僅供對照顯示
  function cdiGrade(n) {
    if (!(n > 0)) throw new RangeError('數理必須為正整數: ' + n);
    return globalThis.NOVA_TABLES.jishuGrade.cdi[(n - 1) % 81];
  }

  Nova.dayan = { LUCKY_ACCEPT_DEFAULT, GRADES, JISHU_GRADES, JISHU_TABLES, JISHU_TABLE_LABEL, find, isLucky, jishu, isJishu, jishuTable, jishuOf, grade, cdiGrade };
})(globalThis.Nova = globalThis.Nova || {});
