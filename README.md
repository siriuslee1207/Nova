# Nova — 小孩取名

繁體中文取名工具。保留 [fate](https://github.com/babyname/fate) 的命名規則與五維評分（五格數理、三才、八字喜用五行、生肖、音韻），
產出為**單一 `dist/nova.html`**，雙擊即用、離線可跑；Python 負責資料 ETL、常數表、單檔打包、參考實作與測試。

## 快速開始（開發）

```powershell
python -m venv .venv
.venv\Scripts\pip install -e ".[dev,build,bazi]"
.venv\Scripts\python tools\fetch_source.py     # 下載 fate character.json 與 Unihan
.venv\Scripts\python tools\build.py            # tables → chars → fixtures → dist/nova.html
.venv\Scripts\python -m pytest
```

雙擊 `dist/nova.html` 使用；雙擊 `tests/parity.html` 驗證 JS 與 Python 參考實作分數完全一致。

## 目錄

- `data/tables/` 常數表（單一真相來源，Python 與 JS 共用）
- `nova_core/` Python 參考實作與 CLI
- `src/` 前端原始碼（vanilla JS，build 時內嵌）
- `tools/` Python 建置腳本
- `docs/spike-notes.md` 資料品質與環境驗證紀錄

授權：MIT（見 `LICENSE`、第三方見 `NOTICE`）。
