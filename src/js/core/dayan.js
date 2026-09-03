// 八十一數理（對應 nova_core/dayan.py）；資料來自 NOVA_TABLES.dayan（data/tables/dayan81.json）。
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

  Nova.dayan = { LUCKY_ACCEPT_DEFAULT, find, isLucky };
})(globalThis.Nova = globalThis.Nova || {});
