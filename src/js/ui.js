// UI：表單 → 姓氏筆畫 → 八字 → 產生/評分 → 渲染。純 vanilla，classic script，file:// 可用。
(function () {
  'use strict';
  const $ = (s) => document.querySelector(s);
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const wxTag = (wx) => wx ? `<span class="wx wx-${wx}">${wx}</span>` : '';
  const DIMS = [['文化', 'wenhua'], ['五行', 'wuxing'], ['生肖', 'shengxiao'], ['五格', 'wuge'], ['音韻', 'yinyun']];

  const state = { strokes: null, fate: null, results: [], l1: 0, l2: 0, surname: '', runId: 0 };

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
    box.innerHTML = info.map((x, i) => x.stroke
      ? `<span class="chip">${esc(x.ch)} ${wxTag(x.wx)}<input type="number" min="1" max="60" value="${x.stroke}" data-i="${i}" aria-label="${esc(x.ch)} 筆畫" title="康熙筆畫，可依流派調整"> 畫</span>`
      : `<span class="chip warn">${esc(x.ch)} 查無筆畫，請輸入 <input type="number" min="1" max="60" data-i="${i}" aria-label="${esc(x.ch)} 筆畫"> 畫</span>`).join('')
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

  // ---------------------------------------------------------------- 產生
  function readOptions() {
    const gender = $('#gender').value;
    const fc = $('#female-caution');
    return {
      strictness: $('#strictness').value,
      excludeFemaleCaution: fc.checked,
      maxLevel: Number($('#level').value),
      avoidChars: new Set([...$('#avoid').value.replace(/\s/g, '')]),
      requireChars: new Set([...$('#require').value.replace(/\s/g, '')]),
      fixedFirst: $('#fixed-first').value.trim() || null,
      fixedSecond: $('#fixed-second').value.trim() || null,
      topN: Math.max(1, Math.min(200, Number($('#topn').value) || 20)),
      perFirstChar: Math.max(0, Number($('#perfirst').value) || 0),
      gender,
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
        Object.assign(state, { fate, results: res, l1, l2, surname: s.surname });
        renderResults(res, s.surname, l1, l2, fate);
        setBusy(false, `${res.length} 個結果，${Math.round(performance.now() - t0)} ms`);
        try { history.replaceState(null, '', buildQuery(s.surname)); } catch (_) { /* file:// 在部分瀏覽器不允許 */ }
      } catch (e) {
        console.error(e);
        $('#results').innerHTML = `<p class="hint">發生錯誤：${esc(e.message)}</p>`;
        setBusy(false, '');
      }
    })();
  }

  function renderResults(res, surname, l1, l2, fate) {
    const box = $('#results');
    if (!res.length) { box.innerHTML = '<p class="hint">沒有符合條件的組合，請放寬嚴格度或字集。</p>'; return; }
    box.innerHTML = res.map((c, i) => card(c, i, surname, l1, l2)).join('');
    box.querySelectorAll('.card').forEach((el, i) => el.addEventListener('click', (ev) => {
      if (ev.target.closest('.detail')) return;
      const c = res[i];
      const d = el.querySelector('.detail');
      if (d) { d.remove(); return; }
      const r = Nova.rating.rateName(l1, l2, c.c1, c.c2, fate);
      el.insertAdjacentHTML('beforeend', detailHtml(r, c.c1, c.c2));
    }));
  }

  function card(c, i, surname, l1, l2) {
    const g = c.combo.ge;
    return `<article class="card" tabindex="0">
      <div class="head"><span class="rank">${i + 1}</span><span class="name">${esc(surname + c.c1.char + c.c2.char)}</span>
        <span class="py">${esc(c.c1.py[0])} ${esc(c.c2.py[0])}</span>
        <span class="total">${c.total.toFixed(1)} <span class="badge g-${esc(c.grade)}">${esc(c.grade)}</span></span></div>
      <div class="bars">${DIMS.map(([n], k) => `<span class="bar">${n} ${Math.round(c.scores[k])}<i><b style="width:${c.scores[k]}%"></b></i></span>`).join('')}</div>
      <div class="meta"><span>筆畫 ${l1}${l2 ? '+' + l2 : ''}+${c.combo.f1}+${c.combo.f2}</span><span>五格 ${g.tian}/${g.ren}/${g.di}/${g.wai}/${g.zong}</span>
        <span>三才 ${esc(c.combo.sancaiKey)}</span><span>${wxTag(c.c1.wx)}${wxTag(c.c2.wx)}</span></div>
    </article>`;
  }

  function detailHtml(r, c1, c2) {
    const S = Nova.sancai, W = Nova.wuge, D = Nova.dayan, g = r.ge;
    const geItems = g ? [['天格', g.tian], ['人格', g.ren], ['地格', g.di], ['外格', g.wai], ['總格', g.zong]].map(([n, v]) => {
      const dy = D.find(v);
      return `<div><small>${n}</small><span class="n">${v}</span><small class="lucky-${esc(dy.lucky)}">${esc(dy.title)}・${esc(dy.lucky)}</small><small>${W.yinyangOf(v)}${W.elementOf(v)}</small></div>`;
    }).join('') : '';
    const ren = g ? W.elementOf(g.ren) : '';
    return `<div class="detail">
      <div class="charinfo">${[c1, c2].map((c) => `<div><span class="c">${esc(c.char)}</span>${esc(c.py.join(' / '))}・${c.stroke}畫・${wxTag(c.wx)}<br><span class="dim">${esc(c.meaning || '（無釋義）')}</span></div>`).join('')}</div>
      ${g ? `<h4>五格</h4><div class="ge">${geItems}</div>
      <p class="dim">${g ? [['天格', g.tian], ['人格', g.ren], ['地格', g.di], ['外格', g.wai], ['總格', g.zong]].map(([n, v]) => `${n}：${esc(D.find(v).comment)}`).join('<br>') : ''}</p>
      <h4>三才 ${esc(r.sancaiKey)}・${esc(S.verdict(r.sancaiKey))}</h4>
      <p>${esc(S.detail(r.sancaiKey))}</p>
      <p><b>基礎運</b> ${esc(S.jichu(ren, W.elementOf(g.di)))}<br><b>成功運</b> ${esc(S.chenggong(ren, W.elementOf(g.tian)))}<br><b>人際</b> ${esc(S.renji(ren, W.elementOf(g.wai)))}</p>` : ''}
      <h4>評分明細</h4>
      ${DIMS.map(([n, k]) => `<p><b>${n} ${r[k]}</b> <span class="dim">${esc((r.details[k] || []).join('；') || '—')}</span></p>`).join('')}
    </div>`;
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
    const r = Nova.rating.rateName(l1, l2, c1, c2, fate);
    const c = { c1, c2, combo: { ge: r.ge, f1: c1.stroke, f2: c2.stroke, sancaiKey: r.sancaiKey }, scores: [r.wenhua, r.wuxing, r.shengxiao, r.wuge, r.yinyun], total: r.total, grade: r.grade };
    $('#results').innerHTML = card(c, 0, s.surname, l1, l2) + '';
    $('#results .card').insertAdjacentHTML('beforeend', detailHtml(r, c1, c2));
    setBusy(false, '');
  }

  // ---------------------------------------------------------------- URL 參數（測試與分享）
  function buildQuery(surname) {
    const p = new URLSearchParams();
    p.set('surname', surname);
    if ($('#born-date').value) p.set('born', $('#born-date').value + ($('#hour-unknown').checked || !$('#born-time').value ? '' : 'T' + $('#born-time').value));
    p.set('gender', $('#gender').value);
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
    if (p.get('gender')) $('#gender').value = p.get('gender');
    for (const k of ['level', 'strictness', 'method', 'topn', 'perfirst', 'avoid', 'require']) if (p.get(k) != null) $('#' + k).value = p.get(k);
    if (p.get('first')) $('#fixed-first').value = p.get('first');
    if (p.get('second')) $('#fixed-second').value = p.get('second');
    if (p.get('explain')) { $('#explain-name').value = p.get('explain'); return 'explain'; }
    return p.get('auto') !== '0' ? 'generate' : false;
  }

  // ---------------------------------------------------------------- init
  function init() {
    $('#form').addEventListener('submit', onGenerate);
    $('#explain-form').addEventListener('submit', onExplain);
    $('#surname').addEventListener('input', readSurname);
    $('#gender').addEventListener('change', () => { $('#female-caution').checked = $('#gender').value === 'girl'; });
    $('#hour-unknown').addEventListener('change', () => { $('#born-time').disabled = $('#hour-unknown').checked; });
    $('#female-caution').checked = $('#gender').value === 'girl';
    const d = Nova.chars.data();
    $('#version').textContent = `字典 ${d.map.size} 字（${d.generated}）・lunar-javascript・Nova 0.1`;
    const mode = applyQuery();
    if (mode === 'explain') { readSurname(); onExplain(new Event('submit')); }
    else if (mode === 'generate') { readSurname(); onGenerate(); }
  }
  document.addEventListener('DOMContentLoaded', init);
})();
