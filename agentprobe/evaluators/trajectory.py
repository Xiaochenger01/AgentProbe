from __future__ import annotations

import json

from ..schemas import Score, TestCase, Trace
from .base import Evaluator, register_evaluator


def _sig(span) -> str:
    try:
        return f"{span.name}|{json.dumps(span.input, ensure_ascii=False, sort_keys=True)}"
    except TypeError:
        return f"{span.name}|{span.input}"


@register_evaluator("trajectory")
class TrajectoryEvaluator(Evaluator):
    """轨迹级指标:不看答案对不对,看"路走得好不好"。
    - llm_calls / tool_calls / tokens / cost / latency:观测指标(不判 pass)
    - steps_within_budget:LLM 调用次数是否在预算内(判 pass)
    - no_loop:是否出现 >=3 次连续重复的相同工具调用(判 pass)
    - redundant_tool_calls:重复的 工具+参数 调用次数(观测,提示浪费)
    """

    def evaluate(self, case: TestCase, output: str, trace: Trace) -> list[Score]:
        llm_n = len(trace.llm_calls())
        tools = trace.tool_calls()
        sigs = [_sig(s) for s in tools]
        redundant = len(sigs) - len(set(sigs))
        loop = False
        run_len = 1
        for i in range(1, len(sigs)):
            run_len = run_len + 1 if sigs[i] == sigs[i - 1] else 1
            if run_len >= 3:
                loop = True
                break
        max_steps = int(self.cfg.get("max_steps", 0) or 0)
        scores = [
            Score(evaluator=self.name, metric="llm_calls", value=float(llm_n)),
            Score(evaluator=self.name, metric="tool_calls", value=float(len(tools))),
            Score(evaluator=self.name, metric="redundant_tool_calls", value=float(redundant),
                  reason="相同工具+参数被重复调用的次数"),
            Score(evaluator=self.name, metric="total_tokens", value=float(trace.total_tokens())),
            Score(evaluator=self.name, metric="latency_ms", value=round(trace.duration_ms(), 1)),
            Score(evaluator=self.name, metric="no_loop", value=0.0 if loop else 1.0,
                  passed=not loop, reason="检测到疑似死循环" if loop else "无循环"),
        ]
        if max_steps:
            ok = llm_n <= max_steps
            scores.append(
                Score(evaluator=self.name, metric="steps_within_budget",
                      value=float(llm_n), passed=ok,
                      reason=f"LLM 调用 {llm_n} 次 / 预算 {max_steps}")
            )
        return scores
