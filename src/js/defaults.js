// 「給 AI 的偏好」的預設範本文字：第一次開網頁時自動填入欄位；使用者改過的文字會記在瀏覽器，欄位旁的「範本」可隨時帶回。
// 只影響送給 AI 的偏好說明，不會動姓氏、性別、出生時間。要換範本改這裡即可。
(function (Nova) {
  'use strict';
  Nova.template = {
    prefs: '小寶寶姓李，是個男孩，生肖屬馬，10 月生，請提供一些可能會喜歡的用字。',
  };
})(globalThis.Nova = globalThis.Nova || {});
