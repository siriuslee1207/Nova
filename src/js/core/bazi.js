// 八字與喜用神（對應 nova_core/bazi.py）。四柱由 lunar-javascript（全域 Solar）計算；五行分數以十分之一整數累加。
// 用、喜、忌、仇四神必互不相同：平衡法依致強／致弱之因取用（fuyi_rules），格局法依八正格順用／逆用（geju_rules），
// 規則表與說明文字（why）都在 bazi_tables.json，與 Python 共用。
(function (Nova) {
  'use strict';
  const ZHI = '子丑寅卯辰巳午未申酉戌亥';
  const ZODIAC = '鼠牛虎兔龍蛇馬羊猴雞狗豬'; // 依年柱地支（立春為界）
  const ELEMENTS = ['木', '火', '土', '金', '水'];
  const METHODS = ['balance', 'geju'];
  const REL_KEYS = ['yong', 'xi', 'ji', 'chou'];

  const bt = () => globalThis.NOVA_TABLES.bazi;

  function fourPillars(year, month, day, hour, minute) {
    if (typeof Solar === 'undefined') throw new Error('lunar.js 未載入');
    const ec = Solar.fromYmdHms(year, month, day, hour, minute, 0).getLunar().getEightChar();
    ec.setSect(1); // 晚子時（23:00 起）日柱算次日；預設 sect=2 會算當天
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

  // 日主五行 → 各十神的五行：self 比劫、sheng_wo 印、ke_wo 官殺、wo_sheng 食傷、wo_ke 財
  function relations(dayWx) {
    const b = bt();
    return { self: dayWx, sheng_wo: b.sheng_wo[dayWx], ke_wo: b.ke_wo[dayWx], wo_sheng: b.sheng[dayWx], wo_ke: b.ke[dayWx] };
  }

  // 規則表的一列（十神關係名）→ [用, 喜, 忌, 仇] 五行
  function applyRule(rule, dayWx) {
    const rel = relations(dayWx);
    return REL_KEYS.map((k) => rel[rule[k]]);
  }

  // 平衡法（扶抑）→ [用, 喜, 忌, 仇, 說明]
  // 身強：忌＝印、比劫中較旺者（致強之因）；身弱：忌＝官殺、財、食傷中最旺者（致弱之因，同分依此序）
  function balance(tenths, dayWx, qiangruo) {
    const rel = relations(dayWx);
    let cause;
    if (qiangruo === '強') {
      cause = tenths[rel.sheng_wo] > tenths[rel.self] ? '印旺' : '比劫旺';
    } else {
      const drains = [['官殺旺', rel.ke_wo], ['財旺', rel.wo_ke], ['食傷旺', rel.wo_sheng]];
      let best = drains[0];
      for (const d of drains) if (tenths[d[1]] > tenths[best[1]]) best = d; // 同分取序中第一個
      cause = best[0];
    }
    const rule = bt().fuyi_rules[cause];
    return [...applyRule(rule, dayWx), rule.why];
  }

  // 格局法 → {name, elems:[用,喜,忌,仇] | null, shishen, why}
  function geju(pillars, dayGan) {
    const b = bt();
    const mainQi = b.hidden_stems[pillars[1][1]][0][0];
    const ss = b.shishen[dayGan][mainQi];
    const name = b.shishen_to_geju[ss];
    if (!name) return { name: null, elems: null, shishen: ss, why: '' };
    const rule = b.geju_rules[name];
    return { name, elems: applyRule(rule, b.tiangan_wuxing[dayGan]), shishen: ss, why: rule.why };
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
    let [yong, xi, ji, chou, note] = balance(tenths, dayWx, qiangruo);
    const g = geju(pillars, dayGan);
    if (method === 'geju') {
      if (g.elems) { [yong, xi, ji, chou] = g.elems; note = g.why; }
      else note = '月令主氣十神為' + g.shishen + '，不在八正格內，改用平衡法：' + note;
    }
    const hidden = pillars.map((gz) => (gz ? b.hidden_stems[gz[1]].map((x) => x[0]) : []));
    return { sizhu: pillars, hourKnown, dayGan, dayWx, zodiac, fen, total: totalT / 10, qiangruo,
      method, yong, xi, ji, chou, geju: g.name, note, hidden };
  }

  Nova.bazi = { ZHI, ZODIAC, ELEMENTS, METHODS, REL_KEYS, fourPillars, wuxingTenths, judgeStrength, relations, applyRule, balance, geju, compute };
})(globalThis.Nova = globalThis.Nova || {});
