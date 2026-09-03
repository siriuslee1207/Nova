"""Nova — Python 參考實作（權威演算法、CLI、golden 測試向量來源）。

執行期產品是 dist/nova.html 內的 JavaScript；本套件與之共用 data/tables/*.json 與 data/gen/chars.json，
並以 tests/parity.html 驗證兩邊分數完全一致。
"""
from pathlib import Path

__version__ = '0.1.0'
ROOT = Path(__file__).resolve().parents[1]
