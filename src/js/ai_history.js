// AI 推薦的歷史紀錄：每次按「AI 推薦用字」記一筆（條件、偏好、模型、結果），存 localStorage，最多 MAX 筆，新的在前。
// 與最新一筆條件、偏好完全相同的重問只更新那一筆，不重複記。純資料層，畫面在 ui.js。
(function (Nova) {
  'use strict';
  const KEY = 'nova.ai.history.v1', MAX = 30;
  let items = [];
  try {
    const raw = localStorage.getItem(KEY);
    if (raw) items = JSON.parse(raw);
  } catch (_) { /* storage unavailable or corrupt */ }
  if (!Array.isArray(items)) items = [];

  function save() {
    try { localStorage.setItem(KEY, JSON.stringify(items)); } catch (_) { /* ignore */ }
  }
  function list() { return items.slice(); }
  function sameAsk(a, b) {
    return a.surname === b.surname && a.gender === b.gender && a.born === b.born && a.prefs === b.prefs;
  }
  function add(entry) {
    const t = new Date().toISOString();
    if (items[0] && sameAsk(items[0], entry)) {
      Object.assign(items[0], entry, { t, result: null, error: '' });
      save();
      return items[0].id;
    }
    const id = Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
    items.unshift(Object.assign({ id, t, result: null, error: '' }, entry));
    if (items.length > MAX) items.length = MAX;
    save();
    return id;
  }
  function update(id, patch) {
    const it = items.find((x) => x.id === id);
    if (it) { Object.assign(it, patch); save(); }
    return it;
  }
  function remove(id) { items = items.filter((x) => x.id !== id); save(); }
  function clear() { items = []; save(); }

  Nova.aiHistory = { list, add, update, remove, clear, MAX };
})(globalThis.Nova = globalThis.Nova || {});
