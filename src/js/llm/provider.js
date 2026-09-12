// LLM 供應商介面與設定（對應 nova_core/llm/base.py）。設定（含 API key）自動存在 localStorage，清空欄位即移除；
// 注意 file:// 頁面共用同一個 origin，同一瀏覽器開的其他本機 HTML 也讀得到。
(function (Nova) {
  'use strict';
  const STORE_KEY = 'nova.llm.v1';
  const DEFAULTS = { provider: 'gemini', model: 'gemini-3.5-flash-lite', apiKey: '', thinking: 'auto' };
  const settings = Object.assign({}, DEFAULTS);
  try {
    const saved = localStorage.getItem(STORE_KEY);
    if (saved) Object.assign(settings, JSON.parse(saved));
  } catch (_) { /* storage unavailable */ }

  function save() {
    try { localStorage.setItem(STORE_KEY, JSON.stringify(settings)); } catch (_) { /* ignore */ }
  }
  function set(partial) { Object.assign(settings, partial); save(); return settings; }

  const providers = {};
  function register(p) { providers[p.id] = p; }
  function current() { return providers[settings.provider]; }

  // {{var}} 模板渲染；模板來自 NOVA_PROMPTS（data/prompts/*.md）
  function render(name, vars) {
    const t = globalThis.NOVA_PROMPTS && globalThis.NOVA_PROMPTS[name];
    if (!t) throw new Error('缺少提示模板 ' + name);
    return t.replace(/\{\{(\w+)\}\}/g, (_, k) => (vars[k] == null ? '' : String(vars[k])));
  }

  function ensureReady() {
    const p = current();
    if (!p) throw new Error('未知的供應商 ' + settings.provider);
    if (!settings.apiKey) throw new Error('請先貼上 API key');
    return p;
  }
  function streamText(opts) { return ensureReady().streamText(Object.assign({ settings }, opts)); }
  function generateJson(opts) { return ensureReady().generateJson(Object.assign({ settings }, opts)); }

  Nova.llm = { DEFAULTS, settings: () => settings, set, providers, register, current, render, streamText, generateJson };
})(globalThis.Nova = globalThis.Nova || {});
