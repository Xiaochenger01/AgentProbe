"""测试统计模块:Wilson 区间 / bootstrap CI / 两比率显著性检验。"""
from agentprobe.stats import (
    bootstrap_ci,
    summarize_rate,
    two_proportion_z_test,
    wilson_interval,
)


class TestWilsonInterval:
    def test_midpoint_classic_value(self):
        """5/10 的 Wilson 95% 区间经典值 ≈ (0.237, 0.763)。"""
        lo, hi = wilson_interval(5, 10)
        assert abs(lo - 0.2366) < 0.005
        assert abs(hi - 0.7634) < 0.005

    def test_zero_successes(self):
        lo, hi = wilson_interval(0, 10)
        assert lo == 0.0
        assert abs(hi - 0.2775) < 0.005

    def test_all_successes(self):
        lo, hi = wilson_interval(10, 10)
        assert abs(lo - 0.7225) < 0.005
        assert abs(hi - 1.0) < 1e-9  # 浮点噪声容忍

    def test_zero_trials_means_unknown(self):
        assert wilson_interval(0, 0) == (0.0, 1.0)

    def test_interval_contains_point_estimate(self):
        for s, n in [(3, 11), (7, 11), (1, 11)]:
            lo, hi = wilson_interval(s, n)
            assert lo <= s / n <= hi


class TestBootstrap:
    def test_contains_point_estimate(self):
        samples = [True] * 9 + [False]
        lo, hi = bootstrap_ci(samples)
        assert lo < 0.9 < hi
        assert lo > 0.4  # 9/10 的 CI 不应宽到没有信息量

    def test_empty(self):
        assert bootstrap_ci([]) == (0.0, 1.0)

    def test_reproducible(self):
        samples = [True, False, True, True, False, True, False, True, True, False]
        assert bootstrap_ci(samples) == bootstrap_ci(samples)


class TestZTest:
    def test_clear_difference_significant(self):
        p, z = two_proportion_z_test(8, 10, 4, 10)
        assert p < 0.1
        assert z > 0

    def test_small_difference_not_significant(self):
        p, _ = two_proportion_z_test(6, 10, 5, 10)
        assert p > 0.5

    def test_zero_samples_no_difference(self):
        assert two_proportion_z_test(0, 0, 5, 10) == (1.0, 0.0)


class TestSummarize:
    def test_fields(self):
        s = summarize_rate(3, 11)
        assert abs(s["rate"] - round(3 / 11, 4)) < 1e-9  # rate 字段四舍五入到 4 位
        assert s["ci_lower"] < s["rate"] < s["ci_upper"]
        assert s["n"] == 11
