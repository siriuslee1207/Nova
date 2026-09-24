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

### 在手機上使用

iPhone／iPad 在「檔案」App 裡直接點開 `nova.html` **不會動**：iOS 用「快速查看」預覽 HTML，版面畫得出來、但完全不執行 JavaScript，
所以按「產生名字」沒有任何反應。這種情況頁面最上方會出現紅色提示說明原因（提示由 CSS 控制，JavaScript 一跑起來就消失）。四條可用的路：

1. **從電腦分享給手機（最穩）**：電腦上跑 `.venv\Scripts\python tools\serve.py`，它會印出像 `http://192.168.1.23:8000/nova.html` 的網址；
   手機連同一個 Wi-Fi、用瀏覽器開即可，Safari 分享選單的「加入主畫面」可以把它變成像 App 的圖示。
   第一次執行 Windows 防火牆會詢問，要允許「私人網路」。頁面仍是純靜態、運算全在手機上，只有 AI 顧問會從手機直接連 Google。
2. **iPhone 本機開**：「檔案」App 長按 `nova.html` → 分享 → 選 Safari（「拷貝到 Safari」），在 Safari 裡 JavaScript 才會執行；iOS 版本不同可能沒有這個選項。
3. **Android**：用 Chrome 開，網址列輸入 `file:///sdcard/Download/nova.html`。
4. **線上版**：把同一份檔案放到 GitHub Pages（見下），手機在任何網路下開網址即可，不必跟電腦同一個 Wi-Fi。

手機版面是單欄；輸入框字級固定 16px（更小的話 iOS 聚焦時會自動放大整頁），字表與筆畫組合的點擊目標加大。
手機沒有滑鼠可停留看 `title`，所以「筆畫組合選字」改成：點到的字會把拼音、五行與字義寫在字表下方。
另外未攔截的錯誤會直接印在頁面最上方（手機沒有主控台可看）。

### 線上版（GitHub Pages）

`docs/` 就是 GitHub Pages 的站台根目錄：`docs/index.html` 是 `dist/nova.html` 的複本（本機建好、驗證過的那一份），
`docs/nova.html` 只是把舊網址 `nova.html?…` 原樣轉到首頁，`docs/.nojekyll` 要求 GitHub 原封不動送檔、不要跑 Jekyll。
發佈就是三步：

```
.venv\Scripts\python tools\build.py       # src/ 或 data/ 改過才需要
.venv\Scripts\python tools\publish.py     # dist/nova.html → docs/index.html（會擋住忘了重 build 的情況）
git add docs/index.html && git commit -m "publish 線上版" && git push
```

GitHub 上只要設定一次：Settings → Pages → Source 選 **Deploy from a branch**、Branch `main`、資料夾 `/docs`。
網址是 <https://siriuslee1207.github.io/Nova/>（大小寫要對），一樣吃網址參數（`…/Nova/?surname=陳&born=2026-09-03T10:30&gender=girl`）。
刻意不在 GitHub Actions 重新建置：ETL 來源之一 Unihan.zip 是 Unicode 的 "latest"，會隨版本移動，CI 重跑不保證產出與本機一致。

幾件要知道的事：

- GitHub Free 方案只有 **public repo** 能開 Pages，也就是原始碼與內建字典都會公開。Gemini API key 不受影響——它只存在使用者自己的瀏覽器、直接送到 Google。
- 網頁的 origin 從 `file://` 變成 `https://siriuslee1207.github.io`，所以 `file://` 版存的 key、偏好與歷史紀錄**不會**帶過去（相對地也不再與其他本機 HTML 共用 localStorage，比較安全）。
- iOS 用 https 開就會正常執行 JavaScript，Safari 的「加入主畫面」可以做成 App 圖示；`file://` 那個「快速查看不執行 JS」的限制不存在。
- Pages 會快取，剛 push 完手機可能還是舊的，等一兩分鐘或強制重新整理。單檔 1.3 MB，首次載入會傳這麼多（Pages 有 gzip）。

### 評分權重

