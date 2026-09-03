// 八字與喜用神（對應 nova_core/bazi.py）。四柱由 lunar-javascript（全域 Solar）計算；五行分數以十分之一整數累加。
(function (Nova) {
  'use strict';
  const ZHI = '子丑寅卯辰巳午未申酉戌亥';
  const ZODIAC = '鼠牛虎兔龍蛇馬羊猴雞狗豬'; // 依年柱地支（立春為界）
  const ELEMENTS = ['木', '火', '土', '金', '水'];
  const METHODS = ['balance', 'geju'];

  const bt = () => globalThis.NOVA_TABLES.bazi;

  function fourPillars(year, month, day, hour, minute) {
    if (typeof Solar === 'undefined') throw new Error('lunar.js 未載入');
    const ec = Solar.fromYmdHms(year, month, day, hour, minute, 0).getLunar().getEightChar();
    return [ec.getYear(), ec.getMonth(), ec.getDay(), ec.getTime()];
  }

  // 五行分數 ×10：每柱天干 +10，藏干依權重（0.6 → 6）
  function wuxingTenths(pillars) {
    const t = { 木: 0, 火: 0, 土: 0, 金: 0, 水: 0 }, b = bt();
    for (const gz of pillars) {
      const gan = gz[0], zhi = gz[1];
      t[b.tiangan_wuxing[gan]] += 10;
      for (const [stem, w] of b.hidden_stems[zhi]) t[b.tiangan_wuxing[stem]] += Math.round(w * 10);
    }
    return t;
  }

  function judgeStrength(tenths, dayWx) {
    let total = 0;
    for (const e of ELEMENTS) total += tenths[e];
    const mine = tenths[dayWx] + tenths[bt().sheng_wo[dayWx]];
    return mine * 2 > total ? '強' : '弱';
  }

  // 平衡法 → [用, 喜, 忌, 仇]
  function balance(tenths, dayWx, qiangruo) {
    const b = bt();
    let yong, xi, ji, chou;
    if (qiangruo === '強') { yong = b.ke_wo[dayWx]; xi = b.sheng[dayWx]; ji = dayWx; chou = b.sheng_wo[dayWx]; }
    else { yong = dayWx; xi = b.sheng_wo[dayWx]; ji = b.ke_wo[dayWx]; chou = b.ke[dayWx]; }
    let weakest = ELEMENTS[0];
    for (const e of ELEMENTS) if (tenths[e] < tenths[weakest]) weakest = e; // 序中第一個最小者
    if (qiangruo === '弱' && weakest !== dayWx) yong = weakest;
    const xian = ELEMENTS.find((e) => tenths[e] === 0) || '';
    if (xian && qiangruo === '強') chou = xian;
    return [yong, xi, ji, chou];
  }

  // 格局法 → {name, elems:[用,喜,忌,仇] | null, shishen}
  function geju(pillars, dayGan) {
    const b = bt();
    const mainQi = b.hidden_stems[pillars[1][1]][0][0];
    const ss = b.shishen[dayGan][mainQi];
    const name = b.shishen_to_geju[ss];
    if (!name) return { name: null, elems: null, shishen: ss };
    const dayWx = b.tiangan_wuxing[dayGan];
    const rel = { self: dayWx, sheng_wo: b.sheng_wo[dayWx], ke_wo: b.ke_wo[dayWx], wo_sheng: b.sheng[dayWx], wo_ke: b.ke[dayWx] };
    const rule = b.geju_rules[name];
    return { name, elems: ['yong', 'xi', 'ji', 'chou'].map((k) => rel[rule[k]]), shishen: ss };
  }

  // hour 為 null 表示時辰不詳（只以三柱計，時柱留空）
  function compute(year, month, day, hour, minute, method) {
    method = method || 'balance';
    if (!METHODS.includes(method)) throw new RangeError('method 必須為 balance | geju');
    const hourKnown = hour !== null && hour !== undefined;
    const pillars = fourPillars(year, month, day, hourKnown ? hour : 12, hourKnown ? (minute || 0) : 0);
    if (!hourKnown) pillars[3] = '';
    const used = hourKnown ? pillars : pillars.slice(0, 3);
    const b = bt();
    const dayGan = pillars[2][0];
    const dayWx = b.tiangan_wuxing[dayGan];
    const tenths = wuxingTenths(used);
    const fen = {};
    let totalT = 0;
    for (const e of ELEMENTS) { fen[e] = tenths[e] / 10; totalT += tenths[e]; }
    const qiangruo = judgeStrength(tenths, dayWx);
    const zodiac = ZODIAC[ZHI.indexOf(pillars[0][1])];
    let [yong, xi, ji, chou] = balance(tenths, dayWx, qiangruo);
    const g = geju(pillars, dayGan);
    let note = '';
    if (method === 'geju') {
      if (g.elems) [yong, xi, ji, chou] = g.elems;
      else note = '月令主氣十神為' + g.shishen + '，不在八正格內，改用平衡法';
    }
    const hidden = pillars.map((gz) => (gz ? b.hidden_stems[gz[1]].map((x) => x[0]) : []));
    return { sizhu: pillars, hourKnown, dayGan, dayWx, zodiac, fen, total: totalT / 10, qiangruo,
      method, yong, xi, ji, chou, geju: g.name, note, hidden };
  }

  Nova.bazi = { ZHI, ZODIAC, ELEMENTS, METHODS, fourPillars, wuxingTenths, judgeStrength, balance, geju, compute };
})(globalThis.Nova = globalThis.Nova || {});
