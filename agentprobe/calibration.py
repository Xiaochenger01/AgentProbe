"""判官校准:Cohen's κ / 加权 κ 与判官-人工标注一致性分析。

LLM-as-Judge 是"用魔法评价魔法",判官本身必须先被评估。
本模块把判官打分与人工标注对齐,产出:
- 一致率 (agreement) 与 Cohen's κ(binary:pass/fail 时)
- 加权 κ(线性权重,ordinal 1-5 分时)
- 混淆矩阵与不一致样本清单(供人工复核)

标注文件格式(JSONL),每行一条:
    {"case_id": "math_simple", "repeat_index": 0, "passed": true}      # binary
    {"case_id": "kb_refund", "repeat_index": 1, "score": 4}            # ordinal 1-5
"""
from __future__ import annotations

import json
from pathlib import Path

from .schemas import RunReport

# Landis & Koch (1977) 的 κ 解释标准
KAPPA_INTERPRETATION = [
    (0.0, "poor(差,判官不可信)"),
    (0.2, "slight(轻微)"),
    (0.4, "fair(一般)"),
    (0.6, "moderate(中等)"),
    (0.8, "substantial(良好)"),
    (1.01, "almost perfect(几乎完美)"),
]


def load_annotations(path: str | Path) -> dict[tuple[str, int], float | bool]:
    """读取人工标注 JSONL,返回 {(case_id, repeat_index): score|passed}。"""
    out: dict[tuple[str, int], float | bool] = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        item = json.loads(line)
        key = (str(item["case_id"]), int(item.get("repeat_index", 0)))
        if "score" in item:
            out[key] = float(item["score"])
        elif "passed" in item:
            out[key] = bool(item["passed"])
        else:
            raise ValueError(f"标注行缺少 score/passed 字段: {item}")
    return out


def cohens_kappa(judge: list[bool], human: list[bool]) -> float:
    """binary 判定的 Cohen's κ。judge 与 human 等长。空输入返回 0.0。"""
    n = len(judge)
    if n == 0:
        return 0.0
    a = sum(1 for j, h in zip(judge, human) if j and h)
    b = sum(1 for j, h in zip(judge, human) if j and not h)
    c = sum(1 for j, h in zip(judge, human) if not j and h)
    d = sum(1 for j, h in zip(judge, human) if not j and not h)
    p_o = (a + d) / n
    p_e = ((a + b) * (a + c) + (c + d) * (b + d)) / (n * n)
    if p_e >= 1.0:
        return 1.0 if p_o >= 1.0 else 0.0
    return (p_o - p_e) / (1 - p_e)


def weighted_kappa(a: list[float], b: list[float], labels: list[int] | None = None) -> float:
    """ordinal 打分的加权 κ(线性权重 1 - |i-j|/(max-min))。

    labels 缺省时取输入中出现的整数分数(1-5 分制)。
    """
    n = len(a)
    if n == 0:
        return 0.0
    if labels is None:
        vals = {int(round(x)) for x in a + b}
        labels = sorted(vals)
    k = len(labels)
    idx = {v: i for i, v in enumerate(labels)}
    w_max = k - 1
    obs = [[0] * k for _ in range(k)]
    for x, y in zip(a, b):
        obs[idx[int(round(x))]][idx[int(round(y))]] += 1
    p_o = 0.0
    for i in range(k):
        for j in range(k):
            w = 1 - abs(i - j) / w_max if w_max else 1.0
            p_o += w * obs[i][j] / n
    row = [sum(r) for r in obs]
    col = [sum(obs[i][j] for i in range(k)) for j in range(k)]
    p_e = 0.0
    for i in range(k):
        for j in range(k):
            w = 1 - abs(i - j) / w_max if w_max else 1.0
            p_e += w * (row[i] / n) * (col[j] / n)
    if p_e >= 1.0:
        return 1.0 if p_o >= 1.0 else 0.0
    return (p_o - p_e) / (1 - p_e)


def interpret_kappa(kappa: float) -> str:
    for bound, label in KAPPA_INTERPRETATION:
        if kappa < bound:
            return label
    return KAPPA_INTERPRETATION[-1][1]


