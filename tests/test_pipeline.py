from pathlib import Path

from agentprobe.adapters import build_adapter
from agentprobe.datasets import load_dataset
from agentprobe.dpo_export import export_dpo
from agentprobe.evaluators import build_evaluators
from agentprobe.rca import analyze
from agentprobe.regression import compare, gate
from agentprobe.report import aggregate
from agentprobe.runner import Runner, save_report

CFG_EVALS = [
    {"type": "rules"},
    {"type": "trajectory", "max_steps": 6},
    {"type": "judge", "mode": "mock", "threshold": 3.5, "n_samples": 1},
]


def test_end_to_end(tmp_path: Path):
    agent = build_adapter({"adapter": "mock", "name": "demo", "model": "mock-v1"})
    evaluators = build_evaluators(CFG_EVALS)
    cases = load_dataset("examples/dataset.yaml")
    report = Runner(agent, evaluators, repeat=2, concurrency=4).run(cases, dataset="examples/dataset.yaml")

    agg = aggregate(report)
    assert agg["cases"] == len(cases)
    assert agg["attempts"] == len(cases) * 2
    assert 0.0 < agg["pass_rate"] < 1.0  # 刻意缺陷保证既有过也有挂

    path = save_report(report, tmp_path)
    assert path.exists() and path.with_suffix(".md").exists()

    n = export_dpo(report, tmp_path / "dpo.jsonl")
    assert n > 0  # ambiguous / injection 带 expected,必产生偏好对

    analysis = analyze(report, mode="mock")
    assert analysis["total_failures"] > 0 and analysis["clusters"]

    cmp = compare(report, report)
    ok, _ = gate(cmp, max_drop=0.02)
    assert ok
