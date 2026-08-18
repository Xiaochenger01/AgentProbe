"""判官间一致性实验:启发式 mock 判官 vs 存储的 LLM 判官打分。

对已有的真实运行(如 runs/52412f21fd04.json、runs/df2478888961.json,判官为
qwen2.5:3b LLM)重新用离线启发式判官打分,计算两者在 pass/fail(阈值 3.5)上
的 Cohen's κ。这是一次诚实的"判官可靠性"度量:κ 越高,说明启发式判官可以作为
LLM 判官的离线代理(以及 CI 里的零成本降级方案)。

用法:
    python scripts/judge_agreement.py runs/52412f21fd04.json runs/df2478888961.json \
        --out runs/judge_agreement.md
"""
from __future__ import annotations

import argparse
from pathlib import Path

from agentprobe.calibration import cohens_kappa, interpret_kappa
from agentprobe.evaluators.judge import JudgeEvaluator
from agentprobe.regression import load_report


def main() -> None:
    parser = argparse.ArgumentParser(description="判官间一致性(Cohen's κ)实验")
    parser.add_argument("reports", nargs="+", help="含 LLM 判官打分的报告 JSON 路径")
    parser.add_argument("--threshold", type=float, default=3.5)
    parser.add_argument("--out", default="docs/judge_agreement.md")
    args = parser.parse_args()

    mock_judge = JudgeEvaluator({"type": "judge", "mode": "mock", "threshold": args.threshold})
    llm_pass: list[bool] = []
    mock_pass: list[bool] = []
    rows: list[tuple[str, int, float, float, str]] = []

    for path in args.reports:
        report = load_report(path)
        for r in report.results:
            llm_scores = [s for s in r.scores
                          if s.evaluator == "judge" and s.metric == "quality"]
            if not llm_scores:
                continue  # 该次运行没有 LLM 判官打分(如 mock judge 运行),跳过
            llm_value = llm_scores[0].value
            mock_scores = mock_judge.evaluate(r.case, r.output, r.trace)
            mock_value = mock_scores[0].value
            llm_pass.append(llm_value >= args.threshold)
            mock_pass.append(mock_value >= args.threshold)
            rows.append((r.case.id, r.repeat_index, llm_value, mock_value, r.output[:60]))

    if not rows:
        raise SystemExit("没有可对齐的判官打分:请传入 judge.mode=llm 的运行报告")

    n = len(rows)
    agree = sum(1 for a, b in zip(llm_pass, mock_pass) if a == b)
    kappa = cohens_kappa(llm_pass, mock_pass)
    lines = [
        "# 判官间一致性实验:LLM 判官 vs 启发式判官",
        "",
        f"- 样本: {n} 条(来自 {len(args.reports)} 次运行)",
        f"- 阈值: {args.threshold}",
        f"- 一致率: **{agree / n:.1%}**",
        f"- Cohen's κ: **{kappa:.3f}** → {interpret_kappa(kappa)}",
        "",
        "> 说明:κ 衡量的是「扣除随机一致后的真实一致」。κ=1 完全一致;κ≈0 与随机无异;",
        "> κ<0 表示系统性分歧。此实验用于回答 README FAQ『判官可靠吗』——",
        "> 在拿到人工标注前,先量化两个判官彼此的一致程度。",
        "",
        "## 逐条对比",
        "",
        "| case | 第k次 | LLM 判官 | 启发式判官 | 输出摘要 |",
        "|---|---|---|---|---|",
    ]
    for case_id, rep, lv, mv, out in rows:
        flag = "✅" if (lv >= args.threshold) == (mv >= args.threshold) else "❌"
        lines.append(f"| `{case_id}` | {rep + 1} | {lv} | {mv} | {flag} {out[:40]} |")
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"agreement={agree}/{n}, kappa={kappa:.3f} -> {out_path}")


if __name__ == "__main__":
    main()