def calibrate(
    report: RunReport,
    annotations: dict[tuple[str, int], float | bool],
    threshold: float = 3.5,
) -> dict:
    """对齐判官打分与人工标注,返回校准分析结果。

    标注为 bool → 判官按 quality 分数 >= threshold 转 pass/fail,计算 Cohen's κ;
    标注为 float(1-5 分)→ 与判官 quality 分数直接计算加权 κ。
    """
    judge_scores: dict[tuple[str, int], float] = {}
    outputs: dict[tuple[str, int], str] = {}
    for r in report.results:
        q = [s.value for s in r.scores if s.evaluator == "judge" and s.metric == "quality"]
        if q:
            judge_scores[(r.case.id, r.repeat_index)] = q[0]
        outputs[(r.case.id, r.repeat_index)] = r.output

    matched = sorted(set(annotations) & set(judge_scores))
    missing = sorted(set(annotations) - set(judge_scores))
    if not matched:
        return {
            "n": 0, "missing_annotations": [{"key": k} for k in missing],
            "error": "没有可对齐的标注:请确认 case_id/repeat_index 与报告一致,且该次运行启用了 judge 评测器。",
        }

    binary = all(isinstance(v, bool) for v in annotations.values())
    judge_pass: list[bool] = []
    human_pass: list[bool] = []
    judge_vals: list[float] = []
    human_vals: list[float] = []
    mismatches: list[dict] = []

    for key in matched:
        ann = annotations[key]
        js = judge_scores[key]
        if binary:
            hp = bool(ann)
            jp = js >= threshold
            judge_pass.append(jp)
            human_pass.append(hp)
            if jp != hp:
                mismatches.append({
                    "case_id": key[0], "repeat": key[1],
                    "judge_score": js, "judge_pass": jp,
                    "human_pass": hp, "output": outputs[key][:80],
                })
        else:
            judge_vals.append(js)
            human_vals.append(float(ann))
            if abs(js - float(ann)) >= 1.0:
                mismatches.append({
                    "case_id": key[0], "repeat": key[1],
                    "judge_score": js, "human_score": float(ann),
                    "output": outputs[key][:80],
                })

    if binary:
        n = len(matched)
        tp = sum(1 for j, h in zip(judge_pass, human_pass) if j and h)
        fp = sum(1 for j, h in zip(judge_pass, human_pass) if j and not h)
        fn = sum(1 for j, h in zip(judge_pass, human_pass) if not j and h)
        tn = sum(1 for j, h in zip(judge_pass, human_pass) if not j and not h)
        kappa = cohens_kappa(judge_pass, human_pass)
        return {
            "n": n,
            "agreement": round((tp + tn) / n, 4) if n else 0.0,
            "kappa": round(kappa, 4),
            "interpretation": interpret_kappa(kappa),
            "confusion": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
            "mismatches": mismatches[:20],
            "missing_annotations": [{"key": k} for k in missing],
        }
    kappa = weighted_kappa(judge_vals, human_vals, labels=[1, 2, 3, 4, 5])
    return {
        "n": len(matched),
        "weighted_kappa": round(kappa, 4),
        "interpretation": interpret_kappa(kappa),
        "mismatches": mismatches[:20],
        "missing_annotations": [{"key": k} for k in missing],
    }


def to_markdown(result: dict) -> str:
    """校准结果 → Markdown。"""
    if result.get("error"):
        lines = [f"# 判官校准:失败", "", f"- {result['error']}", ""]
        if result.get("missing_annotations"):
            lines.append("未对齐的标注键:")
            for m in result["missing_annotations"][:10]:
                lines.append(f"- {m['key']}")
        return "\n".join(lines) + "\n"

    lines = [f"# 判官校准(与人工标注一致性,n={result['n']})", ""]
    if "kappa" in result:
        lines += [
            f"- 一致率: **{result['agreement']:.1%}**",
            f"- Cohen's κ: **{result['kappa']}** → {result['interpretation']}",
            f"- 混淆矩阵: TP={result['confusion']['tp']} FP={result['confusion']['fp']} "
            f"FN={result['confusion']['fn']} TN={result['confusion']['tn']}",
        ]
    else:
        lines += [
            f"- 加权 κ(线性权重): **{result['weighted_kappa']}** → {result['interpretation']}",
        ]
    if result["mismatches"]:
        lines += ["", "## 不一致样本(供人工复核)", ""]
        for m in result["mismatches"]:
            lines.append(f"- `{m['case_id']}`(第 {m['repeat'] + 1} 次): 判官 {m['judge_score']} "
                         f"vs 人工 {m.get('human_score', m.get('human_pass'))} · {m['output']}")
    if result.get("missing_annotations"):
        lines += ["", f"## 未对齐的标注({len(result['missing_annotations'])} 条)", ""]
        for m in result["missing_annotations"][:10]:
            lines.append(f"- {m['key']}")
    return "\n".join(lines) + "\n"
