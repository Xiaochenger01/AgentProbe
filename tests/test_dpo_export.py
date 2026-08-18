"""测试 DPO 偏好对导出:chosen/rejected 配对逻辑 / JSONL 格式。"""
import json
from pathlib import Path

from agentprobe.dpo_export import export_dpo
from agentprobe.schemas import CaseResult, RunReport, Score, TestCase, Trace


def test_export_single_failure_with_passing_peer(tmp_path: Path):
    """同一用例有一次通过一次失败 → chosen=通过输出, rejected=失败输出。"""
    case = TestCase(id="c1", task="1+1=?", expected="2", tags=["math"])
    results = [
        CaseResult(
            case=case,
            repeat_index=0,
            output="2",
            trace=Trace(case_id="c1"),
            scores=[Score(evaluator="rules", metric="contains", passed=True)],
            passed=True,
        ),
        CaseResult(
            case=case,
            repeat_index=1,
            output="3",
            trace=Trace(case_id="c1"),
            scores=[Score(evaluator="rules", metric="contains", passed=False)],
            passed=False,
        ),
    ]
    out = tmp_path / "test_dpo.jsonl"
    report = RunReport(results=results, agent="demo")
    n = export_dpo(report, str(out))
    assert n == 1
    line = json.loads(out.read_text(encoding="utf-8").splitlines()[0])
    assert line["prompt"] == "1+1=?"
    assert line["chosen"] == "2"
    assert line["rejected"] == "3"
    assert line["case_id"] == "c1"


def test_fallback_to_expected_when_no_passing_peer(tmp_path: Path):
    """没有通过的同用例输出 → chosen 退化为 expected。"""
    case = TestCase(id="c1", task="task", expected="expected_answer")
    results = [
        CaseResult(
            case=case,
            repeat_index=0,
            output="bad answer",
            trace=Trace(case_id="c1"),
            scores=[Score(evaluator="rules", metric="x", passed=False)],
            passed=False,
        ),
    ]
    out = tmp_path / "test_dpo_fallback.jsonl"
    report = RunReport(results=results, agent="demo")
    n = export_dpo(report, str(out))
    assert n == 1
    line = json.loads(out.read_text(encoding="utf-8").splitlines()[0])
    assert line["chosen"] == "expected_answer"
    assert line["rejected"] == "bad answer"


def test_no_chosen_skips(tmp_path: Path):
    """既没有通过的同用例,expected 也为空 → 该失败不导出。"""
    case = TestCase(id="c1", task="task")
    results = [
        CaseResult(
            case=case,
            repeat_index=0,
            output="bad",
            trace=Trace(case_id="c1"),
            scores=[Score(evaluator="rules", metric="x", passed=False)],
            passed=False,
        ),
    ]
    out = tmp_path / "test_dpo_skip.jsonl"
    report = RunReport(results=results, agent="demo")
    n = export_dpo(report, str(out))
    assert n == 0


def test_all_passed_no_export(tmp_path: Path):
    """全部通过 → 无偏好对导出。"""
    case = TestCase(id="c1", task="task")
    results = [
        CaseResult(
            case=case, repeat_index=0, output="ok",
            trace=Trace(case_id="c1"),
            scores=[Score(evaluator="rules", metric="x", passed=True)],
            passed=True,
        ),
    ]
    out = tmp_path / "test_dpo_all_pass.jsonl"
    report = RunReport(results=results, agent="demo")
    n = export_dpo(report, str(out))
    assert n == 0


def test_empty_output_not_exported(tmp_path: Path):
    """失败但 output 为空 → 不导出。"""
    case = TestCase(id="c1", task="task")
    results = [
        CaseResult(
            case=case, repeat_index=0, output="",
            trace=Trace(case_id="c1"),
            scores=[Score(evaluator="rules", metric="x", passed=False)],
            passed=False,
        ),
    ]
    out = tmp_path / "test_dpo_empty.jsonl"
    report = RunReport(results=results, agent="demo")
    n = export_dpo(report, str(out))
    assert n == 0


def test_jsonl_format_utf8(tmp_path: Path):
    """JSONL 为 UTF-8,每条一行。"""
    case = TestCase(id="c1", task="中文任务", expected="中文答案", tags=["math"])
    results = [
        CaseResult(
            case=case, repeat_index=0, output="中文答案",
            trace=Trace(case_id="c1"),
            scores=[Score(evaluator="rules", metric="x", passed=True)], passed=True,
        ),
        CaseResult(
            case=case, repeat_index=1, output="错误",
            trace=Trace(case_id="c1"),
            scores=[Score(evaluator="rules", metric="x", passed=False)], passed=False,
        ),
    ]
    out = tmp_path / "test_dpo_utf8.jsonl"
    report = RunReport(results=results, agent="demo")
    n = export_dpo(report, str(out))
    assert n == 1
    line = json.loads(out.read_text(encoding="utf-8").splitlines()[0])
    assert line["prompt"] == "中文任务"
    assert line["chosen"] == "中文答案"
