"""把建好的 dist/nova.html 複製成 docs/index.html，讓 GitHub Pages 直接託管它。

線上版刻意放「本機建置並驗證過的那一份」，而不是在 CI 重新建置：ETL 的來源之一
Unihan.zip 是 Unicode 的 "latest"，會隨版本移動，CI 重跑不保證跟本機一模一樣。

用法：

    .venv\\Scripts\\python tools/build.py        # 先 build（src/ 或 data/ 改過的話）
    .venv\\Scripts\\python tools/publish.py      # 再 publish
    git add docs/index.html && git commit -m "publish" && git push

GitHub 那邊只要設定一次：Settings → Pages → Source = Deploy from a branch，
Branch = main、資料夾 = /docs。網址是 https://<帳號>.github.io/<repo>/。
"""
from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / 'dist' / 'nova.html'
SITE = ROOT / 'docs' / 'index.html'
# publish 之前 dist/nova.html 應該比這些來源都新，否則就是忘了重 build
SOURCES = [ROOT / 'src', ROOT / 'data' / 'gen']


def newer_than_dist() -> list[Path]:
    stamp = DIST.stat().st_mtime
    stale = []
    for base in SOURCES:
        if not base.exists():
            continue
        for p in base.rglob('*'):
            if p.is_file() and p.stat().st_mtime > stamp:
                stale.append(p.relative_to(ROOT))
    return stale


def main(argv: list[str]) -> None:
    force = '--force' in argv
    if not DIST.exists():
        sys.exit(f'找不到 {DIST.relative_to(ROOT)}，先跑 python tools/build.py')

    stale = newer_than_dist()
    if stale and not force:
        listed = '\n'.join(f'    {p}' for p in stale[:10])
        more = f'\n    …另外 {len(stale) - 10} 個' if len(stale) > 10 else ''
        sys.exit(f'dist/nova.html 比這些來源舊，先重跑 python tools/build.py（或加 --force）：\n{listed}{more}')

    html = DIST.read_text(encoding='utf-8')
    leftovers = re.findall(r'<(?:script|link)[^>]*?\s(?:src|href)="(?!data:|https?:)([^"]+)"', html)
    if leftovers:
        sys.exit(f'dist/nova.html 還有外部參考，不能單檔託管：{leftovers}')

    SITE.parent.mkdir(exist_ok=True)
    shutil.copyfile(DIST, SITE)
    print(f'wrote {SITE.relative_to(ROOT)} ({SITE.stat().st_size / 1024:.0f} KB)')
    if stale:
        print('（--force：忽略了比 dist 新的來源檔）')
    print('接著：git add docs/index.html && git commit -m "publish 線上版" && git push')


if __name__ == '__main__':
    main(sys.argv[1:])