總分預設是五維加權：文化 20%、五行 25%、生肖 10%、五格三才 30%、音韻 15%（三才併在五格維度內）。
表單的「評分權重」可自己調：選預設組合（預設五維／只看三才五格／八字五行為主／音韻字義為主／五維等重），
或直接填五個數字。數字只看比例，Nova 會正規化成總和 1 再算分——填「三才五格 1、其他 0」，總分就等於三才五格的分數，
等級（上上／上吉…）與各維分數的算法都不變。權重只影響總分與排名，篩掉哪些筆畫組合仍由「嚴格度」決定；
AI 推薦時也會把這次的權重寫進提示。權重會記在這個瀏覽器，也可用網址參數帶入，例如
`nova.html?surname=李&weights=0,0,0,1,0` 或 `…&weights=三才五格%3D1,其他%3D0`。

AI 顧問：在左側貼上你自己的 Gemini API key（AI Studio 建立；新式 key 以 `AQ.` 開頭，舊式 `AIza` 已被 Google 停用），
按「AI 推薦用字」，或在卡片明細中按「AI 解說」（含以名字兩字起頭的藏頭對聯與白話解釋）。key 由瀏覽器直接送到 Google，不經任何中間伺服器。
key 與模型設定會自動存在這個瀏覽器的 localStorage，下次開啟不用重貼，清空欄位即移除；`file://` 頁面共用同一個 origin，
同一瀏覽器開的其他本機 HTML 也讀得到，公用電腦請用完清掉。免費層每日請求數有限，預設模型 `gemini-3.5-flash-lite`；貼上 key 後會自動抓取這把 key 可用的 Gemini 文字模型清單填入下拉選單，選「自行輸入…」可手動填模型名稱，按 ↻ 重新抓取。模型壅塞（503）或每分鐘限流（429）會自動退避重試最多 3 次，狀態列會顯示；仍失敗就換一個模型。
網頁端只提供 Gemini；GitHub Copilot 沒有可用的 API key，只能走下方命令列。
「給 AI 的偏好」第一次開啟時帶入一段依寶寶背景（姓李、男孩、屬馬、十月生）寫成的偏好提示：想要的風格、生肖字根偏好、讀音與用字禁忌、風格多樣性、理由寫法，可直接改寫，改過的文字會記在這個瀏覽器，欄位旁的「範本」可帶回；範本文字在 `src/js/defaults.js`。
「歷史紀錄」會記下每次 AI 推薦的條件、偏好、模型與結果（最多 30 筆，同樣存在這個瀏覽器），可把偏好帶回欄位、修改後重新詢問；重問同一組條件與偏好只會更新同一筆。

### 筆畫組合選字

想先定筆畫格局、再自己挑字，按「筆畫組合選字」：Nova 依姓氏筆畫列出**所有**合格的（第一字, 第二字）筆畫組合，依第一字筆畫分組；
點一個第二字筆畫，下方就列出兩個筆畫各自的全部候選字（可依五行、注音聲調過濾，聲調取主要讀音；兩排都可複選，同一排多選是「其中之一」、五行與聲調之間要同時符合，按「全部」取消該排條件；
兩個字各有自己的過濾條件；有出生時間時用神／喜神的字加框、忌神／仇神淡化；滑鼠停在字上看拼音與字義），
點一個第一字、再點一個第二字，立刻用一般的評分卡評分（可展開明細、AI 解說），選過的名字留在下方比較。
合格標準與「嚴格度」無關，由三層決定，都可在畫面上調整並記在這個瀏覽器：

- **三才吉凶表**（謝達輝表，見下）：可勾選 最吉／吉／平吉／半吉，預設 最吉＋吉；凶、最凶不列出。
- **吉數**：勾選的格（預設天格、人格、地格、外格、總格全部）都必須落在 36 吉數
  `1 3 5 6 7 8 11 13 15 16 17 18 21 23 24 25 29 31 32 33 35 37 39 41 45 47 48 52 55 57 61 63 65 67 68 81`（超過 81 循環）。
  天格只由姓氏決定：林、張、楊、許、鄭、周、莊、蕭等姓的天格不在吉數內，畫面會提示並可一鍵取消勾選天格，改以其他四格判定。
