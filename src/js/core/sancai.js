// 三才配置吉凶（對應 nova_core/sancai.py）；資料來自 NOVA_TABLES.sancai / sancaiText。
(function (Nova) {
  'use strict';
  const STRICTNESS_MIN_LEVEL = { strict: 6, moderate: 5, relaxed: 4 };

  const combos = () => globalThis.NOVA_TABLES.sancai.combos;
  const text = () => globalThis.NOVA_TABLES.sancaiText;

  function keyOf(tian, ren, di) {
    const e = Nova.wuge.elementOf;
    return e(tian) + e(ren) + e(di);
  }
  function verdict(key) { return combos()[key].verdict; }
  function level(key) { return combos()[key].level; }
  function passes(key, strictness) { return level(key) >= STRICTNESS_MIN_LEVEL[strictness || 'moderate']; }
  function detail(key) { return text().detail[key] || ('三才' + key + '配置' + verdict(key) + '。'); }
  function jichu(renEl, diEl) { return text().jichu[renEl + diEl] || ''; }       // 基礎運（人×地）
  function chenggong(renEl, tianEl) { return text().chenggong[renEl + tianEl] || ''; } // 成功運（人×天）
  function renji(renEl, waiEl) { return text().renji[renEl + waiEl] || ''; }       // 人際（人×外）

  Nova.sancai = { STRICTNESS_MIN_LEVEL, keyOf, verdict, level, passes, detail, jichu, chenggong, renji };
})(globalThis.Nova = globalThis.Nova || {});
