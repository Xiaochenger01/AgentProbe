"""测试判官校准:Cohen's κ / 加权 κ / calibrate 对齐。"""
import pytest

from agentprobe.calibration import (
    calibrate,
    cohens_kappa,
    interpret_kappa,
    load_annotations,
    to_markdown,
    weighted_kappa,
)
from agentprobe.schemas import CaseResult, RunReport, Score, TestCase, Trace


def _report_with_judge(scores: list[float]) -> RunReport:
    results = []
    for i, q in enumerate(scores):
        case = TestCase(id=f"c{i}", task=f"t{i}")
        results.append(
            CaseResult(
                case=case, output="x", trace=Trace(case_id=f"c{i}"),
                scores=[Score(evaluator="judge", metric="quality", value=q)],
            )
        )
    return RunReport(results=results)


class TestCohensKappa:
    def test_perfect_agreement(self):
        assert cohens_kappa([True, True, False, False], [True, True, False, False]) == 1.0

    def test_perfect_disagreement(self):
        assert cohens_kappa([True, False, True, False], [False, True, False, True]) == -1.0

    def test_empty(self):
        assert cohens_kappa([], []) == 0.0

    def test_chance_level_is_zero(self):
        # 判官全 True、人工一半 True 一半 False → κ = 0
        kappa = cohens_kappa([True, True, True, True], [True, True, False, False])
        assert abs(kappa) < 1e-9

    def test_known_value(self):
        # 构造 a=5,b=1,c=1,d=3: n=10, p_o=0.8, p_e=0.52 → κ=0.5833
        judge = [True] * 6 + [False] * 4
        human = [True] * 5 + [False] + [True] + [False] * 3
        assert abs(cohens_kappa(judge, human) - 0.5833) < 1e-3


class TestWeightedKappa:
    def test_perfect(self):
        assert weighted_kappa([5.0, 4.0, 3.0], [5.0, 4.0, 3.0]) == 1.0

    def test_symmetric(self):
        a, b = [5.0, 5.0, 4.0, 3.0], [4.0, 4.0, 3.0, 2.0]
        assert weighted_kappa(a, b) == pytest.approx(weighted_kappa(b, a), rel=1e-9)

    def test_more_agreement_higher_kappa(self):
        """越一致 κ 越高:基本一致 > 0.5,系统性反转 < 0。"""
        agree_a = [1.0, 2.0, 3.0, 4.0, 5.0]
        agree_b = [1.0, 2.0, 3.0, 4.0, 4.0]
        disagree_a = [1.0, 2.0, 3.0, 4.0, 5.0]
        disagree_b = [5.0, 4.0, 3.0, 2.0, 1.0]
        labels = [1, 2, 3, 4, 5]
        k_agree = weighted_kappa(agree_a, agree_b, labels=labels)
        k_disagree = weighted_kappa(disagree_a, disagree_b, labels=labels)
        assert k_agree > 0.5
        assert k_disagree < 0.0
        assert k_agree > k_disagree

    def test_empty(self):
        assert weighted_kappa([], []) == 0.0


class TestInterpret:
    def test_ranges(self):
        assert "poor" in interpret_kappa(-0.1)
        assert "moderate" in interpret_kappa(0.5)
        assert "almost perfect" in interpret_kappa(0.9)


class TestCalibrate:
    def test_binary_perfect(self):
        report = _report_with_judge([4.5, 4.5, 2.0, 2.0])
        ann = {("c0", 0): True, ("c1", 0): True, ("c2", 0): False, ("c3", 0): False}
        result = calibrate(report, ann)
        assert result["n"] == 4
        assert result["kappa"] == 1.0
        assert result["confusion"] == {"tp": 2, "fp": 0, "fn": 0, "tn": 2}

    def test_binary_one_mismatch(self):
        report = _report_with_judge([4.5, 4.5, 2.0, 2.0])
        ann = {("c0", 0): False, ("c1", 0): True, ("c2", 0): False, ("c3", 0): False}
        result = calibrate(report, ann)
        assert result["kappa"] < 1.0
        assert result["confusion"]["fp"] == 1
        assert len(result["mismatches"]) == 1

    def test_ordinal_uses_weighted_kappa(self):
        report = _report_with_judge([5.0, 4.0, 3.0])
        ann = {("c0", 0): 5.0, ("c1", 0): 4.0, ("c2", 0): 3.0}
        result = calibrate(report, ann)
        assert "weighted_kappa" in result
        assert result["weighted_kappa"] == 1.0

    def test_no_matching_annotations(self):
        report = _report_with_judge([4.5])
        ann = {("wrong_id", 0): True}
        result = calibrate(report, ann)
        assert "error" in result

    def test_markdown(self):
        report = _report_with_judge([4.5, 2.0])
        ann = {("c0", 0): True, ("c1", 0): False}
        md = to_markdown(calibrate(report, ann))
        assert "Cohen's κ" in md
        assert "TP=" in md


class TestLoadAnnotations:
    def test_binary_and_ordinal(self, tmp_path):
        p = tmp_path / "labels.jsonl"
        p.write_text(
            '{"case_id": "a", "repeat_index": 0, "passed": true}\n'
            '{"case_id": "b", "repeat_index": 1, "score": 4}\n',
            encoding="utf-8",
        )
        ann = load_annotations(p)
        assert ann[("a", 0)] is True
        assert ann[("b", 1)] == 4.0

    def test_missing_field_raises(self, tmp_path):
        p = tmp_path / "bad.jsonl"
        p.write_text('{"case_id": "a"}\n', encoding="utf-8")
        with pytest.raises(ValueError, match="缺少"):
            load_annotations(p)