- **吉數等級**：把 81 數分成 大吉 28／吉 8／半吉 6／半凶 14／凶 25 五級，**人格、地格、外格、總格四格**都必須落在勾選的等級內；
  預設五級全勾＝不限制，結果與只有前兩層時相同。大吉＋吉 恰好就是 36 吉數，所以只勾「大吉」＝在吉數裡再挑兩表皆吉的數
  （例：王 41 組 → 11 組、陳 16 組 → 1 組）。**天格撇除不計**——天格由姓氏決定、改不了，列表與五格卡仍會標出它的等級供參考。

另沿用左側的「字集」「排除字」「排除女性不宜總格」；網址參數 `nova.html?surname=陳&mode=combos` 可直接開啟這個模式，再加 `&combo=19,6&pick=薇宇` 可預先選好組合與字。
每組旁的「五格分」仍是原評分（fate 的 81 數理表與三才表），只作排序參考；兩張三才表的分級在明細中並列顯示。

資料來源：三才吉凶表轉錄自中國五術大學 謝達輝姓名學研究所「三才配置吉凶」（cdi.org.tw `n-3-gold.html` 系列五頁，125 組 → `data/tables/sancai_cdi.json`）；
36 吉數為熊崎氏 81 數理常用吉數（`data/tables/jishu36.json`）；吉數等級（`data/tables/jishu_grade.json`）由兩張 81 數表合併而成——
fate 的 `dayan81.json`（吉／半吉／凶）與同站「姓名81劃吉凶分類表」（`n-81.html`，吉／吉帶凶／凶帶吉／凶，存在同檔的 `cdi` 欄）：
大吉＝兩表皆吉，吉＝36 吉數其餘成員，半吉＝非吉數但兩表都還看好，半凶＝只有一表看好，凶＝兩表皆凶。三張表都可直接編輯後重新 build。

## 命令列

```powershell
.venv\Scripts\python -m nova_core.cli 陳 --born 2026-09-03T10:30 --gender girl --top 12
.venv\Scripts\python -m nova_core.cli 歐陽 --gender boy --level 1 --first 承
.venv\Scripts\python -m nova_core.cli 陳 --born 2026-09-03T10:30 --explain 冠宇
.venv\Scripts\python -m nova_core.cli 李 --born 2026-10-15T09:20 --weights "三才五格=1,其他=0"     # 自訂評分權重
.venv\Scripts\python -m nova_core.cli 李 --born 2026-10-15T09:20 --weights wuge --json             # 同上，預設名稱
.venv\Scripts\python -m nova_core.cli 陳 --combos                                                  # 筆畫組合選字：列出所有合格筆畫組合
.venv\Scripts\python -m nova_core.cli 林 --combos --grids ren,di,wai,zong --sancai-grades 最吉,吉,平吉   # 天格非吉數的姓：去掉 tian
.venv\Scripts\python -m nova_core.cli 王 --combos --jishu-grades 大吉                              # 人地外總四格都要「大吉」（吉數等級）
.venv\Scripts\python -m nova_core.cli 陳 --combo 19,6 --level 1                                    # 該組合的兩份字表（--json 可機器讀）
.venv\Scripts\python -m nova_core.cli 陳 --born 2026-09-03T10:30 --ai recommend --provider gemini     # 需 GEMINI_API_KEY
.venv\Scripts\python -m nova_core.cli 陳 --born 2026-09-03T10:30 --explain 冠宇 --ai explain --provider copilot
.venv\Scripts\python -m nova_core.cli 陳 --born 2026-09-03T10:30 --ai recommend --ai-dump              # 只印提示，不呼叫
```

Copilot 走官方 `github-copilot-sdk`（或 PATH 上的 `copilot` CLI），沿用你已登入的 Copilot 訂閱；
Nova 不使用 IDE 內部端點（無公開文件且有帳號停權案例）。SDK 首次使用會自動下載 CLI runtime（約 160 MB）到
`%LOCALAPPDATA%\github-copilot-sdk\cli\<版本>\copilot.exe`，之後登入一次即可：

