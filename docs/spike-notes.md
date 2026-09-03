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
- 本機無 `copilot` CLI／`gh`，Copilot provider 依官方 SDK 文件撰寫，未實測。
- 資料品質決策補充：`kFrequency` 在 Unihan 17.0 已不存在，`kGradeLevel` 僅涵蓋 48% 且遺漏大量名字用字，故常用等級改由 `name_common.json`（可編輯）定義第 1 級。
