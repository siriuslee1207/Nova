// 預設使用者範本：開網頁時若沒有網址參數、也沒有上次留下的條件，就自動帶入並直接產生；「套用範本」按鈕可隨時帶回。
// 要換範本改這裡即可（bornDate 為估計值，出生後在畫面上改成實際日期與時間）。
(function (Nova) {
  'use strict';
  Nova.template = {
    label: '李家男寶（2026 馬年 10 月）',
    surname: '李',
    gender: 'boy',
    bornDate: '2026-10-15',
    bornTime: '',
    hourUnknown: true,
    prefs: '男寶寶，2026 馬年 10 月出生。請提供一些我們可能會喜歡的用字：字義正向、好念好寫、不太俗也不冷僻，並簡短說明為何適合屬馬的孩子。',
    note: '已套用範本：出生日期先以 10 月中估算、勾了時辰不詳；寶寶出生後請改成實際日期與時間，再按「產生名字」。',
  };
})(globalThis.Nova = globalThis.Nova || {});
