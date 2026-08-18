from __future__ import annotations

from pathlib import Path

from .report import aggregate
from .schemas import RunReport
from .stats import two_proportion_z_test


def load_report(path: str | Path) -> RunReport:
    return RunReport.model_validate_json(Path(path).read_text(encoding="utf-8"))


def _case_pass_map(report: RunReport) -> dict[str, bool]:
    m: dict[str, list[bool]] = {}
    for r in report.results:
        m.setdefault(r.case.id, []).append(r.passed)
    return {cid: all(v) for cid, v in m.items()}


def compare(base: RunReport, new: RunReport) -> dict:
    ab, an = aggregate(base), aggregate(new)
    bmap, nmap = _case_pass_map(base), _case_pass_map(new)
    common = sorted(set(bmap) & set(nmap))
    regressed = [c for c in common if bmap[c] and not nmap[c]]
    fixed = [c for c in common if not bmap[c] and nmap[c]]
    keys = ("pass_rate", "pass_pow_k", "avg_quality", "avg_tokens", "avg_latency_ms")
    display_keys = keys + ("attempts",)

    # 可比性警告:repeat / 数据集 / 用例集合不一致时,指标不可直接比
    warnings: list[str] = []
    if base.repeat != new.repeat:
        warnings.append(
            f"两次运行的 repeat 不一致(k={base.repeat} vs k={new.repeat}),pass^k 语义不可直接比较"
        )
    if base.dataset != new.dataset:
        warnings.append(f"两次运行的数据集不一致({base.dataset} vs {new.dataset})")
    added = sorted(set(nmap) - set(bmap))
    removed = sorted(set(bmap) - set(nmap))
    if added:
        warnings.append(f"新运行多出用例(基线没有): {added}")
    if removed:
        warnings.append(f"新运行缺少用例(基线有): {removed}")

    # pass rate 下降的显著性(pooled z-test,双侧)
    n1 = int(ab["attempts"])
    n2 = int(an["attempts"])
    s1 = int(round(ab["pass_rate"] * n1))
    s2 = int(round(an["pass_rate"] * n2))
    p_value, _z = two_proportion_z_test(s1, n1, s2, n2)
    # pass^k 基于用例级 bootstrap 区间:区间下限跌破基线点估计才计为可信回退
    powk_ci_lo = an["pass_pow_k_ci"][0]

    return {
        "base_run": base.run_id,
        "new_run": new.run_id,
        "base": {k: ab[k] for k in display_keys},
        "new": {k: an[k] for k in display_keys},
        "delta": {k: round(an[k] - ab[k], 4) for k in keys},
        "regressed_cases": regressed,
        "fixed_cases": fixed,
        "warnings": warnings,
        "pass_rate_p_value": round(p_value, 4),
        "pass_pow_k_ci_new": an["pass_pow_k_ci"],
        "pass_pow_k_ci_base": ab["pass_pow_k_ci"],
    }


def gate(cmp: dict, max_drop: float = 0.02, p_threshold: float = 0.10) -> tuple[bool, str]:
    """回归门禁。

    拦截条件(任一):
    1. 出现新失败用例(硬信号,样本级确定性);
    2. pass rate 下降超过 max_drop **且**统计显著(p < p_threshold)——
       防止小样本随机波动被误判为回退;
    3. pass^k 下降超过 max_drop(pass^k 本身已是对可靠性的严格度量)。

    旧版无 p 值字段的 cmp dict 兼容:p 值缺省视为显著(维持原行为)。
    """
    drops = []
    if cmp["regressed_cases"]:
        drops.append(f"新增失败用例 {cmp['regressed_cases']}")
    dr = cmp["delta"]["pass_rate"]
    if dr < -max_drop:
        p = cmp.get("pass_rate_p_value", 0.0)
        if p < p_threshold:
            drops.append(f"pass_rate 下降 {-dr:.1%}(p={p:.3f},统计显著)")
        else:
            drops.append(f"pass_rate 下降 {-dr:.1%} 但统计不显著(p={p:.3f}),仅记录")
    dk = cmp["delta"]["pass_pow_k"]
    if dk < -max_drop:
        ci = cmp.get("pass_pow_k_ci_new")
        if ci is not None and ci[0] >= cmp.get("base", {}).get("pass_pow_k", 1.0):
            drops.append(f"pass^k 下降 {-dk:.1%} 但新运行 CI 覆盖基线点估计,仅记录")
        else:
            drops.append(f"pass^k 下降 {-dk:.1%}")
    # 显著类 drops 才拦截;仅记录类 drops 不拦截
    blocking = [d for d in drops if not d.endswith("仅记录")]
    ok = not blocking
    msg = "[PASS] 门禁通过" if ok else "[FAIL] 门禁拦截: " + "; ".join(blocking)
    if drops:
        msg += " | " + "; ".join(drops)
    return ok, msg


def to_markdown(cmp: dict) -> str:
    lines = [
        f"# 回归对比  base=`{cmp['base_run']}` -> new=`{cmp['new_run']}`",
        "",
        "| 指标 | base | new | Δ |",
        "|---|---|---|---|",
    ]
    for k in cmp["base"]:
        d = cmp["delta"].get(k)
        lines.append(f"| {k} | {cmp['base'][k]} | {cmp['new'][k]} | {d:+}" if d is not None else f"| {k} | {cmp['base'][k]} | {cmp['new'][k]} | - |")
    lines += [
        "",
        f"- 回归用例: {cmp['regressed_cases'] or '无'}",
        f"- 修复用例: {cmp['fixed_cases'] or '无'}",
        f"- pass rate 下降显著性: p={cmp.get('pass_rate_p_value', 'n/a')}"
        f"(双侧 z-test,{cmp.get('base', {}).get('attempts', '?')} vs {cmp.get('new', {}).get('attempts', '?')} 次执行)",
    ]
    for w in cmp.get("warnings", []):
        lines.append(f"- ⚠️ {w}")
    return "\n".join(lines) + "\n"
