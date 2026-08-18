from __future__ import annotations

import json
from pathlib import Path

from .schemas import RunReport


def export_dpo(report: RunReport, out_path: str | Path = "dpo_pairs.jsonl") -> int:
    """把评测失败案例转化为 DPO 偏好对,打通『评测 -> 训练』闭环。
    chosen 优先取同一用例通过的输出(真实成功轨迹),否则取参考答案 expected;
    rejected 为失败输出。产出可直接喂给 TRL 的 DPOTrainer。"""
    by: dict[str, list] = {}
    order: list[str] = []
    for r in report.results:
        if r.case.id not in by:
            by[r.case.id] = []
            order.append(r.case.id)
        by[r.case.id].append(r)

    count = 0
    with Path(out_path).open("w", encoding="utf-8") as f:
        for cid in order:
            group = by[cid]
            case = group[0].case
            chosen_pool = [r.output for r in group if r.passed and r.output]
            if not chosen_pool and case.expected:
                chosen_pool = [case.expected]
            if not chosen_pool:
                continue
            for r in group:
                if r.passed or not r.output:
                    continue
                f.write(
                    json.dumps(
                        {
                            "prompt": case.task,
                            "chosen": chosen_pool[0],
                            "rejected": r.output,
                            "case_id": cid,
                            "tags": case.tags,
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
                count += 1
    return count
