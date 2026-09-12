# M0 Spike 紀錄（2026-09-03）

## 環境
- Python 3.14.2（venv：lunar_python 1.4.8 MIT、pytest 9.1、opencc-python-reimplemented 0.1.7 Apache-2.0）
- git 2.41、node 24.14、curl 8.1；Edge/Chrome 可用（headless `--dump-dom` 驗證 `file://`）
- lunar-javascript 1.7.7（MIT，UMD，全域 `Solar/Lunar/EightChar`，436 KB 未壓縮）

## `file://` 實測（spike/file_test.html，Edge headless）
| 項目 | 結果 |
|---|---|
| `sessionStorage` / `localStorage` | 可用 |
| Blob Worker（`new Worker(URL.createObjectURL(new Blob([...])))`） | 可用，往返 24.6 ms |
| lunar.js classic script | 可用；2026-09-03 10:30 → 丙午 丙申 庚辰 辛巳；2026-02-03→02-04 月柱由己丑切庚寅（立春，節氣正確） |
| Gemini `generateContent` / `streamGenerateContent?alt=sse`，`Origin: null` | **CORS 放行**：收到 HTTP 401 JSON（假 key）。只送 `Content-Type` + `x-goog-api-key` |
- lunar.js 輸出為簡體（马、处暑、白蜡金）→ `bazi.js` 需以索引對照繁體詞表。

## fate `character.json`（30,060 筆）品質
- `common_level`、`gender_hint` 全空；`regular` 僅 3,768 字（陳 無、陈 有）→ 旗標不可用於繁體常用判斷。
- `is_variant` 錯標常用字（俊/萱/浩/然）；`歐` 無 `is_traditional`。
- `science_stroke` 對繁體字系統性錯誤（陳 18 應 16、陽 19 應 17；簡體 陈 16、阳 17 反而正確）→ **棄用**。
- `kangxi_stroke` 對簡繁同形字被錯誤還原（余 15 應 7、曲 19、岳 17、台 14、合 14、云 12、系 19）、另有零星錯誤（泛 6 應 9、回 5、吊 4、王 5 應 4）。
- 拼音全為調號形式（無數字調）；字義平均 33 字，約 30% 為 Unihan 英文釋義，其餘為簡體新華字典文字。
- Big5 常用區 5,401 字中缺 88 字（含 謝、藝、陣、極、詩、試、遠、錢、銀…），次常用區缺 288 字。

## Unihan（最新版，Unicode License）
- 已無 `kRSKangXi`；用 `kRSUnicode` 部首序號→康熙部首筆畫（1–6:1 … 214:17）+ 餘筆 推算。
- 與 fate `kangxi_stroke` 在 Big5 常用字上 95.6% 一致；不一致 236 字多為 fate 錯。
- Unihan 依字形計餘筆，與康熙不同的少數例外（成 6 vs 7、求、些）放 `data/tables/stroke_overrides.json`；成-系列在 Unihan 內部亦不一致（晟 用 7、誠/盛/城 用 6）。
- 缺字 88 個全部有 `kRSUnicode`/`kMandarin`/`kDefinition`。

## 決策
1. **筆畫**：Unihan 部首+餘筆 → overrides（數字字、康熙特例）→ 缺值退回 fate `kangxi_stroke`。ETL 報表列出所有 Unihan≠fate 之字供人工檢視。
2. **常用等級**：Python 內建 `big5` codec：A440–C67E → 1（常用）、C940–F9D5 → 2（次常用）、其他 → 3。`regular := lvl==1`。
3. **字集**：以 Big5 常用+次常用為全集，排除 `simplified_of_char≠自身` 的純簡體字；缺字由 Unihan 補（拼音、筆畫、英文釋義；五行以部首→五行規則，否則數理五行，標記 `src=unihan`）。
4. **文字轉換**：OpenCC `s2twp` + 後修正（生髮→生發）。姓氏簡→繁對照：Unihan `kTraditionalVariant` 有值且該字不在 Big5 常用區者，取 OpenCC `s2tw` 結果（避免 于→於、干→幹、后→後）。
5. **拼音**：ETL 轉數字調（`hào`→`hao4`，輕聲不加數字）；韻母比較前去掉調號數字。
6. **LLM**：Gemini 走瀏覽器直連 BYOK；Copilot 只走官方 SDK/CLI（見計畫）。

