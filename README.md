# Nova — 小孩取名

繁體中文取名工具。命名規則與五維評分移植自 [fate](https://github.com/babyname/fate)（MIT）——
五格數理、八十一數理、三才配置、八字喜用五行、生肖、音韻——並修正其已知問題、以臺灣資料重建字典。

- **執行**：單一 `dist/nova.html`，雙擊即用、完全離線、資料不離開電腦。
- **建置**：Python 負責資料 ETL、常數表、打包、參考實作、測試與 CLI。
- **AI 顧問（選用）**：Gemini（AI Studio，瀏覽器直連 BYOK）／GitHub Copilot（官方 SDK，僅 CLI）。AI 只能從 Nova 已通過五格／三才篩選的字池中挑字，分數一律由 Nova 計算。

## 使用

雙擊 `dist/nova.html`，輸入姓氏、性別、出生日期時間（可勾「時辰不詳」），按「產生名字」。
點結果卡片展開五格、三才、評分明細；「單一名字評分」可直接評自己想的名字。
可用網址參數預填並自動執行，例如 `nova.html?surname=陳&born=2026-09-03T10:30&gender=girl` 或 `…&explain=冠宇`。

AI 顧問：在左側貼上你自己的 Gemini API key（AI Studio 建立；新式 key 以 `AQ.` 開頭，舊式 `AIza` 已被 Google 停用），
按「AI 推薦用字」，或在卡片明細中按「AI 解說」。key 由瀏覽器直接送到 Google，不經任何中間伺服器；
勾「記住」才會存在本分頁的 sessionStorage。免費層每日請求數有限，預設模型 `gemini-3.5-flash-lite`，可自行更換。

## 命令列

```powershell
.venv\Scripts\python -m nova_core.cli 陳 --born 2026-09-03T10:30 --gender girl --top 12
.venv\Scripts\python -m nova_core.cli 歐陽 --gender boy --level 1 --first 承
.venv\Scripts\python -m nova_core.cli 陳 --born 2026-09-03T10:30 --explain 冠宇
.venv\Scripts\python -m nova_core.cli 陳 --born 2026-09-03T10:30 --ai recommend --provider gemini     # 需 GEMINI_API_KEY
.venv\Scripts\python -m nova_core.cli 陳 --born 2026-09-03T10:30 --explain 冠宇 --ai explain --provider copilot
.venv\Scripts\python -m nova_core.cli 陳 --born 2026-09-03T10:30 --ai recommend --ai-dump              # 只印提示，不呼叫
```

Copilot 走官方 `github-copilot-sdk`（或 PATH 上的 `copilot` CLI），沿用你已登入的 Copilot 訂閱；
Nova 不使用 IDE 內部端點（無公開文件且有帳號停權案例）。

## 開發

```powershell
python -m venv .venv
.venv\Scripts\pip install -e ".[dev,build,bazi]"        # 另可加 gemini / copilot
.venv\Scripts\python tools\fetch_source.py             # 下載 fate character.json 與 Unihan.zip 到 data/raw/
.venv\Scripts\python tools\build.py --fixtures         # tables → chars → prompts → golden → dist/nova.html
.venv\Scripts\python -m pytest                         # Python 參考實作
node tests\parity.mjs                                  # 或雙擊 tests\parity.html：JS 與 Python 逐位一致
```

`tools/transcribe_fate.py` 從 `ref/fate/` 的 Go 原始碼重新產生常數表（需先 `curl` 下載，見 `docs/spike-notes.md`）。

## 目錄

| 路徑 | 內容 |
|---|---|
| `data/tables/` | 常數表（單一真相來源）：八十一數理、三才 125 組與解析、八字表、筆畫特例、常見取名用字、排除字、字義覆蓋 |
| `data/prompts/` | LLM 提示模板（Python 直讀，build 內嵌 JS） |
| `data/gen/` | 建置產物：`chars.json`/`chars.gen.js`、`tables.gen.js`、`prompts.gen.js`、`etl_report.md` |
| `nova_core/` | Python 參考實作、CLI、`llm/`（gemini、copilot、advisor） |
| `src/` | 前端：`js/core/*`（與 Python 對應的模組）、`js/llm/*`、`ui.js`、`vendor/lunar.js` |
| `tools/` | ETL、轉錄、fixture、打包 |
| `tests/` | pytest；`parity_core.js` + `parity.mjs`/`parity.html` |
| `docs/spike-notes.md` | 資料品質、環境驗證與決策紀錄 |

## 與 fate 的差異

- 修正：五格「半吉」分支永遠走不到、聲調判斷對調號拼音失效、三才「中吉」等級缺漏導致永遠被過濾、`金金火` 缺項、喜用神方法切換不影響評分。
- 資料：以 Big5 常用／次常用字為全集（純簡體字自動轉繁）；筆畫改用 Unihan 康熙部首＋餘筆並加姓名學特例（數字字、成 7 等）；拼音以臺灣讀音為主並轉數字調；字義以 OpenCC 轉臺灣正體並人工修正常用字；常用等級分三級（常見取名用字／常用／次常用），數字與虛詞預設不入候選。
- 新增：時辰不詳模式、同一首字次數上限、指定輩字、姓氏筆畫可手動覆寫、Python/JS 一致性測試、AI 顧問。
- 五行分數以十分之一整數累加，避免浮點雜訊影響強弱判斷。

分數僅供參考。授權 MIT（`LICENSE`），第三方見 `NOTICE`。
