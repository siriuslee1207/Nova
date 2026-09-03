// 五格剖象（對應 nova_core/wuge.py）。所有 core 模組寫入 globalThis.Nova，classic script 可用。
(function (Nova) {
  'use strict';
  const MAX_STROKE = 30;
  const ELEMENT_BY_DIGIT = '水木木火火土土金金水'; // 格數末位 → 五行

  // l1,l2 姓氏筆畫（單姓 l2=0）；f1,f2 名字筆畫（單字名 f2=0）。總格取 1..81 循環，其餘不循環。
  function calcWuge(l1, l2, f1, f2) {
    const tian = l2 === 0 ? l1 + 1 : l1 + l2;
    const ren = (l2 === 0 ? l1 : l2) + f1;
    const di = f2 === 0 ? f1 + 1 : f1 + f2;
    const wai = (l2 === 0 ? 1 : l1) + (f2 === 0 ? 1 : f2);
    const zong = ((l1 + l2 + f1 + f2 - 1) % 81) + 1;
    return { tian, ren, di, wai, zong };
  }

  function elementOf(n) { return ELEMENT_BY_DIGIT[n % 10]; }
  function yinyangOf(n) { return n % 2 === 0 ? '陰' : '陽'; }

  Nova.wuge = { MAX_STROKE, ELEMENT_BY_DIGIT, calcWuge, elementOf, yinyangOf };
})(globalThis.Nova = globalThis.Nova || {});
