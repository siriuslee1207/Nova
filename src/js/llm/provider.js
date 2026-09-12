// LLM 供應商介面與設定（對應 nova_core/llm/base.py）。key 預設只留記憶體；勾選「記住」才進 sessionStorage。
(function (Nova) {
  'use strict';
  const STORE_KEY = 'nova.llm.v1';
  const DEFAULTS = { provider: 'gemini', model: 'gemini-3.5-flash-lite', apiKey: '', remember: false, thinking: 'auto' };
  const settings = Object.assign({}, DEFAULTS);
  try {
    const saved = sessionStorage.getItem(STORE_KEY);
    if (saved) Object.assign(settings, JSON.parse(saved), { remember: true });
  } catch (_) { /* storage unavailable */ }

  function save() {
    try {
      if (settings.remember) sessionStorage.setItem(STORE_KEY, JSON.stringify(settings));
      else sessionStorage.removeItem(STORE_KEY);
    } catch (_) { /* ignore */ }
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
