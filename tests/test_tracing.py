"""测试链路追踪器:span 树结构 / 嵌套 / 错误捕获 / finish 语义。"""
import pytest

from agentprobe.schemas import SpanKind, Trace
from agentprobe.tracing import Tracer


class TestTracerBasic:
    def test_single_span(self):
        tracer = Tracer()
        with tracer.span("llm", "test_span", input="hello") as sp:
            sp.output = "world"
            sp.prompt_tokens = 100
        trace = tracer.finish("final")
        assert len(trace.spans) == 1
        assert trace.spans[0].name == "test_span"
        assert trace.spans[0].input == "hello"
        assert trace.spans[0].output == "world"
        assert trace.spans[0].prompt_tokens == 100
        assert trace.spans[0].end is not None
        assert trace.final_output == "final"
        assert trace.ended is not None

    def test_span_kind_from_string(self):
        tracer = Tracer()
        with tracer.span("llm", "x"):
            pass
        trace = tracer.finish("")
        assert trace.spans[0].kind == SpanKind.LLM

    def test_span_kind_from_enum(self):
        tracer = Tracer()
        with tracer.span(SpanKind.TOOL, "y"):
            pass
        trace = tracer.finish("")
        assert trace.spans[0].kind == SpanKind.TOOL


class TestSpanHierarchy:
    def test_parent_id_chains(self):
        tracer = Tracer()
        with tracer.span("agent", "root") as root:
            with tracer.span("llm", "child"):
                pass
        trace = tracer.finish("")
        assert len(trace.spans) == 2
        child = trace.spans[1]
        assert child.parent_id == root.id

    def test_deeply_nested(self):
        tracer = Tracer()
        with tracer.span("agent", "a") as a:
            with tracer.span("llm", "b") as b:
                with tracer.span("tool", "c") as c:
                    pass
        trace = tracer.finish("")
        spans_by_id = {s.id: s for s in trace.spans}
        assert spans_by_id[c.id].parent_id == b.id
        assert spans_by_id[b.id].parent_id == a.id
        assert spans_by_id[a.id].parent_id is None


class TestErrorHandling:
    def test_exception_captured_in_span(self):
        tracer = Tracer()
        with pytest.raises(ValueError, match="boom"):
            with tracer.span("tool", "risky"):
                raise ValueError("boom")
        trace = tracer.finish("error_output")
        assert trace.spans[0].error == "ValueError: boom"

    def test_exception_does_not_lose_final_output(self):
        tracer = Tracer()
        try:
            with tracer.span("tool", "risky"):
                raise RuntimeError("fail")
        except RuntimeError:
            pass
        trace = tracer.finish("graceful fallback")
        assert trace.final_output == "graceful fallback"
        assert "RuntimeError: fail" in trace.spans[0].error


class TestFinish:
    def test_sets_timestamp(self):
        tracer = Tracer()
        with tracer.span("llm", "x"):
            pass
        trace = tracer.finish("done")
        assert trace.ended is not None
        assert trace.final_output == "done"
        assert trace.duration_ms() >= 0

    def test_existing_trace_used(self):
        existing = Trace(case_id="pre_existing")
        tracer = Tracer(existing)
        with tracer.span("llm", "x"):
            pass
        trace = tracer.finish("")
        assert trace.case_id == "pre_existing"
