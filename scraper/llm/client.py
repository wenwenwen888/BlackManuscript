"""LLM 客户端：OpenAI 兼容 API 调用。

通过环境变量配置：
  OPENAI_API_KEY   必填
  OPENAI_BASE_URL  可选，默认 https://api.openai.com/v1
                    可换 DeepSeek: https://api.deepseek.com/v1
                    可换通义: https://dashscope.aliyuncs.com/compatible-mode/v1
                    可换 Kimi: https://api.moonshot.cn/v1
  LLM_MODEL        可选，默认 gpt-4o-mini
  LLM_MODEL_STRONG 可选，处理 prompt 用更强模型，默认同 LLM_MODEL

不引入 openai SDK 依赖，直接用 urllib + requests-style，
便于在境外 VPS 最小化部署。
"""
from __future__ import annotations

import os
import json
import logging
import urllib.request
import urllib.error
from typing import Optional

logger = logging.getLogger(__name__)


class LLMError(Exception):
    pass


class LLMClient:
    """OpenAI 兼容的 chat completions 客户端。"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: int = 60,
    ):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.base_url = (base_url or os.environ.get("OPENAI_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
        self.model = model or os.environ.get("LLM_MODEL", "gpt-4o-mini")
        self.timeout = timeout

        if not self.api_key:
            logger.warning("OPENAI_API_KEY 未设置，LLM 调用将失败")

    def chat(
        self,
        messages: list[dict],
        *,
        model: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 800,
    ) -> str:
        """调用 chat completions，返回 assistant 文本。"""
        if not self.api_key:
            raise LLMError("OPENAI_API_KEY 未设置")

        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": model or self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")[:500]
            raise LLMError(f"HTTP {e.code}: {body}") from e
        except urllib.error.URLError as e:
            raise LLMError(f"URL error: {e}") from e

        try:
            obj = json.loads(raw)
            return obj["choices"][0]["message"]["content"]
        except (json.JSONDecodeError, KeyError, IndexError) as e:
            raise LLMError(f"解析响应失败: {e}, raw={raw[:500]}") from e

    def chat_json(
        self,
        messages: list[dict],
        *,
        model: Optional[str] = None,
        temperature: float = 0.3,
    ) -> dict:
        """调用并解析 JSON 响应。自动剥离 ```json 代码块包装。"""
        text = self.chat(messages, model=model, temperature=temperature)
        return _parse_json_response(text)


def _parse_json_response(text: str) -> dict:
    """解析 LLM 返回的 JSON，容错剥离 markdown 代码块。"""
    text = text.strip()
    # 剥离 ```json ... ``` 包装
    if text.startswith("```"):
        # 去掉首行 ```
        lines = text.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    # 偶尔模型会加前后多余文字，尝试截取第一个 { 到最后一个 }
    first = text.find("{")
    last = text.rfind("}")
    if first >= 0 and last > first:
        text = text[first:last + 1]
    return json.loads(text)


# 模块级单例，按需创建
_default_client: Optional[LLMClient] = None


def get_client() -> LLMClient:
    global _default_client
    if _default_client is None:
        _default_client = LLMClient()
    return _default_client
