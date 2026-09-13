// UI：表單 → 姓氏筆畫 → 八字 → 產生/評分 → 渲染；AI 顧問（推薦用字、解說）。純 vanilla，classic script，file:// 可用。
(function () {
  'use strict';
  const $ = (s) => document.querySelector(s);
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const wxTag = (wx) => wx ? `<span class="wx wx-${wx}">${wx}</span>` : '';
  const DIMS = [['文化', 'wenhua'], ['五行', 'wuxing'], ['生肖', 'shengxiao'], ['五格', 'wuge'], ['音韻', 'yinyun']];

  const state = { fate: null, results: [], l1: 0, l2: 0, surname: '', runId: 0, weights: null };
  // 卡片註冊表：data-id → {cand, fate, l1, l2, surname}，供事件委派使用
  const registry = new Map();
  let nextId = 1;

  // ---------------------------------------------------------------- 姓氏
  function readSurname() {
    const raw = $('#surname').value.trim();
    if (!raw) return null;
    const { surname, notes } = Nova.chars.normalizeSurname(raw);
    const chars = [...surname];
    if (chars.length > 2) { showSurnameInfo([], ['姓氏須為 1–2 字']); return null; }
    const info = chars.map((ch) => {
      const c = Nova.chars.lookup(ch);
      return { ch, stroke: c ? c.stroke : null, wx: c ? c.wx : '' };
    });
    showSurnameInfo(info, notes);
    return { surname, info };
  }

  function showSurnameInfo(info, notes) {
    const box = $('#surname-info');
    const prev = [...box.querySelectorAll('input[data-i]')].map((i) => i.value);
    box.innerHTML = info.map((x, i) => x.stroke
      ? `<span class="chip">${esc(x.ch)} ${wxTag(x.wx)}<input type="number" min="1" max="60" value="${x.stroke}" data-i="${i}" aria-label="${esc(x.ch)} 筆畫" title="康熙筆畫，可依流派調整"> 畫</span>`
      : `<span class="chip warn">${esc(x.ch)} 查無筆畫，請輸入 <input type="number" min="1" max="60" value="${prev[i] || ''}" data-i="${i}" aria-label="${esc(x.ch)} 筆畫"> 畫</span>`).join('')
      + notes.map((n) => `<span class="chip">${esc(n)}</span>`).join('');
  }

  function surnameStrokes(info) {
    const inputs = [...$('#surname-info').querySelectorAll('input[data-i]')];
    const strokes = info.map((x, i) => Number(inputs[i] && inputs[i].value) || x.stroke || 0);
    if (strokes.some((s) => !s)) throw new Error('請輸入姓氏筆畫');
    return [strokes[0], strokes[1] || 0];
  }

  // ---------------------------------------------------------------- 八字
  function readFate() {
    const d = $('#born-date').value;
    if (!d) return null;
    const [y, m, day] = d.split('-').map(Number);
    const unknown = $('#hour-unknown').checked;
    const t = $('#born-time').value;
    let hour = null, minute = 0;
    if (!unknown && t) { const [hh, mm] = t.split(':').map(Number); hour = hh; minute = mm; }
    return Nova.bazi.compute(y, m, day, hour, minute, $('#method').value);
  }

  function renderBazi(f) {
    const box = $('#bazi');
    if (!f) { box.hidden = true; box.innerHTML = ''; return; }
    const names = ['年柱', '月柱', '日柱', '時柱'];
    box.hidden = false;
    box.innerHTML = `
      <div><b>八字</b> <span class="dim">日主 ${esc(f.dayGan)}${wxTag(f.dayWx)}（${esc(f.qiangruo)}）・生肖 ${esc(f.zodiac)}・${f.method === 'geju' ? '格局法' : '平衡法'}${f.geju ? '・' + esc(f.geju) : ''}</span></div>
      <div class="pillars">${f.sizhu.map((gz, i) => `<div class="pillar"><small>${names[i]}</small><div class="gz">${gz ? esc(gz) : '—'}</div><small>${f.hidden[i].length ? '藏 ' + esc(f.hidden[i].join('')) : (i === 3 ? '時辰不詳' : '')}</small></div>`).join('')}</div>
      <div class="fen">${Nova.bazi.ELEMENTS.map((e) => `<span>${wxTag(e)}<b>${f.fen[e]}</b></span>`).join('')}<span class="dim">合計 ${f.total}</span></div>
      <div class="fen"><span>用神 ${wxTag(f.yong)}</span><span>喜神 ${wxTag(f.xi)}</span><span>忌神 ${wxTag(f.ji)}</span><span>仇神 ${wxTag(f.chou)}</span>${f.note ? `<span class="dim">${esc(f.note)}</span>` : ''}</div>`;
  }

  // ---------------------------------------------------------------- 評分權重
  // 欄位裡放「未正規化」的五個數字（只看比例）；正規化成總和 1 這件事只在 generator／rateName 內做一次，
  // 兩邊都從同一份原始權重出發，才不會因為重複正規化差一個位數。權重記在這個瀏覽器。
  const WEIGHTS_KEY = 'nova.weights.v1';
  const weightInputs = () => [...document.querySelectorAll('#weights input[data-w]')];
  const sameWeights = (a, b) => a.every((v, i) => Math.abs(v - b[i]) < 1e-9);

  function readWeights() {
    return weightInputs().map((el) => { const v = Number(el.value); return Number.isFinite(v) && v > 0 ? v : 0; });
  }

  function renderWeightBox() {
    const r = Nova.rating;
    $('#weight-preset').innerHTML = Object.keys(r.PRESETS).map((k) =>
      `<option value="${k}" title="${esc(r.weightsText(r.normalizeWeights(r.PRESETS[k])))}">${esc(r.PRESET_NAMES[k])}</option>`).join('')
      + '<option value="custom">自訂…</option>';
    $('#weights').innerHTML = r.DIMS.map((k) =>
      `<label class="wcell">${esc(r.DIM_NAMES[k])}<input type="number" data-w="${k}" min="0" max="100" step="0.05"><small></small></label>`).join('');
  }

  function applyWeights(vals) {
    weightInputs().forEach((el, i) => { el.value = String(vals[i]); });
    syncWeights();
  }

  function syncWeights() {
    const r = Nova.rating, raw = readWeights(), n = r.normalizeWeights(raw);
    weightInputs().forEach((el, i) => {
      el.parentNode.querySelector('small').textContent = r.round1(n[i] * 100) + '%';
      el.parentNode.classList.toggle('off', !(raw[i] > 0));
    });
    const hit = Object.keys(r.PRESETS).find((k) => sameWeights(n, r.normalizeWeights(r.PRESETS[k])));
    $('#weight-preset').value = hit || 'custom';
    $('#weights-summary').textContent = hit ? r.PRESET_NAMES[hit] : r.weightsText(n);
    try { localStorage.setItem(WEIGHTS_KEY, JSON.stringify(raw)); } catch (_) { /* ignore */ }
    return n;
  }

  function initWeights() {
    renderWeightBox();
    let saved = null;
    try { saved = JSON.parse(localStorage.getItem(WEIGHTS_KEY)); } catch (_) { /* ignore */ }
    applyWeights(Array.isArray(saved) && saved.length === 5 ? saved : Nova.rating.DEFAULT_WEIGHTS);
    $('#weights').addEventListener('input', syncWeights);
    $('#weight-preset').addEventListener('change', () => {
      const v = $('#weight-preset').value;
      if (Object.prototype.hasOwnProperty.call(Nova.rating.PRESETS, v)) applyWeights(Nova.rating.PRESETS[v]);
    });
    $('#weight-reset').addEventListener('click', () => applyWeights(Nova.rating.DEFAULT_WEIGHTS));
  }

  // ---------------------------------------------------------------- 產生
  function readOptions() {
    return {
      strictness: $('#strictness').value,
      excludeFemaleCaution: $('#female-caution').checked,
      maxLevel: Number($('#level').value),
      avoidChars: new Set([...$('#avoid').value.replace(/\s/g, '')]),
      requireChars: new Set([...$('#require').value.replace(/\s/g, '')]),
      fixedFirst: $('#fixed-first').value.trim() || null,
      fixedSecond: $('#fixed-second').value.trim() || null,
      topN: Math.max(1, Math.min(200, Number($('#topn').value) || 20)),
      perFirstChar: Math.max(0, Number($('#perfirst').value) || 0),
      weights: readWeights(),
      gender: $('#gender').value,
    };
  }

  function setBusy(busy, msg) {
    $('#go').disabled = busy;
    $('#status').textContent = msg || '';
  }

  function onGenerate(ev) {
    if (ev) ev.preventDefault();
    const s = readSurname();
    if (!s) { $('#surname').focus(); return; }
    let l1, l2;
    try { [l1, l2] = surnameStrokes(s.info); } catch (e) { setBusy(false, e.message); return; }
    setBusy(true, '計算中…');
    $('#results').innerHTML = '<div class="progress"><b id="pbar"></b></div>';
    const runId = ++state.runId;
    (async () => {
      try {
        const fate = readFate();
        renderBazi(fate);
        const opt = readOptions();
        const t0 = performance.now();
        const pbar = $('#pbar');
        const res = await Nova.generator.generateAsync(l1, l2, fate, opt, (i, n) => { if (pbar) pbar.style.width = (100 * i / n) + '%'; });
        if (runId !== state.runId) return; // 使用者已重新送出
        Object.assign(state, { fate, results: res, l1, l2, surname: s.surname, weights: opt.weights });
        renderResults(res, { surname: s.surname, l1, l2, fate, weights: opt.weights });
        const nw = Nova.rating.normalizeWeights(opt.weights);
        setBusy(false, `${res.length} 個結果，${Math.round(performance.now() - t0)} ms`
          + (Nova.rating.isDefaultWeights(nw) ? '' : `・權重 ${Nova.rating.weightsText(nw)}`));
        try { history.replaceState(null, '', buildQuery(s.surname)); } catch (_) { /* file:// 在部分瀏覽器不允許 */ }
      } catch (e) {
        console.error(e);
        $('#results').innerHTML = `<p class="hint">發生錯誤：${esc(e.message)}</p>`;
        setBusy(false, '');
      }
    })();
  }

  function renderResults(res, ctx) {
    const box = $('#results');
    registry.clear();
    if (!res.length) { box.innerHTML = '<p class="hint">沒有符合條件的組合，請放寬嚴格度或字集。</p>'; return; }
    box.innerHTML = res.map((c, i) => card(c, i, ctx)).join('');
  }

  function register(cand, ctx) {
    const id = nextId++;
    registry.set(String(id), Object.assign({ cand }, ctx));
    return id;
  }

  function card(c, i, ctx, reason) {
    const g = c.combo.ge;
    const id = register(c, ctx);
    const nw = Nova.rating.normalizeWeights(ctx.weights || null);   // 只影響顯示，分數已由引擎算好
    return `<article class="card" tabindex="0" data-id="${id}">
      <div class="head"><span class="rank">${i + 1}</span><span class="name">${esc(ctx.surname + c.c1.char + c.c2.char)}</span>
        <span class="py">${esc(c.c1.py[0])} ${esc(c.c2.py[0])}</span>
        <span class="total">${c.total.toFixed(1)} <span class="badge g-${esc(c.grade)}">${esc(c.grade)}</span></span></div>
      <div class="bars">${DIMS.map(([n], k) => `<span class="bar${nw[k] > 0 ? '' : ' off'}" title="權重 ${Nova.rating.round1(nw[k] * 100)}%">${n} ${Math.round(c.scores[k])}<i><b style="width:${c.scores[k]}%"></b></i></span>`).join('')}</div>
      <div class="meta"><span>筆畫 ${ctx.l1}${ctx.l2 ? '+' + ctx.l2 : ''}+${c.combo.f1}+${c.combo.f2}</span><span>五格 ${g.tian}/${g.ren}/${g.di}/${g.wai}/${g.zong}</span>
        <span>三才 ${esc(c.combo.sancaiKey)}</span><span>${wxTag(c.c1.wx)}${wxTag(c.c2.wx)}</span></div>
      ${reason ? `<div class="reason">AI：${esc(reason)}</div>` : ''}
    </article>`;
  }

  function detailHtml(r, c1, c2) {
    const S = Nova.sancai, W = Nova.wuge, D = Nova.dayan, g = r.ge;
    const w = r.weights || Nova.rating.DEFAULT_WEIGHTS;
    const geList = g ? [['天格', g.tian], ['人格', g.ren], ['地格', g.di], ['外格', g.wai], ['總格', g.zong]] : [];
    const geItems = geList.map(([n, v]) => {
      const dy = D.find(v);
      return `<div><small>${n}</small><span class="n">${v}</span><small class="lucky-${esc(dy.lucky)}">${esc(dy.title)}・${esc(dy.lucky)}</small><small>${W.yinyangOf(v)}${W.elementOf(v)}</small></div>`;
    }).join('');
    const ren = g ? W.elementOf(g.ren) : '';
    const aiOk = document.body.classList.contains('ai-ready');
    return `<div class="detail">
      <div class="charinfo">${[c1, c2].map((c) => `<div><span class="c">${esc(c.char)}</span>${esc(c.py.join(' / '))}・${c.stroke}畫・${wxTag(c.wx)}<br><span class="dim">${esc(c.meaning || '（無釋義）')}</span></div>`).join('')}</div>
      ${g ? `<h4>五格</h4><div class="ge">${geItems}</div>
      <p class="dim">${geList.map(([n, v]) => `${n}：${esc(D.find(v).comment)}`).join('<br>')}</p>
      <h4>三才 ${esc(r.sancaiKey)}・${esc(S.verdict(r.sancaiKey))}</h4>
      <p>${esc(S.detail(r.sancaiKey))}</p>
      <p><b>基礎運</b> ${esc(S.jichu(ren, W.elementOf(g.di)))}<br><b>成功運</b> ${esc(S.chenggong(ren, W.elementOf(g.tian)))}<br><b>人際</b> ${esc(S.renji(ren, W.elementOf(g.wai)))}</p>` : ''}
      <h4>評分明細 <span class="dim">總分 ${r.total.toFixed(1)}（${esc(r.grade)}）＝各維加權平均</span></h4>
      ${DIMS.map(([n, k], i) => `<p><b${w[i] > 0 ? '' : ' class="off"'}>${n} ${r[k]}</b> <span class="wpct">×${Nova.rating.round1(w[i] * 100)}%</span> <span class="dim">${esc((r.details[k] || []).join('；') || '—')}</span></p>`).join('')}
      <p><button type="button" class="ai-explain" ${aiOk ? '' : 'disabled title="請先在左側 AI 顧問填入 API key"'}>AI 解說</button></p>
      <div class="ai-text"></div>
    </div>`;
  }

  function onResultsClick(ev) {
    const el = ev.target.closest('.card');
    if (!el) return;
    const entry = registry.get(el.dataset.id);
    if (!entry) return;
    if (ev.target.classList.contains('ai-explain')) { onAiExplain(entry, el); return; }
    if (ev.target.closest('.detail')) return;
    const d = el.querySelector('.detail');
    if (d) { d.remove(); return; }
    const r = Nova.rating.rateName(entry.l1, entry.l2, entry.cand.c1, entry.cand.c2, entry.fate, entry.weights || null);
    el.insertAdjacentHTML('beforeend', detailHtml(r, entry.cand.c1, entry.cand.c2));
  }

  function candFromRating(c1, c2, r) {
    return { c1, c2, combo: { ge: r.ge, f1: c1.stroke, f2: c2.stroke, sancaiKey: r.sancaiKey },
      scores: [r.wenhua, r.wuxing, r.shengxiao, r.wuge, r.yinyun], total: r.total, grade: r.grade };
  }

  // ---------------------------------------------------------------- 筆畫組合選字
  // 與「產生名字」獨立（核心在 js/core/combos.js）：謝達輝三才等級 → 勾選的格皆為 36 吉數（含天格）
  // → 人地外總四格的吉數等級（大吉／吉／半吉／半凶／凶，預設全收；天格不計）→ 依第一字筆畫分組列出
  // 所有 (第一字, 第二字) 筆畫；點一組 → 兩份字表 → 點第一字＋第二字 → 用現有評分卡評分。過濾條件記在這個瀏覽器。
  const COMBOS_KEY = 'nova.combos.v1';
  const GRID_LABEL = { tian: '天格', ren: '人格', di: '地格', wai: '外格', zong: '總格' };
  const TONES = [['1', 'ˉ', '一聲'], ['2', 'ˊ', '二聲'], ['3', 'ˇ', '三聲'], ['4', 'ˋ', '四聲'], ['0', '˙', '輕聲']];   // yinyun.tone 的值
  // wxf／tf：兩個字各自的五行、聲調過濾，都可複選（Set 空＝全部；同一排多選是 OR，五行與聲調之間是 AND）
  const cstate = { ctx: null, filt: null, rows: [], sel: null, pick: [null, null], wxf: [new Set(), new Set()], tf: [new Set(), new Set()], names: [] };
  let urlCombo = null, urlPick = null;   // 網址 &combo=19,6[&pick=薇宇]：開頁時預先選好組合（與字），供分享與測試

  function loadCombosFilter() {
    const f = Nova.combos.defaultFilter();
    try {
      const s = JSON.parse(localStorage.getItem(COMBOS_KEY));
      if (s && Array.isArray(s.grades)) {
        const g = s.grades.filter((x) => Nova.sancai.CDI_SELECTABLE.includes(x));
        if (g.length) f.sancaiGrades = new Set(g);
      }
      if (s && Array.isArray(s.grids)) f.grids = Nova.combos.GRIDS.filter((k) => s.grids.includes(k));
      if (s && Array.isArray(s.jishuGrades)) {
        const jg = s.jishuGrades.filter((x) => Nova.dayan.GRADES.includes(x));
        if (jg.length) f.jishuGrades = new Set(jg);
      }
    } catch (_) { /* ignore */ }
    return f;
  }
  function saveCombosFilter(f) {
    try { localStorage.setItem(COMBOS_KEY, JSON.stringify({ grades: [...f.sancaiGrades], grids: f.grids, jishuGrades: [...f.jishuGrades] })); } catch (_) { /* ignore */ }
  }
  const combosMounted = () => !!$('#combos') && !!cstate.ctx;

  function onCombos() {
    const s = readSurname();
    if (!s) { $('#surname').focus(); return; }
    let l1, l2;
    try { [l1, l2] = surnameStrokes(s.info); } catch (e) { setBusy(false, e.message); return; }
    state.runId++;                                   // 進行中的 generateAsync 不再回寫結果
    const fate = readFate();
    renderBazi(fate);
    const same = cstate.ctx && cstate.ctx.surname === s.surname && cstate.ctx.l1 === l1 && cstate.ctx.l2 === l2;
    cstate.ctx = { surname: s.surname, l1, l2, fate, weights: readWeights() };
    cstate.filt = loadCombosFilter();
    cstate.filt.excludeFemaleCaution = $('#female-caution').checked;
    if (!same) { cstate.sel = null; cstate.pick = [null, null]; cstate.names = []; }
    recomputeCombos();
    renderCombos();
    setBusy(false, `${cstate.rows.length} 組合格筆畫組合`);
    if (urlCombo) {
      const [f1, f2] = urlCombo.split(/[,+]/).map(Number);
      cstate.sel = cstate.rows.find((r) => r.f1 === f1 && r.f2 === f2) || null;
      const cs = urlPick ? [...urlPick].map((ch) => Nova.chars.lookup(ch)) : [];
      if (cstate.sel && cs.length === 2 && cs[0] && cs[1] && cs[0].stroke === f1 && cs[1].stroke === f2) cstate.pick = cs;
      urlCombo = urlPick = null;
      renderGroups(); renderPick(); composeName();
    }
    try { history.replaceState(null, '', buildQuery(s.surname) + '&mode=combos'); } catch (_) { /* file:// 在部分瀏覽器不允許 */ }
  }

  function recomputeCombos() {
    const { l1, l2 } = cstate.ctx;
    cstate.rows = Nova.combos.enumerateCombos(l1, l2, cstate.filt);
    if (cstate.sel && !cstate.rows.some((r) => r.f1 === cstate.sel.f1 && r.f2 === cstate.sel.f2)) { cstate.sel = null; cstate.pick = [null, null]; }
  }

  function tianBadge() {
    const { l1, l2 } = cstate.ctx, n = Nova.combos.tianOf(l1, l2), D = Nova.dayan, dy = D.find(n), ok = D.isJishu(n), jg = D.grade(n);
    return `天格 <b class="n">${n}</b> <span class="lucky-${esc(dy.lucky)}">${esc(dy.title)}・${esc(dy.lucky)}</span> <span class="${ok ? 'jishu-ok' : 'jishu-bad'}">${ok ? '吉數' : '非吉數'}</span> <b class="jg-${esc(jg)}" title="吉數等級 ${esc(jg)}（謝達輝 81 劃表 ${esc(D.cdiGrade(n))}）；天格不納入等級條件">${esc(jg)}</b>`;
  }

  function renderCombos() {
    const { surname, l1, l2 } = cstate.ctx, f = cstate.filt;
    registry.clear();
    const gradeChips = Nova.sancai.CDI_SELECTABLE.map((g) =>
      `<label class="chip cg-${esc(g)}"><input type="checkbox" data-f="grade" value="${esc(g)}"${f.sancaiGrades.has(g) ? ' checked' : ''}>${esc(g)}</label>`).join('');
    const gridChips = Nova.combos.GRIDS.map((k) =>
      `<label class="chip"><input type="checkbox" data-f="grid" value="${k}"${f.grids.includes(k) ? ' checked' : ''}>${GRID_LABEL[k]}${k === 'tian' ? ' ' + Nova.combos.tianOf(l1, l2) : ''}</label>`).join('');
    const jishu = [...Nova.dayan.jishu()].sort((a, b) => a - b);
    const jgCounts = Nova.dayan.GRADES.reduce((m, g) => (m[g] = 0, m), {});
    for (let n = 1; n <= 81; n++) jgCounts[Nova.dayan.grade(n)]++;
    const jgChips = Nova.dayan.GRADES.map((g) =>
      `<label class="chip jg-${esc(g)}" title="81 數中 ${jgCounts[g]} 個"><input type="checkbox" data-f="jgrade" value="${esc(g)}"${f.jishuGrades.has(g) ? ' checked' : ''}>${esc(g)}<small>${jgCounts[g]}</small></label>`).join('');
    $('#results').innerHTML = `<section id="combos" class="combos">
      <div class="combos-head"><h3>筆畫組合選字 <span class="dim">姓 ${esc(surname)} ${l1}${l2 ? '+' + l2 : ''} 畫</span></h3><div class="tian" id="combos-tian">${tianBadge()}</div></div>
      <div class="combos-filter" id="combos-filter">
        <div class="frow"><span class="flabel">三才吉凶表（謝達輝）</span>${gradeChips}</div>
        <div class="frow"><span class="flabel">須為吉數的格</span>${gridChips}<span class="dim small" title="${jishu.join(' ')}">吉數表 ${jishu.length} 個</span></div>
        <div class="frow"><span class="flabel">吉數等級（人地外總）</span>${jgChips}<span class="dim small" title="天格由姓氏決定、改不了，不納入這條件">天格不計；大吉＋吉＝36 吉數；全勾＝不限制</span></div>
        <p class="hint small">另沿用左側「字集」「排除字」「排除女性不宜總格」。五格分是原評分（fate 81 數理表），只作排序參考。</p>
      </div>
      <div id="combos-groups"></div><div id="combos-pick"></div><div id="combos-names"></div>
    </section>`;
    renderGroups(); renderPick(); renderNames();
  }

  function renderGroups() {
    const box = $('#combos-groups');
    if (!box) return;
    const { l1, l2 } = cstate.ctx, f = cstate.filt, rows = cstate.rows;
    $('#combos-tian').innerHTML = tianBadge();
    if (!rows.length && f.grids.includes('tian') && !Nova.combos.tianOk(l1, l2)) {
      const alt = Nova.combos.enumerateCombos(l1, l2, Object.assign({}, f, { grids: f.grids.filter((k) => k !== 'tian') })).length;
      box.innerHTML = `<p class="hint tianfail">天格 ${Nova.combos.tianOf(l1, l2)} 不在吉數內；天格由姓氏決定、無法選擇。取消勾選「天格」即可列出其他各格皆吉數的組合（${alt} 組）。<button type="button" class="chip" data-act="drop-tian">取消勾選天格</button></p>`;
      return;
    }
    if (!rows.length) { box.innerHTML = '<p class="hint">沒有符合的組合：請至少勾選一個三才等級，或加入「平吉」、放寬吉數等級、減少須為吉數的格。</p>'; return; }
    const groups = Nova.combos.groupByFirst(rows);
    const gradesTxt = Nova.sancai.CDI_SELECTABLE.filter((g) => f.sancaiGrades.has(g)).join('、');
    const gridsTxt = f.grids.length ? f.grids.map((k) => GRID_LABEL[k][0]).join('') + ' 皆吉數' : '不限吉數';
    const jgTxt = f.jishuGrades.size >= Nova.dayan.GRADES.length ? ''
      : '；人地外總等級限 ' + Nova.dayan.GRADES.filter((g) => f.jishuGrades.has(g)).join('、');
    box.innerHTML = `<p class="combos-summary">符合 <b>${rows.length}</b> 組・第一字 ${groups.length} 種筆畫 <span class="dim">（三才 ${esc(gradesTxt)}；${gridsTxt}${esc(jgTxt)}）點第二字筆畫選定組合</span></p>`
      + groups.map(([f1, rs]) => `<div class="cgroup"><span class="f1">第一字 ${f1} 畫</span>${rs.map((r) => {
        const g = r.ge, on = cstate.sel && cstate.sel.f1 === r.f1 && cstate.sel.f2 === r.f2;
        const marks = Nova.combos.GRIDS.map((k) => GRID_LABEL[k][0] + r.grades[k]).join(' ');
        return `<button type="button" class="f2 cg-${esc(r.cdiGrade)}${on ? ' on' : ''}" data-f1="${r.f1}" data-f2="${r.f2}" aria-pressed="${on ? 'true' : 'false'}" title="五格 ${g.tian}/${g.ren}/${g.di}/${g.wai}/${g.zong}（${marks}）・三才 ${esc(r.sancaiKey)} ${esc(r.cdiGrade)}（原表 ${esc(r.fateVerdict)}）・五格分 ${r.wugeScore}">${r.f2}<small>${esc(r.cdiGrade)}</small></button>`;
      }).join('')}</div>`).join('');
  }

  function geCells(g) {
    const D = Nova.dayan, W = Nova.wuge;
    return [['天格', g.tian], ['人格', g.ren], ['地格', g.di], ['外格', g.wai], ['總格', g.zong]].map(([n, v]) => {
      const dy = D.find(v), ok = D.isJishu(v), jg = D.grade(v);
      return `<div><small>${n}</small><span class="n">${v}</span><small class="lucky-${esc(dy.lucky)}">${esc(dy.title)}・${esc(dy.lucky)}</small><small class="${ok ? 'jishu-ok' : 'jishu-bad'}">${ok ? '吉數' : '非吉數'}・${W.yinyangOf(v)}${W.elementOf(v)}</small><small class="jg-${esc(jg)}" title="吉數等級（謝達輝 81 劃表 ${esc(D.cdiGrade(v))}）">${esc(jg)}</small></div>`;
    }).join('');
  }

  // 五行／聲調晶片：點「全部」（值為空）清空條件，點其他值加入或移除；清空後就是不限
  function toggleFilter(set, v) { if (!v) set.clear(); else if (!set.delete(v)) set.add(v); }

  function charListHtml(slot, stroke, list) {
    const fate = cstate.ctx.fate, wxf = cstate.wxf[slot], tf = cstate.tf[slot], pick = cstate.pick[slot];
    const toneOf = (c) => String(Nova.yinyun.tone(c.py[0]));   // 以主要讀音的聲調為準；0 = 輕聲
    const hitWx = (c) => !wxf.size || wxf.has(c.wx);           // 空＝不限
    const hitTone = (c) => !tf.size || tf.has(toneOf(c));
    const byTone = list.filter(hitTone);   // 只套聲調（供五行按鈕計數）
    const byWx = list.filter(hitWx);       // 只套五行（供聲調按鈕計數）
    const shown = byTone.filter(hitWx);
    // 每顆晶片是獨立開關，計數不含同一排其他選項（勾了也還看得到別的五行／聲調各有幾字）
    const chip = (on, attr, val, label, n) =>
      `<button type="button" class="chip${on ? ' on' : ''}" aria-pressed="${on ? 'true' : 'false'}" data-slot="${slot}" data-${attr}="${esc(val)}">${label}<small>${n}</small></button>`;
    const wxChips = ['', ...Nova.bazi.ELEMENTS].map((e) =>
      chip(e ? wxf.has(e) : !wxf.size, 'wxf', e, e ? wxTag(e) + e : '全部', e ? byTone.filter((c) => c.wx === e).length : byTone.length)).join('');
    const toneChips = [['', '', '全部'], ...TONES].map(([t, mark, name]) =>
      chip(t ? tf.has(t) : !tf.size, 'tf', t, (mark ? '<b class="tm">' + mark + '</b>' : '') + name, t ? byWx.filter((c) => toneOf(c) === t).length : byWx.length)).join('');
    const tiles = shown.map((c) => {
      const hi = fate && (c.wx === fate.yong || c.wx === fate.xi), lo = fate && (c.wx === fate.ji || c.wx === fate.chou);
      const on = pick && pick.char === c.char;
      return `<button type="button" class="ch${hi ? ' hi' : ''}${lo ? ' lo' : ''}${on ? ' on' : ''}" data-slot="${slot}" data-ch="${esc(c.char)}" data-wx="${esc(c.wx)}" title="${esc(c.py.join(' / '))}・${esc(c.wx)}・${esc(c.meaning || '（無釋義）')}">${esc(c.char)}</button>`;
    }).join('');
    return `<div class="charlist" data-slot="${slot}"><h4>${slot === 0 ? '第一字' : '第二字'} ${stroke} 畫 <span class="dim">（${shown.length}${shown.length !== list.length ? '／' + list.length : ''} 字）</span></h4>
      <div class="wxfilter chips"><span class="fl">五行</span>${wxChips}</div>
      <div class="wxfilter chips"><span class="fl">聲調</span>${toneChips}</div>
      <div class="chars">${tiles || '<span class="dim">（沒有同時符合所選五行與聲調的字）</span>'}</div>
      <p class="chinfo">${pick ? chInfoHtml(pick) : ''}</p></div>`;
  }

  // 手機沒有滑鼠、看不到 title，所以點到的字直接把拼音與字義寫在字表下面
  function chInfoHtml(c) {
    return `<b>${esc(c.char)}</b>${esc(c.py.join(' / '))}・${wxTag(c.wx)}・${esc(c.meaning || '（無釋義）')}`;
  }

  function renderPick() {
    const box = $('#combos-pick');
    if (!box) return;
    const r = cstate.sel;
    if (!r) { box.innerHTML = ''; return; }
    const S = Nova.sancai, fate = cstate.ctx.fate;
    const lists = Nova.combos.charLists(r.f1, r.f2, Number($('#level').value), readOptions().avoidChars);
    cstate.pick = cstate.pick.map((p, i) => (p && lists[i].some((c) => c.char === p.char) ? p : null));   // 改字集／排除字後失效的字丟掉
    const legend = fate ? `<br>綠框：用神／喜神 ${wxTag(fate.yong)}${wxTag(fate.xi)}；淡化：忌神／仇神 ${wxTag(fate.ji)}${wxTag(fate.chou)}。` : '';
    box.innerHTML = `<div class="combo-sel">
      <h4>已選 ${r.f1} + ${r.f2} 畫 <span class="dim">五格分（原評分）${r.wugeScore}</span></h4>
      <div class="ge">${geCells(r.ge)}</div>
      <p>三才 ${esc(r.sancaiKey)}・<b class="cg-${esc(r.cdiGrade)}">${esc(r.cdiGrade)}</b> <span class="dim">（原表 ${esc(r.fateVerdict)}）</span><br><span class="dim">${esc(S.detail(r.sancaiKey))}</span></p>
      <p class="hint small">點一個第一字、再點一個第二字，下方就會出現這個名字的評分；字表可依五行、注音聲調過濾（聲調取主要讀音），兩排都可複選——同一排選多個是「其中之一」，五行與聲調則要同時符合，點「全部」取消該排的條件。點到的字會在字表下方顯示拼音與字義。${legend}</p>
    </div>
    <div class="charpick">${charListHtml(0, r.f1, lists[0])}${charListHtml(1, r.f2, lists[1])}</div>`;
  }

  function renderNames() {
    const box = $('#combos-names');
    if (!box) return;
    if (!cstate.names.length) { box.innerHTML = ''; return; }
    const ctx = Object.assign({}, cstate.ctx, { weights: readWeights() });
    const rate = (c1, c2) => Nova.rating.rateName(ctx.l1, ctx.l2, c1, c2, ctx.fate, ctx.weights);
    box.innerHTML = `<div class="combos-names"><h4>已選名字 <span class="dim">（${cstate.names.length}）</span><button type="button" class="icon" data-act="clear-names">清除</button></h4>`
      + cstate.names.map(({ c1, c2 }, i) => card(candFromRating(c1, c2, rate(c1, c2)), i, ctx)).join('') + '</div>';
    const first = box.querySelector('.card');                     // 最新一張直接展開明細
    if (first) { const { c1, c2 } = cstate.names[0]; first.insertAdjacentHTML('beforeend', detailHtml(rate(c1, c2), c1, c2)); }
  }

  function composeName() {
    const [c1, c2] = cstate.pick;
    if (!c1 || !c2) return;
    const key = c1.char + c2.char;
    cstate.names = [{ c1, c2 }, ...cstate.names.filter((n) => n.c1.char + n.c2.char !== key)].slice(0, 30);
    renderNames();
    const r = Nova.rating.rateName(cstate.ctx.l1, cstate.ctx.l2, c1, c2, cstate.ctx.fate, readWeights());
    setBusy(false, `已選 ${cstate.ctx.surname}${key} ${r.total.toFixed(1)}（${r.grade}）`);
  }

  function onCombosClick(ev) {
    if (!ev.target.closest('#combos') || ev.target.closest('.card')) return;   // 卡片交給 onResultsClick
    const b = ev.target.closest('button');
    if (!b) return;
    if (b.classList.contains('f2')) {
      const f1 = Number(b.dataset.f1), f2 = Number(b.dataset.f2);
      cstate.sel = cstate.rows.find((r) => r.f1 === f1 && r.f2 === f2) || null;
      cstate.pick = [null, null];
      renderGroups(); renderPick();
      const p = $('#combos-pick');
      if (p && p.scrollIntoView) p.scrollIntoView({ behavior: 'smooth', block: 'start' });
      return;
    }
    if (b.classList.contains('ch')) {
      const slot = Number(b.dataset.slot), c = Nova.chars.lookup(b.dataset.ch);
      cstate.pick[slot] = cstate.pick[slot] && cstate.pick[slot].char === c.char ? null : c;
      b.closest('.chars').querySelectorAll('.ch.on').forEach((x) => x.classList.remove('on'));
      if (cstate.pick[slot]) b.classList.add('on');
      const info = b.closest('.charlist').querySelector('.chinfo');
      if (info) info.innerHTML = cstate.pick[slot] ? chInfoHtml(c) : '';
      composeName();
      return;
    }
    if (b.dataset.wxf !== undefined) { toggleFilter(cstate.wxf[Number(b.dataset.slot)], b.dataset.wxf); renderPick(); return; }
    if (b.dataset.tf !== undefined) { toggleFilter(cstate.tf[Number(b.dataset.slot)], b.dataset.tf); renderPick(); return; }
    if (b.dataset.act === 'drop-tian') {
      cstate.filt.grids = cstate.filt.grids.filter((k) => k !== 'tian');
      const cb = $('#combos-filter input[data-f="grid"][value="tian"]');
      if (cb) cb.checked = false;
      saveCombosFilter(cstate.filt); recomputeCombos(); renderGroups(); renderPick();
      setBusy(false, `${cstate.rows.length} 組合格筆畫組合`);
      return;
    }
    if (b.dataset.act === 'clear-names') { cstate.names = []; renderNames(); }
  }

  function onCombosChange(ev) {
    if (!ev.target.closest('#combos-filter')) return;
    const f = cstate.filt;
    f.sancaiGrades = new Set([...document.querySelectorAll('#combos-filter input[data-f="grade"]:checked')].map((i) => i.value));
    f.grids = [...document.querySelectorAll('#combos-filter input[data-f="grid"]:checked')].map((i) => i.value);
    f.jishuGrades = new Set([...document.querySelectorAll('#combos-filter input[data-f="jgrade"]:checked')].map((i) => i.value));
    saveCombosFilter(f); recomputeCombos(); renderGroups(); renderPick();
    setBusy(false, `${cstate.rows.length} 組合格筆畫組合`);
  }

  // 左側條件變動時同步：女性不宜總格 → 重算組合；字集／排除字 → 重畫字表
  function onCombosSideChange(kind) {
    if (!combosMounted()) return;
    if (kind === 'female') { cstate.filt.excludeFemaleCaution = $('#female-caution').checked; recomputeCombos(); renderGroups(); }
    renderPick();
  }

  // ---------------------------------------------------------------- 單一名字
  function onExplain(ev) {
    ev.preventDefault();
    const s = readSurname();
    if (!s) { $('#surname').focus(); return; }
    const name = [...$('#explain-name').value.trim()];
    if (name.length !== 2) { setBusy(false, '請輸入兩字名'); return; }
    const c1 = Nova.chars.lookup(name[0]), c2 = Nova.chars.lookup(name[1]);
    if (!c1 || !c2) { $('#results').innerHTML = `<p class="hint">字典中查無「${esc(name.join(''))}」的用字。</p>`; return; }
    let l1, l2;
    try { [l1, l2] = surnameStrokes(s.info); } catch (e) { setBusy(false, e.message); return; }
    const fate = readFate();
    renderBazi(fate);
    const weights = readWeights();
    const r = Nova.rating.rateName(l1, l2, c1, c2, fate, weights);
    registry.clear();
    $('#results').innerHTML = card(candFromRating(c1, c2, r), 0, { surname: s.surname, l1, l2, fate, weights });
    $('#results .card').insertAdjacentHTML('beforeend', detailHtml(r, c1, c2));
    setBusy(false, '');
  }

  // ---------------------------------------------------------------- AI 顧問
  function aiProvider() { return Nova.llm.providers[$('#ai-provider').value]; }

  function aiSync() {
    const p = aiProvider();
    if (!$('#ai-model').value.trim() && p.defaultModel) $('#ai-model').value = p.defaultModel;
    const s = Nova.llm.set({ provider: p.id, model: $('#ai-model').value.trim(), apiKey: $('#ai-key').value.trim() });
    const warn = p.keyWarning(s.apiKey);
    $('#ai-warn').innerHTML = warn ? `<span class="chip ${s.apiKey ? 'warn' : ''}">${esc(warn)}</span>` : '';
    const ready = !!s.apiKey;
    $('#ai-recommend').disabled = !ready;
    document.body.classList.toggle('ai-ready', ready);
    document.querySelectorAll('.ai-explain').forEach((b) => { b.disabled = !ready; });
    aiSyncPick();
  }

  // 模型下拉：清單抓到後列出模型 id，最後一項「自行輸入…」才顯示文字欄位；文字欄位 #ai-model 永遠是設定的真相來源。
  const CUSTOM = '__custom__';
  let modelList = [], customMode = false;
  function aiRenderPick() {
    const opts = modelList.length
      ? modelList.map((m) => `<option value="${esc(m.id)}" title="${esc(m.label)}">${esc(m.id)}</option>`)
      : ['<option value="" disabled>（貼上 key 後自動抓取清單）</option>'];
    opts.push(`<option value="${CUSTOM}">自行輸入…</option>`);
    $('#ai-model-pick').innerHTML = opts.join('');
    aiSyncPick();
  }
  function aiSyncPick() {
    const cur = $('#ai-model').value.trim();
    const custom = customMode || !modelList.some((m) => m.id === cur);
    $('#ai-model-pick').value = custom ? CUSTOM : cur;
    $('#ai-model-custom').hidden = !custom;
  }

  // 模型清單：有 key 就向供應商抓一次（同一把 key 不重抓，舊式 key 不白抓）；↻ 強制重抓。清單進 datalist，欄位仍可自行輸入。
  let modelsKey = '', modelsTimer = null;
  async function aiLoadModels(force) {
    const p = aiProvider(), s = Nova.llm.settings(), st = $('#ai-models-status');
    if (!s.apiKey || !p.listModels) { st.textContent = ''; return; }
    if (!force && (modelsKey === s.apiKey || p.keyWarning(s.apiKey))) return;
    modelsKey = s.apiKey;
    st.textContent = '抓取可用模型…';
    $('#ai-models-refresh').disabled = true;
    try {
      const models = await Nova.llm.listModels();
      const cur = $('#ai-model').value.trim();
      modelList = models;
      customMode = !models.some((m) => m.id === cur);
      aiRenderPick();
      st.textContent = `${models.length} 個可用模型` + (customMode && cur ? `；目前的「${cur}」不在清單中，保留自行輸入` : '');
    } catch (e) {
      modelsKey = '';
      st.textContent = '抓不到模型清單：' + e.message;
    } finally {
      $('#ai-models-refresh').disabled = false;
    }
  }

  function aiInit() {
    const sel = $('#ai-provider');
    sel.innerHTML = Object.values(Nova.llm.providers).map((p) => `<option value="${p.id}">${esc(p.label)}</option>`).join('');
    const s = Nova.llm.settings();
    sel.value = s.provider;
    $('#ai-model').value = s.model;
    $('#ai-key').value = s.apiKey;
    aiRenderPick();
    sel.addEventListener('change', () => { customMode = false; $('#ai-model').value = aiProvider().defaultModel || ''; aiSync(); });
    $('#ai-model-pick').addEventListener('change', () => {
      const v = $('#ai-model-pick').value;
      customMode = v === CUSTOM;
      if (!customMode) $('#ai-model').value = v;
      aiSync();
      if (customMode) $('#ai-model').focus();
    });
    for (const id of ['ai-model', 'ai-key']) $('#' + id).addEventListener('input', aiSync);
    $('#ai-key').addEventListener('input', () => { clearTimeout(modelsTimer); modelsTimer = setTimeout(() => aiLoadModels(false), 700); });
    $('#ai-models-refresh').addEventListener('click', () => aiLoadModels(true));
    $('#ai-recommend').addEventListener('click', onAiRecommend);
    $('#ai-history-list').addEventListener('click', onHistoryClick);
    initPrefs();
    renderHistory();
    aiSync();
    aiLoadModels(false);
  }

  async function onAiRecommend() {
    const s = readSurname();
    if (!s) { $('#surname').focus(); return; }
    let l1, l2;
    try { [l1, l2] = surnameStrokes(s.info); } catch (e) { $('#ai-status').textContent = e.message; return; }
    const btn = $('#ai-recommend');
    btn.disabled = true;
    $('#ai-status').textContent = 'AI 思考中…';
    let hid = null;
    try {
      const fate = readFate();
      renderBazi(fate);
      const opt = readOptions();
      const combos = Nova.generator.luckyCombos(l1, l2, opt);
      if (!combos.length) throw new Error('沒有合格的筆畫組合，請放寬嚴格度');
      const buckets = Nova.chars.byStroke(opt.maxLevel);
      const prefs = $('#ai-prefs').value.trim();
      savePrefs();
      const nw = Nova.rating.normalizeWeights(opt.weights);
      hid = Nova.aiHistory.add({ surname: s.surname, gender: opt.gender, born: bornSummary(), model: Nova.llm.settings().model,
        weights: Nova.rating.weightsText(nw), prefs });
      renderHistory();
      const req = Nova.advisor.buildRecommend({ surname: s.surname, l1, l2, gender: opt.gender, fate, combos, buckets, n: 8,
        preferences: prefs, weights: opt.weights });
      const { data, usage } = await Nova.llm.generateJson({ system: req.system, user: req.user, schema: Nova.advisor.PICKS_SCHEMA,
        onStatus: (m) => { $('#ai-status').textContent = m; } });
      const { ok, rejected } = Nova.advisor.validatePicks(data.picks, req);
      renderAiPicks(ok, { surname: s.surname, l1, l2, fate, weights: opt.weights });
      Nova.aiHistory.update(hid, { result: ok.map(({ c1, c2 }) => ({ name: s.surname + c1.char + c2.char, total: Nova.rating.rateName(l1, l2, c1, c2, fate, opt.weights).total })) });
      $('#ai-status').textContent = `${ok.length} 個建議` + (rejected.length ? `（${rejected.length} 個不合格已略過）` : '')
        + (usage && usage.totalTokenCount ? `・${usage.totalTokenCount} tokens` : '');
    } catch (e) {
      console.error(e);
      if (hid) Nova.aiHistory.update(hid, { error: e.message });
      $('#ai-status').textContent = e.message;
    } finally {
      renderHistory();
      aiSync();
    }
  }

  // ---------------------------------------------------------------- 給 AI 的偏好：範本文字與記憶
  // 第一次開（沒存過）填 js/defaults.js 的範本；之後記住使用者改過的文字（清空也算），「範本」按鈕帶回範本。
  const PREFS_KEY = 'nova.ai.prefs.v1';
  function templatePrefs() { return (Nova.template && Nova.template.prefs) || ''; }
  function savePrefs() {
    try { localStorage.setItem(PREFS_KEY, $('#ai-prefs').value); } catch (_) { /* ignore */ }
  }
  function initPrefs() {
    let saved = null;
    try { saved = localStorage.getItem(PREFS_KEY); } catch (_) { /* ignore */ }
    $('#ai-prefs').value = saved !== null ? saved : templatePrefs();
    $('#ai-prefs').addEventListener('change', savePrefs);
    $('#ai-prefs-template').addEventListener('click', () => {
      $('#ai-prefs').value = templatePrefs();
      savePrefs();
      $('#ai-prefs').focus();
    });
  }

  // ---------------------------------------------------------------- 歷史紀錄（資料層在 js/ai_history.js）
  function bornSummary() {
    const d = $('#born-date').value;
    if (!d) return '';
    return $('#hour-unknown').checked || !$('#born-time').value ? d + '（時辰不詳）' : d + ' ' + $('#born-time').value;
  }
  function fmtTime(iso) {
    const d = new Date(iso), p = (n) => String(n).padStart(2, '0');
    return `${d.getMonth() + 1}/${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
  }
  function histResult(h) {
    if (h.error) return `<span class="bad">失敗：${esc(h.error)}</span>`;
    if (!h.result) return '<span class="dim">進行中…</span>';
    if (!h.result.length) return '<span class="dim">沒有合格建議</span>';
    return h.result.map((r) => `${esc(r.name)} ${esc(r.total)}`).join('、');
  }
  function renderHistory() {
    const items = Nova.aiHistory.list();
    $('#ai-history-count').textContent = items.length ? `（${items.length}）` : '';
    const box = $('#ai-history-list');
    if (!items.length) {
      box.innerHTML = '<p class="hint small">按「AI 推薦用字」後，這裡會記下每次的條件、偏好、模型與結果；可把偏好帶回欄位，修改後重新詢問。</p>';
      return;
    }
    box.innerHTML = items.map((h) => `
      <div class="hist-item" data-id="${esc(h.id)}">
        <div class="hist-meta">${esc(fmtTime(h.t))}・${esc(h.surname)}・${h.gender === 'girl' ? '女' : '男'}${h.born ? '・' + esc(h.born) : ''}${h.model ? '・' + esc(h.model) : ''}${h.weights ? '・權重 ' + esc(h.weights) : ''}</div>
        <div class="hist-prefs">${h.prefs ? esc(h.prefs) : '<span class="dim">（無偏好說明）</span>'}</div>
        <div class="hist-result">${histResult(h)}</div>
        <div class="hist-actions"><button type="button" data-act="load">帶回偏好</button><button type="button" data-act="del">刪除</button></div>
      </div>`).join('') + '<div class="hist-actions"><button type="button" data-act="clear">清除全部</button></div>';
  }
  function onHistoryClick(ev) {
    const b = ev.target.closest('button[data-act]');
    if (!b) return;
    const act = b.dataset.act;
    if (act === 'clear') {
      if (confirm('清除全部歷史紀錄？')) { Nova.aiHistory.clear(); renderHistory(); }
      return;
    }
    const id = b.closest('.hist-item').dataset.id;
    if (act === 'del') { Nova.aiHistory.remove(id); renderHistory(); return; }
    if (act === 'load') {
      const h = Nova.aiHistory.list().find((x) => x.id === id);
      if (!h) return;
      $('#ai-prefs').value = h.prefs;
      savePrefs();
      $('#ai-prefs').focus();
      $('#ai-status').textContent = '已帶回偏好，修改後按「AI 推薦用字」重新詢問';
    }
  }

  function renderAiPicks(ok, ctx) {
    const old = $('#ai-picks');
    if (old) old.remove();
    const cards = ok.map(({ c1, c2, reason }, i) => card(candFromRating(c1, c2, Nova.rating.rateName(ctx.l1, ctx.l2, c1, c2, ctx.fate, ctx.weights || null)), i, ctx, reason));
    const html = `<section id="ai-picks"><h3>AI 推薦（分數由 Nova 計算，點卡片看明細）</h3>${cards.length ? cards.join('') : '<p class="hint">AI 沒有給出合格的建議，請再試一次或調整偏好。</p>'}</section>`;
    const box = $('#results');
    if (box.querySelector('.hint') && !box.querySelector('.card')) box.innerHTML = '';
    box.insertAdjacentHTML('afterbegin', html);
  }

  async function onAiExplain(entry, cardEl) {
    const out = cardEl.querySelector('.ai-text'), btn = cardEl.querySelector('.ai-explain');
    btn.disabled = true;
    out.textContent = '生成中…';
    try {
      const r = Nova.rating.rateName(entry.l1, entry.l2, entry.cand.c1, entry.cand.c2, entry.fate, entry.weights || null);
      const req = Nova.advisor.buildExplain({ surname: entry.surname, c1: entry.cand.c1, c2: entry.cand.c2, rating: r, fate: entry.fate });
      await Nova.llm.streamText({ system: req.system, user: req.user, onDelta: (_, full) => { out.textContent = full; },
        onStatus: (m) => { out.textContent = m; } });
    } catch (e) {
      out.textContent = '失敗：' + e.message;
    } finally {
      btn.disabled = false;
    }
  }

  // ---------------------------------------------------------------- URL 參數（測試與分享）
  function buildQuery(surname) {
    const p = new URLSearchParams();
    p.set('surname', surname);
    if ($('#born-date').value) p.set('born', $('#born-date').value + ($('#hour-unknown').checked || !$('#born-time').value ? '' : 'T' + $('#born-time').value));
    p.set('gender', $('#gender').value);
    const raw = readWeights();
    if (!Nova.rating.isDefaultWeights(Nova.rating.normalizeWeights(raw))) p.set('weights', raw.join(','));
    return '?' + p.toString();
  }
  function applyQuery() {
    const p = new URLSearchParams(location.search);
    if (!p.get('surname')) return false;
    $('#surname').value = p.get('surname');
    const born = p.get('born') || '';
    if (born) {
      const [d, t] = born.split('T');
      $('#born-date').value = d;
      if (t) $('#born-time').value = t; else $('#hour-unknown').checked = true;
    }
    if (p.get('gender')) { $('#gender').value = p.get('gender'); $('#female-caution').checked = p.get('gender') === 'girl'; }
    for (const k of ['level', 'strictness', 'method', 'topn', 'perfirst', 'avoid', 'require']) if (p.get(k) != null) $('#' + k).value = p.get(k);
    if (p.get('first')) $('#fixed-first').value = p.get('first');
    if (p.get('second')) $('#fixed-second').value = p.get('second');
    if (p.get('weights')) {
      // 五個數字、「wuge」這類預設名稱、或「三才五格=1,其他=0」都收
      try { applyWeights(Nova.rating.parseWeights(p.get('weights')) || Nova.rating.DEFAULT_WEIGHTS); $('#weights-box').open = true; }
      catch (e) { setBusy(false, '權重參數看不懂：' + e.message); }
    }
    if (p.get('mode') === 'combos') { urlCombo = p.get('combo'); urlPick = p.get('pick'); return 'combos'; }
    if (p.get('explain')) { $('#explain-name').value = p.get('explain'); return 'explain'; }
    return p.get('auto') !== '0' ? 'generate' : false;
  }

  // ---------------------------------------------------------------- init
  function init() {
    $('#form').addEventListener('submit', onGenerate);
    $('#explain-form').addEventListener('submit', onExplain);
    $('#results').addEventListener('click', onResultsClick);
    $('#surname').addEventListener('input', readSurname);
    $('#gender').addEventListener('change', () => { $('#female-caution').checked = $('#gender').value === 'girl'; });
    $('#hour-unknown').addEventListener('change', () => { $('#born-time').disabled = $('#hour-unknown').checked; });
    $('#female-caution').checked = $('#gender').value === 'girl';
    // 筆畫組合選字：性別→「女性不宜」的同步已在上面先註冊，這裡的 change 才讀得到新值（程式改 checked 不會再觸發 change）
    $('#combos-go').addEventListener('click', onCombos);
    $('#results').addEventListener('click', onCombosClick);
    $('#results').addEventListener('change', onCombosChange);
    for (const id of ['female-caution', 'gender']) $('#' + id).addEventListener('change', () => onCombosSideChange('female'));
    $('#level').addEventListener('change', () => onCombosSideChange('level'));
    $('#avoid').addEventListener('input', () => onCombosSideChange('avoid'));
    $('#surname').addEventListener('input', () => { const s = $('#combos'); if (s) s.classList.add('stale'); });
    const d = Nova.chars.data();
    $('#version').textContent = `字典 ${d.map.size} 字（${d.generated}）・lunar-javascript・Nova 0.1`;
    initWeights();
    aiInit();
    const mode = applyQuery();
    if (mode === 'explain') { readSurname(); onExplain(new Event('submit')); }
    else if (mode === 'generate') { readSurname(); onGenerate(); }
    else if (mode === 'combos') { readSurname(); onCombos(); }
  }
  document.addEventListener('DOMContentLoaded', init);
})();
