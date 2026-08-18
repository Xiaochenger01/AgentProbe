"""统计工具:Wilson 置信区间、bootstrapped CI、两比率显著性检验。

动机:小样本评测(如 11 个用例)下,1 个用例翻转就是 ~9% 的波动。
pass rate 必须连同置信区间一起报告;回归门禁只有在下降"既超阈值又统计显著"
时才拦截,否则会误杀纯随机波动。所有随机过程固定 seed,保证 CI 可复现。
"""
from __future__ import annotations

import math
import random

Z95 = 1.959963984540054  # 标准正态 95% 双侧分位点


def wilson_interval(successes: int, trials: int, z: float = Z95) -> tuple[float, float]:
    """二项比率的 Wilson 95% 置信区间。

    相比正态近似(±1.96√(p(1-p)/n)),Wilson 区间在小样本与极端比率
    (0% / 100%)下仍然有效,是二项比率的标准小样本区间估计。
    trials=0 时返回 (0.0, 1.0),表示完全不确定。
    """
    if trials <= 0:
        return 0.0, 1.0
    p = successes / trials
    denom = 1 + z * z / trials
    centre = (p + z * z / (2 * trials)) / denom
    half = z * math.sqrt(p * (1 - p) / trials + z * z / (4 * trials * trials)) / denom
    return max(0.0, centre - half), min(1.0, centre + half)


def bootstrap_ci(
    samples: list[bool], n_resamples: int = 2000, seed: int = 42, z: float = Z95
) -> tuple[float, float]:
    """对布尔样本做 bootstrap 百分位置信区间(默认 95%,seed 固定保证可复现)。

    samples 为空时返回 (0.0, 1.0)。
    """
    if not samples:
        return 0.0, 1.0
    rng = random.Random(seed)
    n = len(samples)
    means: list[float] = []
    for _ in range(n_resamples):
        idx = [rng.randrange(n) for _ in range(n)]
        means.append(sum(samples[i] for i in idx) / n)
    means.sort()
    lo = max(0, int(n_resamples * 0.025))
    hi = min(n_resamples - 1, int(n_resamples * 0.975) - 1)
    return means[lo], means[hi]


def _normal_cdf(x: float) -> float:
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def two_proportion_z_test(
    s1: int, n1: int, s2: int, n2: int
) -> tuple[float, float]:
    """两个比率的显著性检验(双侧 z-test,pooled 方差)。

    返回 (p_value, z_score)。用于 compare:判断 pass rate 的下降是否统计显著。
    样本量为 0 时返回 (1.0, 0.0)(视为无差异)。
    """
    if n1 <= 0 or n2 <= 0:
        return 1.0, 0.0
    p1, p2 = s1 / n1, s2 / n2
    p_pool = (s1 + s2) / (n1 + n2)
    if p_pool <= 0.0 or p_pool >= 1.0:
        # 全过/全挂:无方差,仅当比率不同时视为差异
        return (1.0 if p1 == p2 else 0.0), 0.0
    se = math.sqrt(p_pool * (1 - p_pool) * (1 / n1 + 1 / n2))
    z_score = (p1 - p2) / se
    p_value = 2 * (1 - _normal_cdf(abs(z_score)))
    return p_value, z_score


def summarize_rate(successes: int, trials: int) -> dict:
    """把一个比率的点估计 + Wilson CI 打包成报告字段。"""
    lo, hi = wilson_interval(successes, trials)
    return {
        "rate": round(successes / trials, 4) if trials else 0.0,
        "ci_lower": round(lo, 4),
        "ci_upper": round(hi, 4),
        "n": trials,
    }
