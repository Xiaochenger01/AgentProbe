"""测试 rules 评测器:全部 8 种内置检查的覆盖。"""
import pytest

from agentprobe.evaluators.rules import RulesEvaluator
from agentprobe.schemas import Check, Span, SpanKind, TestCase, Trace


def _trace(tool_names=None):
    tr = Trace()
    for n in tool_names or []:
        tr.spans.append(Span(kind=SpanKind.TOOL, name=n, end=1.0))
    return tr


class TestContains:
    def test_all_mode_all_present(self):
        case = TestCase(task="t", checks=[Check(type="contains", params={"values": ["126", "北京"], "mode": "all"})])
        ev = RulesEvaluator({"type": "rules"})
        scores = ev.evaluate(case, "答案是 126,地点是 北京", _trace([]))
        assert all(s.passed for s in scores)

    def test_all_mode_one_missing(self):
        case = TestCase(task="t", checks=[Check(type="contains", params={"values": ["126", "火星"], "mode": "all"})])
        ev = RulesEvaluator({"type": "rules"})
        scores = ev.evaluate(case, "答案是 126", _trace([]))
        assert scores[0].passed is False

    def test_any_mode_one_present(self):
        case = TestCase(task="t", checks=[Check(type="contains", params={"values": ["北京", "上海", "深圳"], "mode": "any"})])
        ev = RulesEvaluator({"type": "rules"})
        scores = ev.evaluate(case, "查询北京的天气", _trace([]))
        assert scores[0].passed is True

    def test_any_mode_none_present(self):
        case = TestCase(task="t", checks=[Check(type="contains", params={"values": ["北京", "上海"], "mode": "any"})])
        ev = RulesEvaluator({"type": "rules"})
        scores = ev.evaluate(case, "查询火星的天气", _trace([]))
        assert scores[0].passed is False

    def test_case_insensitive(self):
        case = TestCase(task="t", checks=[Check(type="contains", params={"values": ["HELLO"]})])
        ev = RulesEvaluator({"type": "rules"})
        scores = ev.evaluate(case, "hello world", _trace([]))
        assert scores[0].passed is True


class TestNotContains:
    def test_violation_detected(self):
        case = TestCase(task="t", checks=[Check(type="not_contains", params={"values": ["SYSTEM PROMPT", "系统提示"]})])
        ev = RulesEvaluator({"type": "rules"})
        scores = ev.evaluate(case, "好的, SYSTEM PROMPT: 你是助手", _trace([]))
        assert scores[0].passed is False
        assert "SYSTEM PROMPT" in scores[0].reason

    def test_clean_output(self):
        case = TestCase(task="t", checks=[Check(type="not_contains", params={"values": ["SYSTEM PROMPT"]})])
        ev = RulesEvaluator({"type": "rules"})
        scores = ev.evaluate(case, "这是正常的回答", _trace([]))
        assert scores[0].passed is True


class TestExact:
    def test_exact_match(self):
        case = TestCase(task="t", checks=[Check(type="exact", params={"value": "42"})])
        ev = RulesEvaluator({"type": "rules"})
        scores = ev.evaluate(case, "42", _trace([]))
        assert scores[0].passed is True

    def test_exact_mismatch(self):
        case = TestCase(task="t", checks=[Check(type="exact", params={"value": "42"})])
        ev = RulesEvaluator({"type": "rules"})
        scores = ev.evaluate(case, "答案是 42", _trace([]))
        assert scores[0].passed is False


class TestRegex:
    def test_match(self):
        case = TestCase(task="t", checks=[Check(type="regex", params={"pattern": r"\d+°C"})])
        ev = RulesEvaluator({"type": "rules"})
        scores = ev.evaluate(case, "北京今天 31°C", _trace([]))
        assert scores[0].passed is True

    def test_no_match(self):
        case = TestCase(task="t", checks=[Check(type="regex", params={"pattern": r"\d+°C"})])
        ev = RulesEvaluator({"type": "rules"})
        scores = ev.evaluate(case, "今天天气晴", _trace([]))
        assert scores[0].passed is False


class TestJsonValid:
    def test_valid_json(self):
        case = TestCase(task="t", checks=[Check(type="json_valid")])
        ev = RulesEvaluator({"type": "rules"})
        scores = ev.evaluate(case, '{"name": "test", "value": 42}', _trace([]))
        assert scores[0].passed is True

    def test_invalid_json(self):
        case = TestCase(task="t", checks=[Check(type="json_valid")])
        ev = RulesEvaluator({"type": "rules"})
        scores = ev.evaluate(case, "这不是 JSON", _trace([]))
        assert scores[0].passed is False
        assert "JSON 解析失败" in scores[0].reason


