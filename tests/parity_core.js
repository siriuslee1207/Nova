// JS ↔ Python parity checker. Shared by tests/parity.mjs (node) and tests/parity.html (browser).
// Compares the JS engine's output against tests/fixtures/golden.json produced by tools/gen_fixtures.py.
(function (root) {
  'use strict';

  function deepEqual(a, b) {
    if (a === b) return true;
    if (typeof a !== typeof b || a === null || b === null) return false;
    if (Array.isArray(a)) {
      if (!Array.isArray(b) || a.length !== b.length) return false;
      return a.every((v, i) => deepEqual(v, b[i]));
    }
    if (typeof a === 'object') {
      const ka = Object.keys(a).sort(), kb = Object.keys(b).sort();
      if (!deepEqual(ka, kb)) return false;
      return ka.every((k) => deepEqual(a[k], b[k]));
    }
    return false;
  }

  function fateFromInput(Nova, inp) {
    if (!inp) return null;
    return Nova.bazi.compute(inp.year, inp.month, inp.day, inp.hour, inp.minute, inp.method);
  }

  function fateToExpect(f) {
    return { sizhu: f.sizhu, hour_known: f.hourKnown, day_gan: f.dayGan, day_wx: f.dayWx, zodiac: f.zodiac,
      fen: f.fen, total: f.total, qiangruo: f.qiangruo, method: f.method, yong: f.yong, xi: f.xi, ji: f.ji,
      chou: f.chou, geju: f.geju, note: f.note };
  }

  function run(golden, Nova) {
    const fails = [];
    let pass = 0;
    const check = (section, input, expect, got) => {
      if (deepEqual(expect, got)) pass++;
      else fails.push({ section, input, expect, got });
    };

    for (const t of golden.bazi) check('bazi', t.input, t.expect, fateToExpect(fateFromInput(Nova, t.input)));

    for (const t of golden.rating) {
      const c1 = Nova.chars.lookup(t.input.c1), c2 = Nova.chars.lookup(t.input.c2);
      const r = Nova.rating.rateName(t.input.l1, t.input.l2, c1, c2, fateFromInput(Nova, t.input.fate));
      check('rating', t.input, t.expect, { wenhua: r.wenhua, wuxing: r.wuxing, shengxiao: r.shengxiao, wuge: r.wuge,
        yinyun: r.yinyun, total: r.total, grade: r.grade, ge: r.ge, sancai_key: r.sancaiKey });
    }

    for (const t of golden.combos) {
      const cs = Nova.generator.luckyCombos(t.input.l1, t.input.l2, Object.assign(Nova.generator.defaultOptions(),
        { strictness: t.input.strictness, excludeFemaleCaution: t.input.exclude_female_caution }));
      check('combos', t.input, t.expect, { count: cs.length, pairs: cs.map((c) => [c.f1, c.f2, c.wugeScore, c.sancaiKey]) });
    }

    for (const t of golden.generate) {
      const o = t.input.options;
      const res = Nova.generator.generate(t.input.l1, t.input.l2, fateFromInput(Nova, t.input.fate), {
        strictness: o.strictness, excludeFemaleCaution: o.exclude_female_caution, maxLevel: o.max_level,
        avoidChars: new Set(o.avoid_chars), requireChars: new Set(o.require_chars), fixedFirst: o.fixed_first,
        fixedSecond: o.fixed_second, topN: o.top_n, perFirstChar: o.per_first_char,
      });
      check('generate', t.input, t.expect, res.map((c) => ({ name: c.c1.char + c.c2.char, total: c.total, grade: c.grade,
        scores: c.scores, f1: c.combo.f1, f2: c.combo.f2 })));
    }
    for (const t of golden.prompts || []) {
      const inp = t.input, o = inp.options;
      const fate = fateFromInput(Nova, inp.fate);
      const opt = Object.assign(Nova.generator.defaultOptions(), { strictness: o.strictness, excludeFemaleCaution: o.exclude_female_caution, maxLevel: o.max_level });
      const req = Nova.advisor.buildRecommend({ surname: inp.surname, l1: inp.l1, l2: inp.l2, gender: inp.gender, fate,
        combos: Nova.generator.luckyCombos(inp.l1, inp.l2, opt), buckets: Nova.chars.byStroke(o.max_level), n: 8, preferences: inp.preferences });
      const c1 = Nova.chars.lookup(inp.name[0]), c2 = Nova.chars.lookup(inp.name[1]);
      const ex = Nova.advisor.buildExplain({ surname: inp.surname, c1, c2, rating: Nova.rating.rateName(inp.l1, inp.l2, c1, c2, fate), fate });
      check('prompts', { surname: inp.surname, name: inp.name }, t.expect, { system: req.system, recommend_user: req.user,
        explain_user: ex.user, allowed_strokes: [...req.allowed.keys()].sort((a, b) => a - b) });
    }
    return { pass, fails, total: pass + fails.length };
  }

  root.NovaParity = { run, deepEqual };
})(globalThis);