## 2026-09-04 驗證紀錄
- Python/JS parity：`tests/parity.mjs` 550/550（八字 34、評分 500、筆畫組合 6、完整產生 10）；瀏覽器 `tests/parity.html`（file://）同樣全過。
- JS 產生耗時（node）：預設 104 ms；次常用字集＋寬鬆＋top 100 約 1 s → UI 用 `generateAsync` 分批讓出主執行緒。
- `dist/nova.html` 1.2 MB，`file://` 下以 `?surname=陳&born=…` 自動執行成功；Edge headless 截圖版面正常。
- Gemini adapter 以假 key 從 `file://` 實測：`generateContent` 與 `streamGenerateContent` 皆收到 401 JSON 並轉成可讀錯誤（CORS 放行）；`AIza` 前綴警示正確。**尚未以真 key 驗證成功路徑**（需使用者自備 key）。
- 本機無 `copilot` CLI／`gh`，Copilot provider 依官方 SDK 文件撰寫，未實測（2026-09-12 已補實測，見下節）。
- 資料品質決策補充：`kFrequency` 在 Unihan 17.0 已不存在，`kGradeLevel` 僅涵蓋 48% 且遺漏大量名字用字，故常用等級改由 `name_common.json`（可編輯）定義第 1 級。

## 2026-09-12 Copilot provider 實測
- `github-copilot-sdk` 1.0.11 會自動下載 pinned 的 CLI runtime 1.0.79（159 MB，約 6 秒）到 `%LOCALAPPDATA%\github-copilot-sdk\cli\1.0.79\copilot.exe`，不需 PATH 上有 copilot；`copilot.exe login`（瀏覽器 OAuth，token 進 Windows 憑證庫）後 SDK `auth.getStatus` 回 authenticated，`models.list` 列出 16 個模型（gpt-5-mini 單價最低，reasoning 支援 low/medium/high；gpt-5.4-mini 另支援 none）。
- SDK 的 `mode="empty"` 不能用：它會對 runtime 設 `COPILOT_DISABLE_KEYTAR=1`，讀不到憑證庫裡的登入（即使 `base_directory` 指回 `~/.copilot` 也一樣，且未登入時 `list_models` 直接拋錯）。改在預設模式下逐項關閉：`available_tools=[]`、`system_message={'mode': 'replace'}`、`skip_custom_instructions=True`、`enable_session_store=False`、`memory={'enabled': False}`、`enable_skills=False`。
- 未登入時事件序列為 SessionErrorData → AssistantIdleData → SessionIdleData，舊版 provider 只等 idle 會回空字串；現在收到 SessionErrorData 就拋 RuntimeError。模型名稱錯誤在 `session.create` 就被拒（`Model "x" is not available`）。SDK 版本漂移（ImportError/AttributeError/TypeError）才退回 CLI 子程序，CLI 路徑優先 PATH、其次 SDK 快取。
- 端到端（gpt-5-mini，reasoning low）：`--ai explain` 12.5 s、逐字串流；`--ai recommend` 29 s，8/8 推薦通過 Nova 驗證。每次呼叫都重新啟動 runtime（約 0.4 s），`generate_json` 重試時會啟動第二次。
- 網頁端移除 Copilot 選項（原為 browser:false 佇位，選了只會顯示說明，反而讓人找 API key）；API key 與模型設定改為自動存 localStorage（原本勾「記住」才進 sessionStorage）。file:// 下所有本機頁面共用同一 origin，已在 README 註明。
- Gemini `models.list`（GET v1beta/models）從 file:// 直連可行：預檢 200、Access-Control-Allow-Headers 含 x-goog-api-key、Allow-Origin: null；假 key 回 401 UNAUTHENTICATED JSON。網頁端貼 key 後自動抓清單，只留 `gemini-*` 且支援 generateContent，排除 tts／image／audio／live／embedding／robotics／computer-use；成功路徑仍需真 key 驗證。

