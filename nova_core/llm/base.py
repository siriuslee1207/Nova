"""供應商介面與提示模板（對應 src/js/llm/provider.js）。"""
from __future__ import annotations

import re
from functools import lru_cache
from typing import Callable, Protocol

from .. import ROOT

PROMPTS_DIR = ROOT / 'data' / 'prompts'


class Provider(Protocol):
    id: str

    def stream_text(self, system: str, user: str, on_delta: Callable[[str], None] | None = None) -> str: ...

    def generate_json(self, system: str, user: str, schema: dict) -> dict: ...


@lru_cache(maxsize=None)
def template(name: str) -> str:
    return (PROMPTS_DIR / f'{name}.md').read_text(encoding='utf-8')


def render(name: str, **vars) -> str:
    return re.sub(r'\{\{(\w+)\}\}', lambda m: '' if vars.get(m.group(1)) is None else str(vars[m.group(1)]), template(name))


def get_provider(name: str, model: str | None = None) -> Provider:
    if name == 'gemini':
        from .gemini import GeminiProvider
        return GeminiProvider(model=model)
    if name == 'copilot':
        from .copilot import CopilotProvider
        return CopilotProvider(model=model)
    raise ValueError(f'未知供應商 {name}（可用：gemini, copilot）')
