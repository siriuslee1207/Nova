// 八十一數理（對應 nova_core/dayan.py）；資料來自 NOVA_TABLES.dayan（data/tables/dayan81.json）。
// 另含「筆畫組合選字」用的 36 吉數（NOVA_TABLES.jishu）與吉數等級（NOVA_TABLES.jishuGrade：大吉／吉／半吉／半凶／凶）。
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
  function isJishu(n) {
    if (!(n > 0)) throw new RangeError('數理必須為正整數: ' + n);
    return jishu().has(((n - 1) % 81) + 1);
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

  Nova.dayan = { LUCKY_ACCEPT_DEFAULT, GRADES, JISHU_GRADES, find, isLucky, jishu, isJishu, grade, cdiGrade };
})(globalThis.Nova = globalThis.Nova || {});
