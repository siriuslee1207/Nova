"""GitHub Copilot 供應商 —— 只走官方途徑：Copilot SDK（pip install github-copilot-sdk）或 `copilot` CLI 子程序。

不使用 api.githubcopilot.com 的 IDE 內部端點（無公開文件、有帳號停權案例）。
SDK 不支援結構化輸出，故 JSON 以提示要求並解析（失敗重試一次）。
認證沿用 `copilot` CLI 登入狀態或 COPILOT_GITHUB_TOKEN / GH_TOKEN / GITHUB_TOKEN。
"""
from __future__ import annotations

import asyncio
import json
import re
import shutil
import subprocess
from typing import Callable

DEFAULT_MODEL = 'gpt-5-mini'
_JSON_BLOCK = re.compile(r'\{.*\}', re.S)


class CopilotProvider:
    id = 'copilot'

    def __init__(self, model: str | None = None):
        self.model = model or DEFAULT_MODEL
        try:
            import copilot  # noqa: F401  github-copilot-sdk
            self._sdk = True
        except ImportError:
            self._sdk = False
        if not self._sdk and not shutil.which('copilot'):
            raise ImportError('需要 github-copilot-sdk（pip install github-copilot-sdk）或 PATH 上的 copilot CLI')

    # ---- transport ------------------------------------------------------------------
    def _run_sdk(self, prompt: str, on_delta: Callable[[str], None] | None) -> str:
        from copilot import CopilotClient
        from copilot.session import PermissionHandler
        from copilot.session_events import AssistantMessageData, SessionIdleData

        async def go() -> str:
            parts: list[str] = []
            async with CopilotClient() as client:
                async with await client.create_session(model=self.model,
                                                       on_permission_request=PermissionHandler.approve_all) as session:
                    done = asyncio.Event()

                    def on_event(event):
                        data = event.data
                        if isinstance(data, AssistantMessageData):
                            parts.append(data.content)
                            if on_delta:
                                on_delta(data.content)
                        elif isinstance(data, SessionIdleData):
                            done.set()

                    session.on(on_event)
                    await session.send(prompt)
                    await done.wait()
            return ''.join(parts)

        return asyncio.run(go())

    def _run_cli(self, prompt: str) -> str:
        cmd = ['copilot', '-p', prompt, '-s', '--model', self.model]
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', timeout=300)
        if proc.returncode != 0:
            raise RuntimeError(f'copilot CLI 失敗（{proc.returncode}）：{proc.stderr.strip()[:300]}')
        return proc.stdout.strip()

    def _complete(self, system: str, user: str, on_delta=None) -> str:
        prompt = f'{system}\n\n---\n\n{user}'
        if self._sdk:
            try:
                return self._run_sdk(prompt, on_delta)
            except Exception as e:  # SDK/CLI 版本漂移時退回 CLI
                if not shutil.which('copilot'):
                    raise
                text = self._run_cli(prompt)
                if on_delta:
                    on_delta(text)
                return text
        text = self._run_cli(prompt)
        if on_delta:
            on_delta(text)
        return text

    # ---- Provider API ---------------------------------------------------------------
    def stream_text(self, system: str, user: str, on_delta: Callable[[str], None] | None = None) -> str:
        return self._complete(system, user, on_delta)

    def generate_json(self, system: str, user: str, schema: dict) -> dict:
        ask = user + '\n\n請只輸出符合上述格式的 JSON，不要加程式碼區塊標記或說明。'
        for attempt in range(2):
            text = self._complete(system, ask)
            m = _JSON_BLOCK.search(text)
            if m:
                try:
                    return json.loads(m.group(0))
                except json.JSONDecodeError:
                    pass
            ask = user + '\n\n上一次回覆不是有效 JSON。請只輸出一個 JSON 物件，不要任何其他文字。'
        raise RuntimeError('Copilot 兩次都未回傳有效 JSON')
