"""测试报告聚合与 Markdown 生成。"""
import pytest

from agentprobe.report import aggregate, to_markdown
from agentprobe.schemas import CaseResult, RunReport, Score, TestCase, Trace


def _report(passed_list: list[bool], repeat: int = 1) -> RunReport:
    results = []
    for i, ok in enumerate(passed_list):
        case = TestCase(id=f"c{i}", task=f"task{i}", tags=["math"] if i % 2 == 0 else ["kb"])
        judge_val = 5.0 if ok else 2.0
        for ri in range(repeat):
            results.append(CaseResult(
                case=case, repeat_index=ri, output="x",
                trace=Trace(case_id=f"c{i}"),
                scores=[
                    Score(evaluator="rules", metric="contains", passed=ok, value=1.0 if ok else 0.0),
                    Score(evaluator="judge", metric="quality", passed=ok, value=judge_val),
                    Score(evaluator="trajectory", metric="llm_calls", value=2.0),
                    Score(evaluator="trajectory", metric="tool_calls", value=1.0),
                ],
                passed=ok,
            ))
    return RunReport(agent="demo", results=results, repeat=repeat)


class TestAggregate:
    def test_all_pass(self):
        r = _report([True, True, True])
        a = aggregate(r)
        assert a["pass_rate"] == 1.0
        assert a["pass_pow_k"] == 1.0
        assert a["cases"] == 3
        assert a["attempts"] == 3

    def test_all_fail(self):
        r = _report([False, False])
        a = aggregate(r)
        assert a["pass_rate"] == 0.0
        assert a["pass_pow_k"] == 0.0

    def test_mixed(self):
        r = _report([True, False, True])
        a = aggregate(r)
        assert 0.6 < a["pass_rate"] < 0.7  # 2/3
        assert 0.6 < a["pass_pow_k"] < 0.7  # 每个用例 1 次 repeat, pass^k = pass_rate

    def test_repeat_handling(self):
        """同一用例 repeat=2:一次通过一次失败 → pass_rate 算 attempt,pass^k 算 case 全过。"""
        case = TestCase(id="c0", task="t")
        results = [
            CaseResult(case=case, repeat_index=0, output="ok", trace=Trace(case_id="c0"),
                       scores=[Score(evaluator="rules", metric="x", passed=True)], passed=True),
            CaseResult(case=case, repeat_index=1, output="bad", trace=Trace(case_id="c0"),
                       scores=[Score(evaluator="rules", metric="x", passed=False)], passed=False),
        ]
        r = RunReport(agent="demo", results=results, repeat=2)
        a = aggregate(r)
        assert a["pass_rate"] == 0.5  # 1/2 次通过
        assert a["pass_pow_k"] == 0.0  # 不是两次全过

    def test_repeat_all_pass(self):
        case = TestCase(id="c0", task="t")
        results = [
            CaseResult(case=case, repeat_index=0, output="ok", trace=Trace(case_id="c0"),
                       scores=[Score(evaluator="rules", metric="x", passed=True)], passed=True),
            CaseResult(case=case, repeat_index=1, output="ok", trace=Trace(case_id="c0"),
                       scores=[Score(evaluator="rules", metric="x", passed=True)], passed=True),
        ]
        r = RunReport(agent="demo", results=results, repeat=2)
        a = aggregate(r)
        assert a["pass_rate"] == 1.0
        assert a["pass_pow_k"] == 1.0

    def test_by_tag(self):
        r = _report([True, True, False])
        a = aggregate(r)
        assert "math" in a["by_tag"]
        assert "kb" in a["by_tag"]

    def test_avg_quality(self):
        r = _report([True, False, True])
        a = aggregate(r)
        assert 4.0 <= a["avg_quality"] <= 5.0

    def test_empty_report(self):
        r = RunReport(agent="demo")
        a = aggregate(r)
        assert a["cases"] == 0
        assert a["pass_rate"] == 0.0


class TestToMarkdown:
    def test_includes_key_sections(self):
        r = _report([True, False])
        md = to_markdown(r)
        assert "体检报告" in md
        assert "pass rate" in md.lower()
        assert "用例明细" in md
        assert "分标签通过率" in md

    def test_failure_section_when_failures(self):
        r = _report([False, True])
        md = to_markdown(r)
        assert "失败样例" in md

    def test_no_failure_section_when_all_pass(self):
        r = _report([True, True])
        md = to_markdown(r)
        assert "失败样例" not in md
