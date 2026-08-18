from __future__ import annotations

import json
import re

from ..schemas import Score, TestCase, Trace
from .base import Evaluator, register_evaluator


def _contains(output: str, trace: Trace, p: dict):
    values = [str(v) for v in p.get("values", [])]
    mode = p.get("mode", "all")
    hits = [v for v in values if v.lower() in output.lower()]
    ok = (len(hits) == len(values)) if mode == "all" else (len(hits) > 0)
    return ok, f"命中 {hits or '无'} / 需 {values}({mode})"


def _not_contains(output: str, trace: Trace, p: dict):
    values = [str(v) for v in p.get("values", [])]
    bad = [v for v in values if v.lower() in output.lower()]
    return (not bad), (f"违规包含 {bad}" if bad else "未包含任何禁止内容")


def _exact(output: str, trace: Trace, p: dict):
    target = str(p.get("value", "")).strip()
    ok = output.strip() == target
    return ok, f"期望恰为 '{target}'"


def _regex(output: str, trace: Trace, p: dict):
    pattern = p.get("pattern", "")
    ok = re.search(pattern, output) is not None
    return ok, f"正则 /{pattern}/ {'匹配' if ok else '未匹配'}"


def _json_valid(output: str, trace: Trace, p: dict):
    try:
        json.loads(output)
        return True, "输出为合法 JSON"
    except json.JSONDecodeError as e:
        return False, f"JSON 解析失败: {e}"


def _tool_called(output: str, trace: Trace, p: dict):
    name = p.get("name", "")
    min_calls = int(p.get("min_calls", 1))
    n = sum(1 for s in trace.tool_calls() if s.name == name)
    return n >= min_calls, f"工具 {name} 调用 {n} 次(需≥{min_calls})"


def _max_tool_calls(output: str, trace: Trace, p: dict):
    n = len(trace.tool_calls())
    limit = int(p.get("n", 0))
    return n <= limit, f"工具共调用 {n} 次(上限 {limit})"


def _no_tool_error(output: str, trace: Trace, p: dict):
    errs = [s.name for s in trace.tool_calls() if s.error]
    return (not errs), (f"工具报错: {errs}" if errs else "所有工具调用无异常")


CHECKS = {
    "contains": _contains,
    "not_contains": _not_contains,
    "exact": _exact,
    "regex": _regex,
    "json_valid": _json_valid,
    "tool_called": _tool_called,
    "max_tool_calls": _max_tool_calls,
    "no_tool_error": _no_tool_error,
}


@register_evaluator("rules")
class RulesEvaluator(Evaluator):
    """执行用例中声明式的规则检查(硬断言,全部计入通过判定)。"""

    def evaluate(self, case: TestCase, output: str, trace: Trace) -> list[Score]:
        scores: list[Score] = []
        for c in case.checks:
            fn = CHECKS.get(c.type)
            if fn is None:
                scores.append(
                    Score(evaluator=self.name, metric=c.type, passed=False, reason="未知检查类型")
                )
                continue
            ok, reason = fn(output, trace, c.params)
            scores.append(
                Score(
                    evaluator=self.name,
                    metric=c.type,
                    value=1.0 if ok else 0.0,
                    passed=ok,
                    reason=reason,
                )
            )
        return scores
