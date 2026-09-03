"""音韻：拼音調號轉數字調、聲調/聲母/韻母拆解（fate rating.go 的 getTone/getShengMu/getYunMu）。

Nova 修正：fate 只認尾碼數字聲調，而資料是調號拼音，聲調項形同失效。
Nova 在 ETL 以 to_numbered() 轉成 `hao4` 形式（輕聲不加數字，tone() 回 0），
韻母比較前先去掉聲調數字。
"""
from __future__ import annotations

import unicodedata

_TONE_OF_MARK = {'̄': 1, '́': 2, '̌': 3, '̀': 4}  # ̄ ́ ̌ ̀

# fate 的聲母表（含 y、w），依序比對前綴；zh/ch/sh 先於單字母。
SHENGMU = ('zh', 'ch', 'sh', 'b', 'p', 'm', 'f', 'd', 't', 'n', 'l', 'g', 'k', 'h',
           'j', 'q', 'x', 'z', 'c', 's', 'r', 'y', 'w')


def to_numbered(pinyin: str) -> str:
    """'hào' → 'hao4'；'lǜ' → 'lü4'；'ma' → 'ma'（輕聲）。已是數字調則原樣回傳。"""
    if pinyin and pinyin[-1].isdigit():
        return pinyin
    tone = 0
    out = []
    for ch in unicodedata.normalize('NFD', pinyin):
        t = _TONE_OF_MARK.get(ch)
        if t:
            tone = t
            continue
        out.append(ch)
    base = unicodedata.normalize('NFC', ''.join(out))
    return f'{base}{tone}' if tone else base


def tone(pinyin: str) -> int:
    """尾碼 1–4 為聲調；無尾碼（輕聲/未知）回 0。"""
    if pinyin and pinyin[-1] in '1234':
        return int(pinyin[-1])
    return 0


def base(pinyin: str) -> str:
    return pinyin[:-1] if pinyin and pinyin[-1].isdigit() else pinyin


def shengmu(pinyin: str) -> str:
    b = base(pinyin)
    for sm in SHENGMU:
        if b.startswith(sm):
            return sm
    return ''


def yunmu(pinyin: str) -> str:
    b = base(pinyin)
    return b[len(shengmu(pinyin)):]
