"""把 dist/nova.html 分享到區域網路，讓手機（尤其 iPhone）能真正執行它。

iPhone／iPad 的「檔案」App 是用「快速查看」預覽 HTML：版面畫得出來，但 JavaScript 完全不執行，
所以按「產生名字」不會有任何反應。手機瀏覽器開 http:// 網址就沒有這個限制。

用法（電腦與手機要在同一個 Wi-Fi）：

    .venv\\Scripts\\python tools/serve.py

會印出像 http://192.168.1.23:8000/nova.html 的網址，手機瀏覽器輸入即可；
Safari 分享選單的「加入主畫面」可以把它變成像 App 的圖示。Ctrl+C 結束。

第一次執行 Windows 可能跳出防火牆詢問，要允許「私人網路」才連得到。
頁面純靜態、完全離線運算，只有 AI 顧問會從手機瀏覽器直接連到 Google。
"""
from __future__ import annotations

import argparse
import socket
import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def lan_ips() -> list[str]:
    """這台電腦在區域網路上的 IPv4 位址，預設路由那張網卡排前面。"""
    ips: list[str] = []
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))          # 不會真的送封包，只是問作業系統會從哪張網卡出去
        ips.append(s.getsockname()[0])
    except OSError:
        pass
    finally:
        s.close()
    try:
        for ip in socket.gethostbyname_ex(socket.gethostname())[2]:
            if ip not in ips and not ip.startswith('127.'):
                ips.append(ip)
    except OSError:
        pass
    return ips


class Handler(SimpleHTTPRequestHandler):
    def end_headers(self) -> None:
        self.send_header('Cache-Control', 'no-store')   # 重新 build 後手機不要吃到舊的
        super().end_headers()

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write('  %s\n' % (fmt % args))


def main() -> None:
    ap = argparse.ArgumentParser(description='在區域網路上分享 dist/nova.html（給手機用）')
    ap.add_argument('--port', type=int, default=8000)
    ap.add_argument('--dir', default=str(ROOT / 'dist'), help='要分享的資料夾（預設 dist/）')
    ap.add_argument('--file', default='nova.html', help='網址要指到的檔案')
    args = ap.parse_args()

    root = Path(args.dir).resolve()
    if not (root / args.file).exists():
        sys.exit(f'找不到 {root / args.file}，先跑 python tools/build.py')

    if not sys.stdout.isatty():        # 主控台本來就走 UTF-16 API，導向檔案／管線時才會踩到 cp950
        try:
            sys.stdout.reconfigure(encoding='utf-8', errors='replace', line_buffering=True)
        except (AttributeError, OSError):
            pass

    httpd = ThreadingHTTPServer(('0.0.0.0', args.port), partial(Handler, directory=str(root)))
    ips = lan_ips()
    print(f'分享 {root}（Ctrl+C 結束）')
    print('手機（同一個 Wi-Fi）用瀏覽器開：')
    for ip in ips or ['<這台電腦的 IP>']:
        print(f'    http://{ip}:{args.port}/{args.file}')
    print(f'這台電腦自己測試：http://127.0.0.1:{args.port}/{args.file}')
    print('連不上的話：確認手機沒開行動網路／VPN、電腦防火牆允許「私人網路」，兩邊在同一個 Wi-Fi。')
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print('\n結束。')
    finally:
        httpd.server_close()


if __name__ == '__main__':
    main()