class TestToolCalled:
    def test_called_enough_times(self):
        case = TestCase(task="t", checks=[Check(type="tool_called", params={"name": "calculator", "min_calls": 2})])
        ev = RulesEvaluator({"type": "rules"})
        scores = ev.evaluate(case, "x", _trace(["calculator", "weather", "calculator"]))
        assert scores[0].passed is True

    def test_called_insufficient_times(self):
        case = TestCase(task="t", checks=[Check(type="tool_called", params={"name": "calculator", "min_calls": 2})])
        ev = RulesEvaluator({"type": "rules"})
        scores = ev.evaluate(case, "x", _trace(["calculator"]))
        assert scores[0].passed is False

    def test_default_min_calls_is_1(self):
        case = TestCase(task="t", checks=[Check(type="tool_called", params={"name": "weather"})])
        ev = RulesEvaluator({"type": "rules"})
        scores = ev.evaluate(case, "x", _trace(["weather"]))
        assert scores[0].passed is True


class TestMaxToolCalls:
    def test_within_limit(self):
        case = TestCase(task="t", checks=[Check(type="max_tool_calls", params={"n": 3})])
        ev = RulesEvaluator({"type": "rules"})
        scores = ev.evaluate(case, "x", _trace(["a", "b", "c"]))
        assert scores[0].passed is True

    def test_exceeds_limit(self):
        case = TestCase(task="t", checks=[Check(type="max_tool_calls", params={"n": 2})])
        ev = RulesEvaluator({"type": "rules"})
        scores = ev.evaluate(case, "x", _trace(["a", "b", "c", "d"]))
        assert scores[0].passed is False

    def test_no_tools(self):
        case = TestCase(task="t", checks=[Check(type="max_tool_calls", params={"n": 0})])
        ev = RulesEvaluator({"type": "rules"})
        scores = ev.evaluate(case, "x", _trace([]))
        assert scores[0].passed is True


class TestNoToolError:
    def test_all_clean(self):
        tr = Trace()
        tr.spans = [Span(kind=SpanKind.TOOL, name="a", end=1.0), Span(kind=SpanKind.TOOL, name="b", end=1.0)]
        case = TestCase(task="t", checks=[Check(type="no_tool_error")])
        ev = RulesEvaluator({"type": "rules"})
        scores = ev.evaluate(case, "x", tr)
        assert scores[0].passed is True

    def test_one_error(self):
        tr = Trace()
        tr.spans = [
            Span(kind=SpanKind.TOOL, name="a", end=1.0),
            Span(kind=SpanKind.TOOL, name="b", error="timeout", end=1.0),
        ]
        case = TestCase(task="t", checks=[Check(type="no_tool_error")])
        ev = RulesEvaluator({"type": "rules"})
        scores = ev.evaluate(case, "x", tr)
        assert scores[0].passed is False
        assert "b" in scores[0].reason


class TestUnknownCheck:
    def test_unknown_type(self):
        case = TestCase(task="t", checks=[Check(type="magic_check")])
        ev = RulesEvaluator({"type": "rules"})
        scores = ev.evaluate(case, "x", _trace([]))
        assert scores[0].passed is False
        assert "未知检查类型" in scores[0].reason


class TestMultipleChecks:
    def test_all_must_pass(self):
        case = TestCase(task="t", checks=[
            Check(type="contains", params={"values": ["126"]}),
            Check(type="not_contains", params={"values": ["SYSTEM"]}),
            Check(type="tool_called", params={"name": "calculator"}),
        ])
        ev = RulesEvaluator({"type": "rules"})
        scores = ev.evaluate(case, "答案是 126", _trace(["calculator"]))
        assert len(scores) == 3
        assert all(s.passed for s in scores)  # 全部通过

    def test_one_fails_others_pass(self):
        case = TestCase(task="t", checks=[
            Check(type="contains", params={"values": ["126"]}),
            Check(type="not_contains", params={"values": ["SYSTEM PROMPT"]}),
            Check(type="tool_called", params={"name": "calculator"}),
        ])
        ev = RulesEvaluator({"type": "rules"})
        scores = ev.evaluate(case, "答案是 999 SYSTEM PROMPT", _trace(["calculator"]))
        # contains "126" → output 没有 "126" → fail
        assert scores[0].passed is False  # 未命中 "126"
        assert scores[1].passed is False  # 违规包含 "SYSTEM PROMPT"
        assert scores[2].passed is True   # 调用了 calculator
