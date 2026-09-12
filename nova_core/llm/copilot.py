"""GitHub Copilot 供應商 —— 只走官方 Copilot SDK（pip install github-copilot-sdk），退路為 `copilot` CLI 子程序。

SDK 首次使用會自動下載 pinned 版 CLI runtime（約 160 MB）到 %LOCALAPPDATA%/github-copilot-sdk/cli/<版本>/，
不需要 PATH 上有 copilot。認證沿用 `copilot login`（存於系統憑證庫）或 COPILOT_GITHUB_TOKEN / GH_TOKEN / GITHUB_TOKEN。
不使用 api.githubcopilot.com 的 IDE 內部端點（無公開文件、有帳號停權案例）。

Session 建立時不開任何工具、不讀 AGENTS.md、不存 session／記憶，只是純文字問答；
system 提示用 replace 模式整段取代 CLI 預設的 coding-agent 提示（含 cwd／環境資訊），與 Gemini 的 system_instruction 對齊。
（SDK 的 mode="empty" 會停用系統憑證庫，讀不到 `copilot login` 的登入，故不採用。）
SDK 沒有結構化輸出，JSON 以提示要求並解析（失敗重試一次）。
"""
from __future__ import annotations

import asyncio
import json
import re
import shutil
import subprocess
from typing import Callable

DEFAULT_MODEL = 'gpt-5-mini'
DEFAULT_EFFORT = 'low'  # 只在模型的 supportedReasoningEfforts 含 low 時送出
DEFAULT_TIMEOUT = 300
_JSON_BLOCK = re.compile(r'\{.*\}', re.S)
_SDK_DRIFT = (ImportError, AttributeError, TypeError)  # SDK 版本漂移才退回 CLI；模型／認證錯誤直接拋出


class CopilotProvider:
    id = 'copilot'
    _effort_cache: dict[str, str | None] = {}

    def __init__(self, model: str | None = None, effort: str | None = None, timeout: float = DEFAULT_TIMEOUT):
        self.model = model or DEFAULT_MODEL
        self.effort = effort
        self.timeout = timeout
        try:
            import copilot  # noqa: F401  github-copilot-sdk
            self._sdk = True
        except ImportError:
            self._sdk = False
        self._cli = shutil.which('copilot') or self._cached_cli()
        if not self._sdk and not self._cli:
            raise ImportError('需要 github-copilot-sdk（pip install github-copilot-sdk）或 PATH 上的 copilot CLI')

    @staticmethod
    def _cached_cli() -> str | None:
        """SDK 下載快取裡的 CLI（SDK 私有 API，拿不到就算了）。"""
        try:
            from copilot._cli_download import get_cached_cli_path
            return get_cached_cli_path()
        except Exception:
            return None

    # ---- SDK transport --------------------------------------------------------------
    async def _pick_effort(self, client) -> str | None:
        if self.effort:
            return self.effort
        if self.model not in self._effort_cache:
            level = None
            try:
                for m in await client.list_models():
                    if m.id == self.model:
                        level = DEFAULT_EFFORT if DEFAULT_EFFORT in (m.supported_reasoning_efforts or []) else None
                        break
            except Exception:
                level = None
            self._effort_cache[self.model] = level
        return self._effort_cache[self.model]

    def _run_sdk(self, system: str, user: str, on_delta: Callable[[str], None] | None) -> str:
        from copilot import CopilotClient
        from copilot.session import PermissionHandler
        from copilot.session_events import (AssistantMessageData, AssistantMessageDeltaData, SessionErrorData,
                                            SessionIdleData)

        async def go() -> str:
            # 不用 mode='empty'：它會設 COPILOT_DISABLE_KEYTAR=1，讀不到 `copilot login` 存在系統憑證庫的登入。
            # 改在預設模式下逐項關掉：無工具、整段取代 system 提示、不讀 AGENTS.md、不存 session／記憶、不載 skills。
            async with CopilotClient(log_level='warning') as client:
                effort = await self._pick_effort(client)
                async with await client.create_session(
                        model=self.model,
                        reasoning_effort=effort,
                        available_tools=[],  # 空清單 = 不給模型任何工具（bash／檔案／MCP 全關）
                        streaming=bool(on_delta),
                        system_message={'mode': 'replace', 'content': system},
                        skip_custom_instructions=True,
                        enable_session_store=False,
                        memory={'enabled': False},
                        enable_skills=False,
                        on_permission_request=PermissionHandler.approve_all) as session:
                    deltas: list[str] = []
                    finals: list[str] = []
                    errors: list[str] = []
                    done = asyncio.Event()

                    def on_event(event):
                        data = event.data
                        if isinstance(data, AssistantMessageDeltaData):
                            deltas.append(data.delta_content)
                            if on_delta:
                                on_delta(data.delta_content)
                        elif isinstance(data, AssistantMessageData):
                            finals.append(data.content)
                        elif isinstance(data, SessionErrorData):
                            errors.append(f'{data.error_type}: {data.message}')
                        elif isinstance(data, SessionIdleData):
                            done.set()

                    session.on(on_event)
                    await session.send(user)
                    try:
                        await asyncio.wait_for(done.wait(), self.timeout)
                    except TimeoutError:
                        raise RuntimeError(f'Copilot {self.timeout:g} 秒內未完成回應') from None
                    if errors:
                        raise RuntimeError('Copilot 錯誤：' + '；'.join(errors))
                    text = ''.join(finals) or ''.join(deltas)
                    if on_delta and not deltas and text:  # 模型不支援串流時一次補印
                        on_delta(text)
                    return text

        return asyncio.run(go())

    # ---- CLI transport --------------------------------------------------------------
    def _run_cli(self, system: str, user: str) -> str:
        cmd = [self._cli, '-p', f'{system}\n\n---\n\n{user}', '-s', '--model', self.model,
               '--no-custom-instructions', '--no-auto-update']
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', timeout=self.timeout)
        if proc.returncode != 0 or proc.stdout.lstrip().startswith('Error:'):
            raise RuntimeError(f'copilot CLI 失敗（{proc.returncode}）：{(proc.stderr or proc.stdout).strip()[:300]}')
        return proc.stdout.strip()

    def _complete(self, system: str, user: str, on_delta=None) -> str:
        if self._sdk:
            try:
                return self._run_sdk(system, user, on_delta)
            except _SDK_DRIFT:
                if not self._cli:
                    raise
        text = self._run_cli(system, user)
        if on_delta:
            on_delta(text)
        return text

    # ---- Provider API ---------------------------------------------------------------
    def stream_text(self, system: str, user: str, on_delta: Callable[[str], None] | None = None) -> str:
        return self._complete(system, user, on_delta)

    def generate_json(self, system: str, user: str, schema: dict) -> dict:
        ask = user + '\n\n請只輸出符合上述格式的 JSON，不要加程式碼區塊標記或說明。'
        last = ''
        for _ in range(2):
            last = self._complete(system, ask)
            m = _JSON_BLOCK.search(last)
            if m:
                try:
                    return json.loads(m.group(0))
                except json.JSONDecodeError:
                    pass
            ask = user + '\n\n上一次回覆不是有效 JSON。請只輸出一個 JSON 物件，不要任何其他文字。'
        raise RuntimeError(f'Copilot 兩次都未回傳有效 JSON：{last[:200]}')