```powershell
.venv\Scripts\python -m copilot download-runtime                          # 可省略，首次呼叫會自動下載
& "$env:LOCALAPPDATA\github-copilot-sdk\cli\1.0.79\copilot.exe" login     # 瀏覽器 OAuth；遠端環境加 --device-code
```

或設環境變數 `COPILOT_GITHUB_TOKEN`（fine-grained PAT，需 Copilot Requests 權限；classic `ghp_` 不支援）。
VS Code 內的 Copilot 登入不會共用給 CLI。預設模型 `gpt-5-mini`（reasoning low），可用 `--model` 換成
`claude-haiku-4.5`、`gpt-5.4-mini` 等；session 不開任何工具、不讀 AGENTS.md、不寫入 Copilot 的 session 紀錄與記憶。

## 開發

```powershell
python -m venv .venv
.venv\Scripts\pip install -e ".[dev,build,bazi]"        # 另可加 gemini / copilot
.venv\Scripts\python tools\fetch_source.py             # 下載 fate character.json 與 Unihan.zip 到 data/raw/
.venv\Scripts\python tools\build.py --fixtures         # tables → chars → prompts → golden → dist/nova.html
.venv\Scripts\python -m pytest                         # Python 參考實作
node tests\parity.mjs                                  # 或雙擊 tests\parity.html：JS 與 Python 逐位一致
.venv\Scripts\python tools\publish.py                  # 驗證過再發佈：dist/nova.html → docs/index.html（GitHub Pages）
```

`tools/transcribe_fate.py` 從 `ref/fate/` 的 Go 原始碼重新產生常數表（需先 `curl` 下載，見 `docs/spike-notes.md`）。

## 目錄

| 路徑 | 內容 |
|---|---|
| `data/tables/` | 常數表（單一真相來源）：八十一數理、三才 125 組與解析、八字表、筆畫特例、常見取名用字、排除字、字義覆蓋、謝達輝三才吉凶表、36 吉數、吉數等級 |
| `data/prompts/` | LLM 提示模板（Python 直讀，build 內嵌 JS） |
| `data/gen/` | 建置產物：`chars.json`/`chars.gen.js`、`tables.gen.js`、`prompts.gen.js`、`etl_report.md` |
| `nova_core/` | Python 參考實作、CLI、`llm/`（gemini、copilot、advisor） |
| `src/` | 前端：`js/core/*`（與 Python 對應的模組）、`js/llm/*`、`ui.js`、`vendor/lunar.js` |
| `tools/` | ETL、轉錄、fixture、打包、`serve.py`（分享給手機）、`publish.py`（發佈到 GitHub Pages） |
| `tests/` | pytest；`parity_core.js` + `parity.mjs`/`parity.html` |
| `docs/` | GitHub Pages 站台：`index.html`（＝建好的 `nova.html`）、`nova.html`（舊網址轉址）、`.nojekyll`；另有 `spike-notes.md`：資料品質、環境驗證與決策紀錄 |

## 與 fate 的差異

- 修正：五格「半吉」分支永遠走不到、聲調判斷對調號拼音失效、三才「中吉」等級缺漏導致永遠被過濾、`金金火` 缺項、喜用神方法切換不影響評分。
- 資料：以 Big5 常用／次常用字為全集（純簡體字自動轉繁）；筆畫改用 Unihan 康熙部首＋餘筆並加姓名學特例（數字字、成 7 等）；拼音以臺灣讀音為主並轉數字調；字義以 OpenCC 轉臺灣正體並人工修正常用字；常用等級分三級（常見取名用字／常用／次常用），數字與虛詞預設不入候選。
- 新增：時辰不詳模式、同一首字次數上限、指定輩字、姓氏筆畫可手動覆寫、自訂五維評分權重、筆畫組合選字（三才吉凶表＋吉數＋吉數等級先定筆畫格局再選字）、Python/JS 一致性測試、AI 顧問。
- 五行分數以十分之一整數累加，避免浮點雜訊影響強弱判斷。

分數僅供參考。授權 MIT（`LICENSE`），第三方見 `NOTICE`。
