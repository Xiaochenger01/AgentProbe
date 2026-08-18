from __future__ import annotations

import json

from ..llm import chat_complete
from ..schemas import TestCase
from ..tools import call_tool, openai_tool_schemas
from ..tracing import Tracer
from .base import AgentAdapter, register_adapter


@register_adapter("openai_tools")
class OpenAIToolsAgent(AgentAdapter):
    """内置的通用工具调用 Agent(ReAct 风格):
    接任意 OpenAI 兼容端点(vLLM / Ollama / DashScope / OpenAI 等),
    自动携带 tools schema,循环执行 思考->调用工具->观察 直至给出最终答案。
    """

    def run(self, case: TestCase, tracer: Tracer) -> str:
        system_prompt = self.cfg.get("system_prompt", "You are a helpful assistant.")
        schemas = openai_tool_schemas(self.cfg.get("tools", []))
        messages: list[dict] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": case.task},
        ]
        max_steps = int(self.cfg.get("max_steps", 6))
        for step in range(max_steps):
            with tracer.span("llm", f"chat#{step + 1}", input=messages[-1].get("content")) as sp:
                out = chat_complete(
                    messages,
                    model=self.model,
                    tools=schemas or None,
                    base_url=self.cfg.get("base_url"),
                    api_key=self.cfg.get("api_key"),
                )
                msg, usage = out["message"], out["usage"]
                sp.prompt_tokens = int(usage.get("prompt_tokens") or 0)
                sp.completion_tokens = int(usage.get("completion_tokens") or 0)
                sp.output = msg.get("content") or str(msg.get("tool_calls"))[:200]
            tool_calls = msg.get("tool_calls") or []
            if not tool_calls:
                return (msg.get("content") or "").strip()
            messages.append(msg)
            for tc in tool_calls:
                name = tc["function"]["name"]
                raw_args = tc["function"].get("arguments") or "{}"
                try:
                    args = json.loads(raw_args)
                except json.JSONDecodeError as e:
                    # 坏 JSON 不静默吞掉:记录错误并把反馈回传给模型,给它自我修正的机会
                    err = f"[ARGUMENT_ERROR] 参数不是合法 JSON: {e}"
                    with tracer.span("tool", name, input=raw_args[:200]) as sp:
                        sp.error = str(e)[:200]
                        sp.output = err
                    messages.append(
                        {"role": "tool", "tool_call_id": tc.get("id", ""),
                         "content": f"{err}。请用合法 JSON 重新调用工具 {name}。"}
                    )
                    continue
                with tracer.span("tool", name, input=args) as sp:
                    try:
                        result = str(call_tool(name, **args))
                    except Exception as e:  # noqa: BLE001
                        result = f"[TOOL_ERROR] {e}"
                        sp.error = str(e)[:200]
                    sp.output = result
                messages.append(
                    {"role": "tool", "tool_call_id": tc.get("id", ""), "content": result}
                )
        return "[MAX_STEPS_EXCEEDED] 未在限定步数内完成任务"
