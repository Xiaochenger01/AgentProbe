"""测试轨迹评测器:步数预算/死循环/冗余调用检测。"""
import pytest

from agentprobe.evaluators.trajectory import TrajectoryEvaluator
from agentprobe.schemas import Score, Span, SpanKind, TestCase, Trace


def _span(kind: SpanKind, name: str, **kw):
    return Span(kind=kind, name=name, end=1.0, **kw)


def test_llm_call_counting():
    tr = Trace()
    tr.spans = [
        _span(SpanKind.LLM, "plan"),
        _span(SpanKind.TOOL, "calc"),
        _span(SpanKind.LLM, "answer"),
    ]
    ev = TrajectoryEvaluator({"type": "trajectory"})
    scores = ev.evaluate(TestCase(task="t"), "", tr)
    llm_calls = next(s for s in scores if s.metric == "llm_calls")
    assert llm_calls.value == 2.0
    assert llm_calls.passed is None  # 观测指标


def test_tool_call_counting():
    tr = Trace()
    tr.spans = [_span(SpanKind.TOOL, "a"), _span(SpanKind.TOOL, "b"), _span(SpanKind.TOOL, "c")]
    ev = TrajectoryEvaluator({"type": "trajectory"})
    scores = ev.evaluate(TestCase(task="t"), "", tr)
    tc = next(s for s in scores if s.metric == "tool_calls")
    assert tc.value == 3.0


def test_redundant_tool_calls():
    tr = Trace()
    tr.spans = [
        _span(SpanKind.TOOL, "weather", input={"city": "北京"}),
        _span(SpanKind.TOOL, "weather", input={"city": "北京"}),  # 重复
        _span(SpanKind.TOOL, "weather", input={"city": "上海"}),
    ]
    ev = TrajectoryEvaluator({"type": "trajectory"})
    scores = ev.evaluate(TestCase(task="t"), "", tr)
    redundant = next(s for s in scores if s.metric == "redundant_tool_calls")
    assert redundant.value == 1.0  # 一对重复


def test_no_loop_normal():
    tr = Trace()
    tr.spans = [
        _span(SpanKind.TOOL, "a"),
        _span(SpanKind.TOOL, "b"),
        _span(SpanKind.TOOL, "a"),
    ]
    ev = TrajectoryEvaluator({"type": "trajectory"})
    scores = ev.evaluate(TestCase(task="t"), "", tr)
    no_loop = next(s for s in scores if s.metric == "no_loop")
    assert no_loop.passed is True


def test_no_loop_detected():
    """连续 3 次相同工具+相同参数 → 死循环。"""
    tr = Trace()
    tr.spans = [
        _span(SpanKind.TOOL, "weather", input={"city": "北京"}),
        _span(SpanKind.TOOL, "weather", input={"city": "北京"}),
        _span(SpanKind.TOOL, "weather", input={"city": "北京"}),  # 3 连击
    ]
    ev = TrajectoryEvaluator({"type": "trajectory"})
    scores = ev.evaluate(TestCase(task="t"), "", tr)
    no_loop = next(s for s in scores if s.metric == "no_loop")
    assert no_loop.passed is False
    assert "死循环" in no_loop.reason


def test_no_loop_interrupted_run():
    """两个相同 + 换工具 + 再两个相同 → 不触发(没有 >=3 连)。"""
    tr = Trace()
    tr.spans = [
        _span(SpanKind.TOOL, "w", input={"city": "北京"}),
        _span(SpanKind.TOOL, "w", input={"city": "北京"}),
        _span(SpanKind.TOOL, "other"),
        _span(SpanKind.TOOL, "w", input={"city": "北京"}),
        _span(SpanKind.TOOL, "w", input={"city": "北京"}),
    ]
    ev = TrajectoryEvaluator({"type": "trajectory"})
    scores = ev.evaluate(TestCase(task="t"), "", tr)
    no_loop = next(s for s in scores if s.metric == "no_loop")
    assert no_loop.passed is True


def test_steps_within_budget_pass():
    tr = Trace()
    tr.spans = [_span(SpanKind.LLM, "a"), _span(SpanKind.LLM, "b")]
    ev = TrajectoryEvaluator({"type": "trajectory", "max_steps": 5})
    scores = ev.evaluate(TestCase(task="t"), "", tr)
    swb = next(s for s in scores if s.metric == "steps_within_budget")
    assert swb.passed is True


def test_steps_within_budget_fail():
    tr = Trace()
    tr.spans = [_span(SpanKind.LLM, f"step{i}") for i in range(8)]
    ev = TrajectoryEvaluator({"type": "trajectory", "max_steps": 5})
    scores = ev.evaluate(TestCase(task="t"), "", tr)
    swb = next(s for s in scores if s.metric == "steps_within_budget")
    assert swb.passed is False


def test_observational_metrics_not_gating():
    """观测指标(llm_calls, tool_calls, tokens, latency)的 passed 应为 None。"""
    tr = Trace()
    tr.spans = [_span(SpanKind.LLM, "a")]
    ev = TrajectoryEvaluator({"type": "trajectory"})
    scores = ev.evaluate(TestCase(task="t"), "", tr)
    observational = {"llm_calls", "tool_calls", "redundant_tool_calls", "total_tokens", "latency_ms"}
    for s in scores:
        if s.metric in observational:
            assert s.passed is None, f"{s.metric} 应为观测指标(passed=None)"


def test_no_max_steps_skips_budget_metric():
    tr = Trace()
    tr.spans = [_span(SpanKind.LLM, "a")]
    ev = TrajectoryEvaluator({"type": "trajectory"})  # 未设置 max_steps
    scores = ev.evaluate(TestCase(task="t"), "", tr)
    assert not any(s.metric == "steps_within_budget" for s in scores)
