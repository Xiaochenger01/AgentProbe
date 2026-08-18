"""测试数据模型: Trace / Span / Score / CaseResult / RunReport 的行为正确性。"""
import time

from agentprobe.schemas import (
    CaseResult,
    Check,
    RunReport,
    Score,
    Span,
    SpanKind,
    TestCase,
    Trace,
    new_id,
)


class TestSpan:
    def test_defaults(self):
        sp = Span(kind=SpanKind.LLM, name="test")
        assert len(sp.id) == 12
        assert sp.parent_id is None
        assert sp.error is None
        assert sp.end is None
        assert sp.prompt_tokens == 0
        assert sp.completion_tokens == 0
        assert sp.cost == 0.0
        assert sp.meta == {}

    def test_latency(self):
        sp = Span(kind=SpanKind.TOOL, name="calc", start=100.0, end=100.5)
        assert sp.latency_ms() == 500.0

    def test_latency_unfinished(self):
        sp = Span(kind=SpanKind.LLM, name="x")
        assert sp.latency_ms() == 0.0

    def test_input_output_roundtrip(self):
        sp = Span(kind=SpanKind.TOOL, name="w", input={"city": "北京"}, output="晴 31°C")
        assert sp.input == {"city": "北京"}
        assert sp.output == "晴 31°C"


class TestTrace:
    def _trace(self) -> Trace:
        tr = Trace(case_id="c1", agent="demo", model="m1")
        tr.spans = [
            Span(kind=SpanKind.LLM, name="plan", prompt_tokens=10, completion_tokens=5),
            Span(kind=SpanKind.TOOL, name="calculator", prompt_tokens=0, completion_tokens=0),
            Span(kind=SpanKind.TOOL, name="weather", error="timeout"),
            Span(kind=SpanKind.LLM, name="answer", prompt_tokens=20, completion_tokens=8),
        ]
        return tr

    def test_spans_of(self):
        tr = self._trace()
        assert len(tr.spans_of(SpanKind.LLM)) == 2
        assert len(tr.spans_of(SpanKind.TOOL)) == 2
        assert len(tr.spans_of(SpanKind.JUDGE)) == 0

    def test_tool_calls_and_llm_calls(self):
        tr = self._trace()
        assert len(tr.tool_calls()) == 2
        assert len(tr.llm_calls()) == 2

    def test_total_tokens(self):
        tr = self._trace()
        assert tr.total_tokens() == 10 + 5 + 20 + 8  # = 43

    def test_cost_default_zero(self):
        tr = self._trace()
        assert tr.total_cost() == 0.0

    def test_has_error(self):
        tr = self._trace()
        assert tr.has_error()

        tr2 = Trace()
        tr2.spans = [Span(kind=SpanKind.LLM, name="ok")]
        assert not tr2.has_error()

    def test_duration(self):
        tr = Trace(started=100.0, ended=101.2)
        assert abs(tr.duration_ms() - 1200.0) < 0.001

    def test_duration_unfinished(self):
        tr = Trace()
        assert tr.duration_ms() == 0.0

    def test_digest_includes_all_spans(self):
        tr = self._trace()
        d = tr.digest()
        assert "[llm]" in d
        assert "[tool]" in d
        assert "weather" in d

    def test_digest_truncation(self):
        tr = self._trace()
        d = tr.digest(max_chars=20)
        assert len(d) <= 20


class TestScore:
    def test_gating_score(self):
        s = Score(evaluator="rules", metric="contains", value=1.0, passed=True)
        assert s.passed is True

    def test_observational_score(self):
        s = Score(evaluator="trajectory", metric="llm_calls", value=5.0)
        assert s.passed is None  # 纯观测指标,不参与 pass 判定


class TestCaseResult:
    def test_first_failure_returns_none_when_all_pass(self):
        r = CaseResult(
            case=TestCase(task="t"),
            trace=Trace(),
            scores=[
                Score(evaluator="rules", metric="x", passed=True),
                Score(evaluator="judge", metric="quality", passed=True, value=4.0),
            ],
        )
        assert r.first_failure() is None

    def test_first_failure_returns_first_failed(self):
        r = CaseResult(
            case=TestCase(task="t"),
            trace=Trace(),
            scores=[
                Score(evaluator="rules", metric="a", passed=True),
                Score(evaluator="rules", metric="b", passed=False, reason="bad"),
                Score(evaluator="rules", metric="c", passed=False, reason="worse"),
            ],
        )
        ff = r.first_failure()
        assert ff is not None
        assert ff.metric == "b"

    def test_passed_defaults_false(self):
        r = CaseResult(case=TestCase(task="t"), trace=Trace())
        assert r.passed is False


class TestRunReport:
    def test_json_roundtrip(self, tmp_path):
        report = RunReport(agent="demo", model="m1", dataset="d.yaml", repeat=3)
        report.results = [
            CaseResult(
                case=TestCase(id="c1", task="hello"),
                trace=Trace(case_id="c1"),
                scores=[Score(evaluator="rules", metric="x", passed=True)],
                passed=True,
            )
        ]
        p = tmp_path / "r.json"
        p.write_text(report.model_dump_json(indent=2), encoding="utf-8")
        loaded = RunReport.model_validate_json(p.read_text(encoding="utf-8"))
        assert loaded.run_id == report.run_id
        assert loaded.repeat == 3
        assert len(loaded.results) == 1
        assert loaded.results[0].passed


class TestCheck:
    def test_default_params(self):
        c = Check(type="contains")
        assert c.params == {}

    def test_with_params(self):
        c = Check(type="contains", params={"values": ["hello"], "mode": "any"})
        assert c.params["values"] == ["hello"]


class TestNewId:
    def test_length_and_uniqueness(self):
        ids = {new_id() for _ in range(100)}
        assert len(ids) == 100
        assert all(len(i) == 12 for i in ids)
