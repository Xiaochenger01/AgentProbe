from __future__ import annotations

import json
import os
from typing import Any, Optional

import requests


class LLMError(RuntimeError):
    pass


def chat_complete(
    messages: list[dict],
    model: str,
    tools: Optional[list[dict]] = None,
    temperature: float = 0.2,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    timeout: int = 60,
) -> dict:
    """调用任意 OpenAI 兼容的 /chat/completions 端点,返回 {message, usage}。"""
    base_url = (base_url or os.getenv("OPENAI_BASE_URL", "")).rstrip("/")
    api_key = api_key or os.getenv("OPENAI_API_KEY", "")
    if not base_url or not api_key:
        raise LLMError(
            "未配置 OPENAI_BASE_URL / OPENAI_API_KEY;"
            "离线演示请使用 mock 适配器与 mock 判官(configs/example.yaml 默认即是)。"
        )
    payload: dict[str, Any] = {"model": model, "messages": messages, "temperature": temperature}
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"
    resp = requests.post(
        f"{base_url}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json=payload,
        timeout=timeout,
    )
    if resp.status_code != 200:
        raise LLMError(f"LLM HTTP {resp.status_code}: {resp.text[:300]}")
    data = resp.json()
    return {"message": data["choices"][0]["message"], "usage": data.get("usage", {}) or {}}


def extract_json(text: str) -> Any:
    """从模型输出中尽力抽取 JSON(容忍 ```json 围栏与前后噪声)。"""
    text = (text or "").strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    starts = [i for i in (text.find("{"), text.find("[")) if i >= 0]
    if starts:
        text = text[min(starts):]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        for endch in ("}", "]"):
            idx = text.rfind(endch)
            if idx > 0:
                try:
                    return json.loads(text[: idx + 1])
                except json.JSONDecodeError:
                    continue
    raise LLMError(f"无法从模型输出解析 JSON: {text[:200]}")