## 2026-09-12 三才吉凶表（謝達輝）與 36 吉數匯入（筆畫組合選字）
- 來源：中國五術大學 謝達輝姓名學研究所 http://www.cdi.org.tw/name/n-3-gold.html 及 n-3-wood/fire/earth/water（Big5，只有 HTTP，WebFetch 升 HTTPS 會被拒，改 curl）。解析五頁的「組別／天格／人格／地格／吉凶」表得 125 組 → `data/tables/sancai_cdi.json`。等級分佈：最吉 16／吉 9／平吉 12／半吉 2（木火火、水木火）／凶 67／最凶 19；`no` = 25×天＋5×人＋地＋1（木火土金水序）。同站「81劃論吉凶」為 吉／吉帶凶／凶帶吉／凶 四級（吉 34 個），與 fate 表大致相同但把 8、17、18、25、39、73 列為吉、57 凶帶吉、61 吉帶凶；未採用。
- 與 fate sancai125 交叉比對：16 個最吉全是 fate 大吉；但 cdi 凶含 6 個 fate 大吉、9 個 fate 中吉，兩表確實不同 → 新模式以 cdi 過濾、fate 只作對照並列顯示，`rate_wuge` 評分不變。
- 36 吉數（使用者指定）= fate 的 30 個「吉」＋ fate 列「半吉」的 8、17、18、25、39、55（73 不在內；無任何 fate 凶數）→ `data/tables/jishu36.json`，`dayan.is_jishu(n)` 與 `find` 同法循環。
- 合格組合數（最吉＋吉、五格含天格皆吉數）：陳 16、李 16、王 41、黃 33、劉 28、蔡 12、歐陽 21、司徒 32、張簡 4；加平吉／半吉多約 20–50%。天格非吉數的常見姓：林(9)、張(12)、楊(14)、許(12)、鄭(20)、周(9)、莊(14)、蕭(19)、戴(19) → 預設 0 組，取消天格後 3–19 組；UI／CLI 都提示並可一鍵去掉天格。
- 決策：篩選鏈獨立成 `nova_core/combos.py` ↔ `src/js/core/combos.js`（`enumerate_combos`，f1、f2 升冪），`generator.lucky_combos` 與既有 parity 案例不動；parity 新增 `combo_table` 7 案（含 林 天格不吉→0 列、取消天格→14 列）。UI 過濾條件存 `nova.combos.v1`。

## 2026-09-13 吉數等級（筆畫組合選字的第三層條件）
- 需求：原本「吉數」只有在不在 36 吉數的二分法，改成可依等級（大吉／吉／半吉…）篩選。fate `dayan81` 只有 吉／半吉／凶（`max_luck` 實際只有 41），沒有「大吉」這一級 → 需要第二個來源。
- 來源：同站 http://www.cdi.org.tw/name/n-81.html「姓名81劃吉凶分類表」（Big5、只有 HTTP，curl 取回；2026-09-12 的筆記已看過但未採用）。解析兩個吉凶標示欄得四級：吉 34／吉帶凶 15／凶帶吉 4／凶 28，與該頁自述的「吉 49（全吉 34、吉中帶凶 15）、凶 32（全凶 28、凶中帶吉 4）」一致 → 存成 `data/tables/jishu_grade.json` 的 `cdi` 欄。
- 使用者選定的分級（兩表合併五級，`grade` 欄）：大吉＝fate 吉且 cdi 吉（28）；吉＝36 吉數其餘（8：8 17 18 25 39 55 57 61）；半吉＝非吉數但 fate 半吉且 cdi 吉／吉帶凶（6：30 50 51 71 73 77）；半凶＝其餘 fate 半吉或 cdi 吉帶凶／凶帶吉（14）；凶＝兩表皆凶（25）。**大吉＋吉 恰為 36 吉數**，所以新條件與舊條件可並存（build_tables 與 pytest 都斷言這件事）。
- 條件語意（使用者選「再加一條 AND」）：吉數仍只看勾選的格（可含天格），等級只看人、地、外、總四格（`GRADE_GRIDS`）；預設五級全勾＝不限制，預設結果與加這條之前完全相同（parity 舊案例數字未變）。
- 天格撇除（使用者第二輪要求）：天格由姓氏決定、改不了，一開始把它也納入等級條件會讓常見姓整份落空（陳 天格 17 是「吉」不是「大吉」→ 只勾大吉 0 組），改成不計後同一條件有 1 組；天格等級仍在天格徽章、五格卡與 CLI 明細標出供參考。連帶移除原本的「勾回 X 等級」提示與 `enumerate_combos` 的天格等級短路。
- 效果：王 41 → 大吉 11 組、陳 16 → 1 組；李（grids 只留人地、等級去掉凶）23 組中有 7 組含非吉數的格，林（不勾任何格、等級留大吉/吉/半吉）18 組全部天格為凶 → 兩條件確實獨立、天格確實不受等級管。parity `combo_table` 7 → 11 案、每列多比五格等級字串，`node tests/parity.mjs` 595/595 通過；Edge headless 在 `file://` 實測 UI：等級 chip 改選會即時重算。
