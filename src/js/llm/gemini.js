// Google AI Studio / Gemini API adapter：raw fetch + SSE，只送 Content-Type 與 x-goog-api-key（多送任何標頭預檢會 403）。
// 從 file://（Origin: null）直連可行（見 docs/spike-notes.md）。
(function (Nova) {
  'use strict';
  const BASE = 'https://generativelanguage.googleapis.com/v1beta/models/';

  function keyWarning(key) {
    if (!key) return '請貼上你自己的 Gemini API key（AI Studio 建立）；key 只從你的瀏覽器直送 Google。';
    if (key.startsWith('AIza')) return '這是舊式 standard key（AIza 開頭）；Gemini 自 2026-09 起拒絕此類 key，請到 AI Studio 建立新的 key（AQ. 開頭）。';
    return '';
  }

  // 3.7/3.8 flash 只接受 MEDIUM/HIGH；lite 與 2.5/3.5/3.6 可用 LOW。auto → 對輕量模型用 LOW，其餘交給模型預設。
  function thinkingConfig(model, thinking) {
    if (thinking && thinking !== 'auto') return { thinkingLevel: thinking };
    if (/flash-lite|3\.5-flash|3\.6-flash|2\.5-/.test(model)) return { thinkingLevel: 'LOW' };
    return null;
  }

  function body(model, system, user, json, schema, thinking) {
    const gc = { maxOutputTokens: 8192 };
    const tc = thinkingConfig(model, thinking);
    if (tc) gc.thinkingConfig = tc;
    if (json) { gc.responseMimeType = 'application/json'; if (schema) gc.responseJsonSchema = schema; }
    return { system_instruction: { parts: [{ text: system }] }, contents: [{ role: 'user', parts: [{ text: user }] }], generationConfig: gc };
  }

  async function toError(res) {
    let text = '', err = null;
    try { text = await res.text(); err = JSON.parse(text).error; } catch (_) { /* non-JSON */ }
    const reason = err && Array.isArray(err.details) ? err.details.map((d) => d.reason).filter(Boolean).join(',') : '';
    let msg = 'Gemini HTTP ' + res.status + (err ? ' ' + (err.status || '') + ': ' + (err.message || '') : '');
    if (reason === 'API_KEY_INVALID') msg = 'API key 無效（400 API_KEY_INVALID）。請確認貼上的是 AI Studio 的新式 key。';
    else if (res.status === 429) {
      msg = /per day|daily|PerDay|RPD/i.test((err && err.message) || '')
        ? '已達此模型的每日請求上限（RPD），要等到太平洋時間午夜才重置；可改用其他模型（如 gemini-3.5-flash-lite）。'
        : '請求過於頻繁（RPM），請等幾秒再試。';
    } else if (res.status === 404) msg = '模型名稱不存在：' + (err ? err.message : '');
    const e = new Error(msg); e.status = res.status; e.reason = reason; e.body = text;
    return e;
  }

  async function request(settings, path, payload, signal) {
    const res = await fetch(BASE + encodeURIComponent(settings.model) + path, {
      method: 'POST', signal,
      headers: { 'Content-Type': 'application/json', 'x-goog-api-key': settings.apiKey },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw await toError(res);
    return res;
  }

  // SSE：每個 data: 是完整 GenerateContentResponse；無 [DONE]，串流關閉即結束；略過 thought 部分。
  async function streamText({ settings, system, user, onDelta, signal }) {
    const res = await request(settings, ':streamGenerateContent?alt=sse', body(settings.model, system, user, false, null, settings.thinking), signal);
    const reader = res.body.pipeThrough(new TextDecoderStream()).getReader();
    let buf = '', text = '', usage = null, finish = null;
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buf += value;
      let i;
      while ((i = buf.indexOf('\n\n')) !== -1) {
        const frame = buf.slice(0, i); buf = buf.slice(i + 2);
        const line = frame.split('\n').find((l) => l.startsWith('data:'));
        if (!line) continue;
        let chunk;
        try { chunk = JSON.parse(line.slice(5).trim()); } catch (_) { continue; }
        if (chunk.promptFeedback && chunk.promptFeedback.blockReason) throw new Error('提示被封鎖：' + chunk.promptFeedback.blockReason);
        if (chunk.usageMetadata) usage = chunk.usageMetadata;
        const cand = chunk.candidates && chunk.candidates[0];
        if (cand && cand.finishReason) finish = cand.finishReason;
        for (const p of (cand && cand.content && cand.content.parts) || []) {
          if (p.thought || !p.text) continue;
          text += p.text;
          if (onDelta) onDelta(p.text, text);
        }
      }
    }
    if (finish && finish !== 'STOP' && finish !== 'MAX_TOKENS') throw new Error('生成中止：' + finish);
    return { text, usage, finishReason: finish };
  }

  async function generateJson({ settings, system, user, schema, signal }) {
    const res = await request(settings, ':generateContent', body(settings.model, system, user, true, schema, settings.thinking), signal);
    const data = await res.json();
    const cand = data.candidates && data.candidates[0];
    if (!cand) throw new Error('沒有回應內容' + (data.promptFeedback ? '：' + JSON.stringify(data.promptFeedback) : ''));
    if (cand.finishReason && cand.finishReason !== 'STOP') throw new Error('生成未完整（' + cand.finishReason + '），請重試或換模型');
    const text = ((cand.content && cand.content.parts) || []).filter((p) => !p.thought).map((p) => p.text || '').join('');
    let parsed;
    try { parsed = JSON.parse(text); } catch (e) { throw new Error('回應不是有效 JSON：' + text.slice(0, 200)); }
    return { data: parsed, raw: text, usage: data.usageMetadata };
  }

  Nova.llm.register({ id: 'gemini', label: 'Google Gemini（AI Studio）', browser: true, defaultModel: 'gemini-3.5-flash-lite',
    keyWarning, streamText, generateJson });
  Nova.llm.register({ id: 'copilot', label: 'GitHub Copilot（僅 Python CLI）', browser: false, defaultModel: '',
    note: 'GitHub Copilot 的官方程式介面是本機 Copilot SDK/CLI，瀏覽器無法直接呼叫；請用 python -m nova_core.cli … --ai --provider copilot。',
    keyWarning: () => '' });
})(globalThis.Nova = globalThis.Nova || {});
