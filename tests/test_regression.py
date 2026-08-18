"""测试回归对比与 CI 门禁:指标 delta 计算 / 新失败用例检测 / 退出码逻辑。"""
import pytest

from agentprobe.regression import compare, gate, load_report, to_markdown
from agentprobe.runner import save_report
from agentprobe.schemas import CaseResult, RunReport, Score, TestCase, Trace


def _report(passed_list: list[bool], agent: str = "demo") -> RunReport:
    results = []
    for i, ok in enumerate(passed_list):
        case = TestCase(id=f"c{i}", task=f"task{i}")
        scores = [
            Score(evaluator="rules", metric="contains", passed=ok, value=1.0 if ok else 0.0),
            Score(evaluator="judge", metric="quality", value=5.0 if ok else 2.0),
        ]
        results.append(
            CaseResult(case=case, output="x", trace=Trace(case_id=f"c{i}"), scores=scores, passed=ok)
        )
    return RunReport(agent=agent, results=results, repeat=1)


def test_identical_reports():
    base = _report([True, True, False])
    new = _report([True, True, False])
    cmp = compare(base, new)
    assert cmp["delta"]["pass_rate"] == 0.0
    assert cmp["delta"]["pass_pow_k"] == 0.0
    assert cmp["regressed_cases"] == []
    assert cmp["fixed_cases"] == []


def test_regression_detected():
    base = _report([True, True, True])
    new = _report([True, False, False])
    cmp = compare(base, new)
    assert cmp["delta"]["pass_rate"] < 0
    assert len(cmp["regressed_cases"]) >= 1


def test_fix_detected():
    base = _report([False, False, True])
    new = _report([True, True, True])
    cmp = compare(base, new)
    assert cmp["delta"]["pass_rate"] > 0
    assert len(cmp["fixed_cases"]) >= 1


def test_different_case_ids_not_compared():
    """只对比共同 case id 的用例。"""
    r1 = RunReport(
        agent="demo",
        results=[
            CaseResult(
                case=TestCase(id="only_in_base", task="t"),
                trace=Trace(case_id="only_in_base"), passed=True,
                scores=[Score(evaluator="rules", metric="x", passed=True)],
            )
        ],
    )
    r2 = RunReport(
        agent="demo",
        results=[
            CaseResult(
                case=TestCase(id="only_in_new", task="t"),
                trace=Trace(case_id="only_in_new"), passed=True,
                scores=[Score(evaluator="rules", metric="x", passed=True)],
            )
        ],
    )
    cmp = compare(r1, r2)
    assert cmp["regressed_cases"] == []
    assert cmp["fixed_cases"] == []
    # 用例集合不一致应产生可比性警告而非崩溃
    assert any("多出用例" in w for w in cmp["warnings"])
    assert any("缺少用例" in w for w in cmp["warnings"])


class TestComparability:
    def test_repeat_mismatch_warns(self):
        base = _report([True, False])
        base.repeat = 1
        new = _report([True, False])
        new.repeat = 3
        cmp = compare(base, new)
        assert any("repeat" in w for w in cmp["warnings"])

    def test_same_config_no_warnings(self):
        base = _report([True, False])
        new = _report([True, False])
        assert compare(base, new)["warnings"] == []

    def test_p_value_present(self):
        base = _report([True, True, True])
        new = _report([True, False, False])
        cmp = compare(base, new)
        assert isinstance(cmp["pass_rate_p_value"], float)
        assert 0.0 <= cmp["pass_rate_p_value"] <= 1.0


class TestGate:
    def test_pass_when_no_regression(self):
        cmp = {"delta": {"pass_rate": 0.0, "pass_pow_k": 0.0}, "regressed_cases": []}
        ok, msg = gate(cmp, max_drop=0.02)
        assert ok
        assert "门禁通过" in msg

    def test_fail_when_pass_rate_drops(self):
        cmp = {"delta": {"pass_rate": -0.05, "pass_pow_k": 0.0}, "regressed_cases": []}
        ok, msg = gate(cmp, max_drop=0.02)
        assert not ok
        assert "门禁拦截" in msg

    def test_fail_when_pass_pow_k_drops(self):
        cmp = {"delta": {"pass_rate": 0.0, "pass_pow_k": -0.03}, "regressed_cases": []}
        ok, msg = gate(cmp, max_drop=0.02)
        assert not ok
        assert "门禁拦截" in msg

    def test_fail_when_new_failures_appear(self):
        cmp = {"delta": {"pass_rate": 0.0, "pass_pow_k": 0.0}, "regressed_cases": ["c1"]}
        ok, msg = gate(cmp, max_drop=0.02)
        assert not ok
        assert "门禁拦截" in msg
        assert "c1" in msg

    def test_within_threshold_passes(self):
        cmp = {"delta": {"pass_rate": -0.01, "pass_pow_k": -0.01}, "regressed_cases": []}
        ok, msg = gate(cmp, max_drop=0.02)
        assert ok

    def test_insignificant_drop_only_recorded(self):
        """下降超阈值但统计不显著(p 大):只记录不拦截,避免小样本随机波动误杀。"""
        cmp = {
            "delta": {"pass_rate": -0.05, "pass_pow_k": 0.0},
            "regressed_cases": [],
            "pass_rate_p_value": 0.5,
        }
        ok, msg = gate(cmp, max_drop=0.02)
        assert ok
        assert "仅记录" in msg

    def test_significant_drop_blocks(self):
        cmp = {
            "delta": {"pass_rate": -0.05, "pass_pow_k": 0.0},
            "regressed_cases": [],
            "pass_rate_p_value": 0.01,
        }
        ok, msg = gate(cmp, max_drop=0.02)
        assert not ok
        assert "统计显著" in msg


class TestCompareMarkdown:
    def test_includes_delta_table(self):
        base = _report([True, False])
        new = _report([False, False])
        cmp = compare(base, new)
        md = to_markdown(cmp)
        assert "回归对比" in md
        assert "base" in md.lower()
        assert "new" in md.lower()
