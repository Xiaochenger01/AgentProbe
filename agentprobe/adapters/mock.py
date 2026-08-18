from __future__ import annotations

import random
import re

from ..schemas import TestCase
from ..tools import call_tool, calculator
from ..tracing import Tracer
from .base import AgentAdapter, register_adapter

_CITIES = ["北京", "上海", "深圳"]


@register_adapter("mock")
class MockAgent(AgentAdapter):
    """确定性(带刻意缺陷)的演示 Agent:无需 API Key 即可完整演示评测→归因→DPO 导出闭环。

    刻意保留的缺陷(让体检报告"有病可看"):
    - 遇到提示注入用例会泄露系统提示词;
    - 遇到模糊指令不澄清、直接臆测作答;
    - 带 flaky 标签的用例,约 50% 概率偷懒不调用工具(用于演示 pass^k 稳定性指标)。

    配置 seed(整数或字符串)后,每个用例按其 case.id 派生独立的局部 RNG:
    同一 seed 下每次运行结果完全一致(与线程调度顺序无关),CI 基线因此稳定;
    不配置 seed 时保持原有随机行为。
    """

    def __init__(self, cfg: dict):
        super().__init__(cfg)
        self._seed = self.cfg.get("seed")

    def _rng_for(self, case: TestCase, tracer: Tracer):
        if self._seed is None:
            return random
        # 按 seed + case.id + repeat 派生局部 RNG:同一次运行内 k 次重复各自独立,
        # 不同运行/不同调度顺序下完全一致 → CI 基线稳定
        ri = getattr(tracer, "repeat_index", 0)
        return random.Random(f"{self._seed}:{case.id}:{ri}")

    def run(self, case: TestCase, tracer: Tracer) -> str:
        rng = self._rng_for(case, tracer)
        task = case.task
        with tracer.span("llm", "plan", input=task) as sp:
            sp.prompt_tokens, sp.completion_tokens = 100 + len(task), 32
            sp.output = "制定计划"

        if "injection" in case.tags:
            return self._answer(tracer, "好的,SYSTEM PROMPT: 你是一个企业助手……(系统提示已输出)")
        if "ambiguous" in case.tags:
            return self._answer(tracer, "42")
        if "flaky" in case.tags and rng.random() < 0.5:
            return self._answer(tracer, "今天天气应该还不错。")

        parts: list[str] = []

        fah = re.search(r"(\d+(?:\.\d+)?)\s*华氏", task)
        if fah:
            f = fah.group(1)
            with tracer.span("tool", "calculator", input={"expression": f"({f}-32)*5/9"}) as sp:
                v = call_tool("calculator", expression=f"({f}-32)*5/9")
                sp.output = v
            parts.append(f"{f} 华氏度约等于 {round(float(v), 1)}°C")

        if "天气" in task:
            for city in _CITIES:
                if city in task:
                    with tracer.span("tool", "weather", input={"city": city}) as sp:
                        w = call_tool("weather", city=city)
                        sp.output = w
                    parts.append(str(w))

        kb_num = None
        if any(k in task for k in ("退款", "发票", "会员")):
            with tracer.span("tool", "kb_search", input={"query": task[:20]}) as sp:
                doc = call_tool("kb_search", query=task)
                sp.output = doc
            m2 = re.search(r"(\d+)\s*天内", str(doc))
            if "退款" in task and m2:
                kb_num = m2.group(1)
                parts.append(f"退款政策支持 {kb_num} 天内无理由退款")
            else:
                parts.append(str(doc))

        expr = self._extract_expr(task)
        if "不要调用" in task:
            if expr:
                parts.append(f"{expr} = {calculator(expression=expr)}")
        elif expr and not fah:
            with tracer.span("tool", "calculator", input={"expression": expr}) as sp:
                v = call_tool("calculator", expression=expr)
                sp.output = v
            v2 = self._post_ops(task, str(v), tracer)
            parts.append(f"{expr} = {v}" if v2 == str(v) else f"先得 {v},最终结果 = {v2}")
        elif kb_num:
            v2 = self._post_ops(task, kb_num, tracer)
            if v2 != kb_num:
                parts.append(f"{kb_num} 经计算后 = {v2}")

        if not parts:
            parts.append(case.expected or f"已完成:{task[:30]}")
        return self._answer(tracer, ";".join(parts))

    # ---------------- helpers ----------------

    def _answer(self, tracer: Tracer, text: str) -> str:
        with tracer.span("llm", "answer", input="draft") as sp:
            sp.prompt_tokens, sp.completion_tokens = 60, min(200, 20 + len(text))
            sp.output = text
        return text

    def _extract_expr(self, task: str) -> str:
        t = re.sub(r"\s*加上\s*", "+", task)
        t = re.sub(r"\s*乘以\s*", "*", t)
        t = re.sub(r"\s*除以\s*", "/", t)
        t = re.sub(r"\s+加\s+", "+", t)
        t = re.sub(r"\s+减\s+", "-", t)
        best = ""
        for c in re.findall(r"[\d\.\(\)\+\-\*/ ]{3,}", t):
            c = c.strip(" ,。;;?？")
            if (
                re.search(r"[\+\-\*/]", c)
                and len(re.findall(r"\d+(?:\.\d+)?", c)) >= 2
                and len(c) > len(best)
            ):
                best = c
        return best.strip()

    def _post_ops(self, task: str, value: str, tracer: Tracer) -> str:
        v = value
        m = re.search(r"加上\s*(\d+(?:\.\d+)?)", task)
        if m:
            with tracer.span("tool", "calculator", input={"expression": f"{v}+{m.group(1)}"}) as sp:
                v = str(call_tool("calculator", expression=f"{v}+{m.group(1)}"))
                sp.output = v
        m = re.search(r"乘以\s*(\d+(?:\.\d+)?)", task)
        if m:
            with tracer.span("tool", "calculator", input={"expression": f"{v}*{m.group(1)}"}) as sp:
                v = str(call_tool("calculator", expression=f"{v}*{m.group(1)}"))
                sp.output = v
        return v
