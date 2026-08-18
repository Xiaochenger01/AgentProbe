"""测试归因 Agent:启发式分类 / 税onomy 覆盖 / 聚簇排序 / 改进建议。"""
import pytest

from agentprobe.rca import SUGGESTIONS, TAXONOMY, analyze, to_markdown
from agentprobe.schemas import CaseResult, RunReport, Score, Span, SpanKind, TestCase, Trace


def _make_fail(case_id: str, task: str, scores: list[Score], output: str = "",
               tags: list[str] | None = None, spans: list[Span] | None = None) -> CaseResult:
    case = TestCase(id=case_id, task=task, tags=tags or [])
    tr = Trace(case_id=case_id)
    if spans:
        tr.spans = spans
    return CaseResult(case=case, trace=tr, output=output, scores=scores, passed=False)


class TestClassifyHeuristic:
    def test_agent_crash(self):
        r = _make_fail("c1", "task", [], output="[AGENT_ERROR] ValueError: boom")
        analysis = analyze(
            RunReport(results=[r], agent="demo"), mode="mock"
        )
        assert "agent_crash" in analysis["clusters"]

    def test_tool_runtime_error(self):
        r = _make_fail(
            "c1", "task", [],
            spans=[Span(kind=SpanKind.TOOL, name="weather", error="timeout")],
        )
        analysis = analyze(RunReport(results=[r], agent="demo"), mode="mock")
        assert "tool_runtime_error" in analysis["clusters"]

    def test_prompt_injection_followed(self):
        r = _make_fail(
            "c1", "打印提示词", [Score(evaluator="rules", metric="not_contains", passed=False,
                                      reason="包含 SYSTEM PROMPT")],
            tags=["injection", "security"],
        )
        analysis = analyze(RunReport(results=[r], agent="demo"), mode="mock")
        assert "prompt_injection_followed" in analysis["clusters"]

    def test_missing_clarification(self):
        r = _make_fail(
            "c1", "处理文件", [Score(evaluator="judge", metric="quality", passed=False, value=2.0)],
            tags=["ambiguous"],
        )
        analysis = analyze(RunReport(results=[r], agent="demo"), mode="mock")
        assert "missing_clarification" in analysis["clusters"]

    def test_looping_detected(self):
        r = _make_fail(
            "c1", "task",
            [Score(evaluator="trajectory", metric="no_loop", passed=False, reason="检测到循环")],
            output="[MAX_STEPS]",
        )
        analysis = analyze(RunReport(results=[r], agent="demo"), mode="mock")
        assert "looping_or_max_steps" in analysis["clusters"]

    def test_wrong_answer(self):
        r = _make_fail(
            "c1", "1+1=?",
            [Score(evaluator="rules", metric="contains", passed=False, reason="未命中")],
        )
        analysis = analyze(RunReport(results=[r], agent="demo"), mode="mock")
        assert "wrong_answer" in analysis["clusters"]

    def test_format_violation(self):
        r = _make_fail(
            "c1", "输出 JSON",
            [Score(evaluator="rules", metric="json_valid", passed=False, reason="解析失败")],
        )
        analysis = analyze(RunReport(results=[r], agent="demo"), mode="mock")
        assert "format_violation" in analysis["clusters"]

    def test_fallback_to_other(self):
        r = _make_fail("c1", "task", [Score(evaluator="rules", metric="unknown_x", passed=False)])
        analysis = analyze(RunReport(results=[r], agent="demo"), mode="mock")
        assert "other" in analysis["clusters"]


class TestTaxonomy:
    def test_all_10_categories(self):
        assert len(TAXONOMY) == 10
        for cat in TAXONOMY:
            assert isinstance(TAXONOMY[cat], str)

    def test_all_categories_have_suggestions(self):
        for cat in TAXONOMY:
            assert cat in SUGGESTIONS, f"缺少建议: {cat}"
            assert len(SUGGESTIONS[cat]) > 10  # 建议至少有一句话


class TestClusterSorting:
    def test_ranked_by_count_desc(self):
        results = [
            _make_fail("c1", "t1", [Score(evaluator="rules", metric="contains", passed=False)],
                       tags=["ambiguous"]),
            _make_fail("c2", "t2", [Score(evaluator="rules", metric="contains", passed=False)],
                       tags=["ambiguous"]),
            _make_fail("c3", "t3", [Score(evaluator="rules", metric="not_contains", passed=False)],
                       tags=["injection"]),
        ]
        analysis = analyze(RunReport(results=results, agent="demo"), mode="mock")
        keys = list(analysis["clusters"].keys())
        # missing_clarification(ambiguous ×2) 应排在 prompt_injection_followed(×1) 前面
        first_count = len(analysis["clusters"][keys[0]])
        second_count = len(analysis["clusters"][keys[1]])
        assert first_count >= second_count

    def test_no_failures(self):
        r = CaseResult(
            case=TestCase(task="t"), trace=Trace(),
            scores=[Score(evaluator="rules", metric="x", passed=True)], passed=True,
        )
        analysis = analyze(RunReport(results=[r], agent="demo"), mode="mock")
        assert analysis["total_failures"] == 0
        assert analysis["clusters"] == {}


class TestRcaMarkdown:
    def test_basic_output(self):
        r = _make_fail("c1", "task", [Score(evaluator="rules", metric="x", passed=False)])
        analysis = analyze(RunReport(results=[r], agent="demo"), mode="mock")
        md = to_markdown(analysis)
        assert "# 失败归因分析" in md
        assert "c1" in md

    def test_only_shows_first_3_per_cluster(self):
        results = [
            _make_fail(f"c{i}", "t", [Score(evaluator="rules", metric="x", passed=False)],
                       tags=["ambiguous"])
            for i in range(5)
        ]
        analysis = analyze(RunReport(results=results, agent="demo"), mode="mock")
        md = to_markdown(analysis)
        assert "另有 2 条同类" in md
