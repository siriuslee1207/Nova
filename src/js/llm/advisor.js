// AI 顧問：組提示（推薦用字 / 命名解說）與驗證模型輸出（對應 nova_core/llm/advisor.py）。
// 推薦用字只能從已通過五格/三才的筆畫組合與候選字池中選 → LLM 永遠不會破壞五格分數。
(function (Nova) {
  'use strict';
  const PICKS_SCHEMA = {
    type: 'object',
    properties: {
      picks: {
        type: 'array',
        items: {
          type: 'object',
          properties: { first: { type: 'string' }, second: { type: 'string' }, reason: { type: 'string' } },
          required: ['first', 'second', 'reason'],
        },
      },
    },
    required: ['picks'],
  };
  const MAX_COMBOS = 12, MAX_PER_STROKE = 40;

  function baziSummary(fate) {
    if (!fate) return '無（未提供出生時間）';
    const sz = fate.sizhu.map((gz, i) => gz || (i === 3 ? '時辰不詳' : '')).filter(Boolean).join(' ');
    return `${sz}；日主 ${fate.dayGan}${fate.dayWx}（${fate.qiangruo}）；五行分佈 ${Nova.bazi.ELEMENTS.map((e) => e + fate.fen[e]).join(' ')}` +
      `；${fate.method === 'geju' ? '格局法' : '平衡法'}${fate.geju ? '（' + fate.geju + '）' : ''}${fate.note ? '，' + fate.note : ''}`;
  }

  // combos: luckyCombos 輸出（依五格分降冪）；buckets: chars.byStroke()
  function buildRecommend({ surname, l1, l2, gender, fate, combos, buckets, n, preferences }) {
    const top = combos.slice().sort((a, b) => b.wugeScore - a.wugeScore).slice(0, MAX_COMBOS);
    const strokes = [...new Set(top.flatMap((c) => [c.f1, c.f2]))].sort((a, b) => a - b);
    const allowed = new Map();
    const poolLines = [];
    for (const s of strokes) {
      const list = (buckets.get(s) || []).slice(0, MAX_PER_STROKE);
      allowed.set(s, new Set(list.map((c) => c.char)));
      if (list.length) poolLines.push(`${s}畫：` + list.map((c) => `${c.char}[${c.py[0]},${c.wx}]`).join(' '));
    }
    const comboSet = new Set(top.map((c) => c.f1 + ',' + c.f2));
    const user = Nova.llm.render('recommend_chars', {
      n: n || 8, surname, surname_strokes: l2 ? `${l1}+${l2}` : String(l1), gender: gender === 'girl' ? '女' : '男',
      bazi_summary: baziSummary(fate),
      yong: fate ? fate.yong : '無', xi: fate ? fate.xi : '無', ji: fate ? fate.ji : '無', chou: fate ? fate.chou : '無',
      zodiac: fate ? fate.zodiac : '無',
      combos: top.map((c) => `${c.f1}+${c.f2}：${c.wugeScore}`).join('；'),
      pools: poolLines.join('\n'),
      preferences: preferences || '無特別偏好',
    });
    return { system: Nova.llm.render('system', {}), user, allowed, comboSet, topCombos: top };
  }

  // 驗證：字在對應筆畫的字池內，且 (f1,f2) 是合格組合
  function validatePicks(picks, req) {
    const ok = [], rejected = [];
    const seen = new Set();
    for (const p of Array.isArray(picks) ? picks : []) {
      const first = String(p.first || '').trim(), second = String(p.second || '').trim();
      const c1 = Nova.chars.lookup(first), c2 = Nova.chars.lookup(second);
      const why = !c1 || !c2 ? '字典查無此字'
        : !(req.allowed.get(c1.stroke) || new Set()).has(first) || !(req.allowed.get(c2.stroke) || new Set()).has(second) ? '不在候選字池'
          : !req.comboSet.has(c1.stroke + ',' + c2.stroke) ? '筆畫組合不合格'
            : seen.has(first + second) ? '重複' : '';
      if (why) rejected.push({ first, second, reason: p.reason, why });
      else { seen.add(first + second); ok.push({ c1, c2, reason: String(p.reason || '') }); }
    }
    return { ok, rejected };
  }

  function buildExplain({ surname, c1, c2, rating, fate }) {
    const g = rating.ge;
    const D = Nova.dayan;
    const user = Nova.llm.render('explain_name', {
      fullname: surname + c1.char + c2.char, pinyin: `${c1.py[0]} ${c2.py[0]}`,
      char_info: [c1, c2].map((c) => `- ${c.char}：${c.py.join('/')}，${c.stroke}畫，五行${c.wx}，釋義「${c.meaning || '無'}」`).join('\n'),
      total: rating.total, grade: rating.grade, wenhua: rating.wenhua, wuxing: rating.wuxing, shengxiao: rating.shengxiao,
      wuge: rating.wuge, yinyun: rating.yinyun,
      wuge_detail: g ? [['天格', g.tian], ['人格', g.ren], ['地格', g.di], ['外格', g.wai], ['總格', g.zong]]
        .map(([n, v]) => `${n}${v}（${D.find(v).title}・${D.find(v).lucky}）`).join('，') : '無',
      sancai: rating.sancaiKey ? `${rating.sancaiKey} ${Nova.sancai.verdict(rating.sancaiKey)}：${Nova.sancai.detail(rating.sancaiKey)}` : '無',
      bazi_summary: baziSummary(fate),
    });
    return { system: Nova.llm.render('system', {}), user };
  }

  Nova.advisor = { PICKS_SCHEMA, MAX_COMBOS, MAX_PER_STROKE, baziSummary, buildRecommend, validatePicks, buildExplain };
})(globalThis.Nova = globalThis.Nova || {});
