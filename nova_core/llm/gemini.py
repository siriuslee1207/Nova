"""Gemini（Google AI Studio）供應商，使用官方 google-genai SDK（pip install "google-genai>=2.22,<3"）。

API key 讀取順序：建構參數 → GEMINI_API_KEY → GOOGLE_API_KEY（SDK 行為；GOOGLE_API_KEY 優先於 GEMINI_API_KEY）。
"""
from __future__ import annotations

import json
import re
from typing import Callable

DEFAULT_MODEL = 'gemini-3.5-flash-lite'


class GeminiProvider:
    id = 'gemini'

    def __init__(self, model: str | None = None, api_key: str | None = None, thinking: str = 'auto'):
        try:
            from google import genai
            from google.genai import types
        except ImportError as e:  # pragma: no cover
            raise ImportError('請安裝 google-genai：pip install "google-genai>=2.22,<3"') from e
        self._types = types
        self.client = genai.Client(api_key=api_key) if api_key else genai.Client()
        self.model = model or DEFAULT_MODEL
        self.thinking = thinking

    def _config(self, system: str, json_schema: dict | None = None):
        t = self._types
        kw = {'system_instruction': system, 'max_output_tokens': 8192}
        level = None if self.thinking == 'auto' else self.thinking
        if level is None and re.search(r'flash-lite|3\.5-flash|3\.6-flash|2\.5-', self.model):
            level = 'LOW'  # 3.7/3.8 flash 只接受 MEDIUM/HIGH，交給預設
        if level:
            kw['thinking_config'] = t.ThinkingConfig(thinking_level=level)
        if json_schema is not None:
            kw['response_mime_type'] = 'application/json'
            kw['response_json_schema'] = json_schema
        return t.GenerateContentConfig(**kw)

    def stream_text(self, system: str, user: str, on_delta: Callable[[str], None] | None = None) -> str:
        out = []
        for chunk in self.client.models.generate_content_stream(model=self.model, contents=user, config=self._config(system)):
            text = chunk.text or ''
            if text:
                out.append(text)
                if on_delta:
                    on_delta(text)
        return ''.join(out)

    def generate_json(self, system: str, user: str, schema: dict) -> dict:
        resp = self.client.models.generate_content(model=self.model, contents=user, config=self._config(system, schema))
        cand = (resp.candidates or [None])[0]
        finish = getattr(cand, 'finish_reason', None)
        if finish is not None and str(finish).split('.')[-1] not in ('STOP', 'FinishReason.STOP'):
            raise RuntimeError(f'生成未完整（{finish}），請重試或換模型')
        text = resp.text or ''
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            raise RuntimeError(f'回應不是有效 JSON：{text[:200]}') from e
