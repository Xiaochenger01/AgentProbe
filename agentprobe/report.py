from __future__ import annotations

from .schemas import CaseResult, RunReport
from .stats import bootstrap_ci, wilson_interval


def _avg(xs) -> float:
    xs = list(xs)
    return sum(xs) / len(xs) if xs else 0.0


def _group(results: list[CaseResult]):
    order: list[str] = []
    by: dict[str, list[CaseResult]] = {}
    for r in results:
        if r.case.id not in by:
            by[r.case.id] = []
            order.append(r.case.id)
        by[r.case.id].append(r)
    return order, by


def aggregate(report: RunReport) -> dict:
    results = report.results
    attempts = len(results)
    order, by = _group(results)
    quality = [
        s.value for r in results for s in r.scores if s.evaluator == "judge" and s.metric == "quality"
    ]
    tags: dict[str, list[bool]] = {}
    for r in results:
        for t in r.case.tags:
            tags.setdefault(t, []).append(r.passed)
    # 统计 rigor:小样本下比率必须连同置信区间报告
    attempts_ok = sum(1 for r in results if r.passed)
    pass_lo, pass_hi = wilson_interval(attempts_ok, attempts)
    case_ok = [all(x.passed for x in v) for v in by.values()]
    powk_lo, powk_hi = bootstrap_ci(case_ok)
    return {
        "cases": len(by),
        "attempts": attempts,
        "repeat": report.repeat,
        "pass_rate": round(_avg(r.passed for r in results), 4) if attempts else 0.0,
        "pass_rate_ci": [round(pass_lo, 4), round(pass_hi, 4)],
        "pass_pow_k": round(_avg(all(x.passed for x in v) for v in by.values()), 4) if by else 0.0,
        "pass_pow_k_ci": [round(powk_lo, 4), round(powk_hi, 4)],
        "avg_quality": round(_avg(quality), 2),
        "avg_llm_calls": round(_avg(len(r.trace.llm_calls()) for r in results), 2),
        "avg_tool_calls": round(_avg(len(r.trace.tool_calls()) for r in results), 2),
        "avg_tokens": round(_avg(r.trace.total_tokens() for r in results), 1),
        "avg_latency_ms": round(_avg(r.trace.duration_ms() for r in results), 1),
        "by_tag": {t: round(_avg(v), 3) for t, v in sorted(tags.items())},
    }


def to_markdown(report: RunReport) -> str:
    a = aggregate(report)
    order, by = _group(report.results)
    lines = [
        f"# AgentProbe 体检报告 `{report.run_id}`",
        "",
        f"- 被测 Agent: **{report.agent}**(model: `{report.model}`) · 数据集: `{report.dataset}` · 每用例重复 k={report.repeat}",
        f"- 用例 {a['cases']} 个 · 总执行 {a['attempts']} 次",
        f"- **pass rate: {a['pass_rate']:.1%}** (95% CI {a['pass_rate_ci'][0]:.1%}–{a['pass_rate_ci'][1]:.1%}) · "
        f"**pass^k(k 次全过): {a['pass_pow_k']:.1%}** (95% CI {a['pass_pow_k_ci'][0]:.1%}–{a['pass_pow_k_ci'][1]:.1%}) · 判官均分 {a['avg_quality']}/5",
        f"- 平均 LLM 调用 {a['avg_llm_calls']} 次 · 工具调用 {a['avg_tool_calls']} 次 · tokens {a['avg_tokens']} · 时延 {a['avg_latency_ms']} ms",
        "",
        "## 分标签通过率",
        "",
        "| tag | pass rate |",
        "|---|---|",
    ]
    for t, v in a["by_tag"].items():
        lines.append(f"| {t} | {v:.1%} |")
    lines += [
        "",
        "## 用例明细",
        "",
        "| case | 任务 | 通过 | 判分 | 首要失败原因 |",
        "|---|---|---|---|---|",
    ]
    for cid in order:
        g = by[cid]
        ok = sum(1 for r in g if r.passed)
        judge_vals = [
            s.value for r in g for s in r.scores if s.evaluator == "judge" and s.metric == "quality"
        ]
        ff = next((r.first_failure() for r in g if r.first_failure()), None)
        reason = f"`{ff.metric}` {ff.reason[:36]}" if ff else ""
        task_short = g[0].case.task[:22].replace("|", "\\|")
        flag = "[PASS]" if ok == len(g) else ("[WARN]" if ok else "[FAIL]")
        lines.append(f"| {cid} | {task_short} | {ok}/{len(g)} {flag} | {round(_avg(judge_vals),2)} | {reason} |")

    fails = [r for r in report.results if not r.passed][:5]
    if fails:
        lines += ["", "## 失败样例(前 5 条)", ""]
        for r in fails:
            ff = r.first_failure()
            lines += [
                f"<details><summary>[FAIL] {r.case.id} · 第 {r.repeat_index + 1} 次 · {ff.metric if ff else ''}</summary>",
                "",
                f"- 任务:{r.case.task}",
                f"- 输出:{r.output[:180]}",
                f"- 失败原因:{ff.reason if ff else ''}",
                f"- 轨迹:{len(r.trace.spans)} spans(工具 {len(r.trace.tool_calls())} 次,tokens {r.trace.total_tokens()})",
                "",
                "</details>",
            ]
    return "\n".join(lines) + "\n"
