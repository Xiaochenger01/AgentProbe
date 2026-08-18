from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
import yaml

from . import __version__
from .adapters import build_adapter
from .datasets import generate_cases, load_dataset, save_dataset
from .dpo_export import export_dpo
from .evaluators import build_evaluators
from .regression import compare as compare_reports
from .regression import gate, load_report
from .regression import to_markdown as cmp_md
from .report import to_markdown
from .rca import analyze
from .rca import to_markdown as rca_md
from .runner import Runner, save_report

app = typer.Typer(help=f"AgentProbe v{__version__} —— 给你的 Agent 做体检", no_args_is_help=True)


def _load_cfg(path: str) -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


@app.command()
def run(
    config: str = typer.Option("configs/example.yaml", "--config", "-c", help="评测配置文件"),
    repeat: Optional[int] = typer.Option(None, help="覆盖配置中的重复次数 k"),
    mock: bool = typer.Option(False, "--mock", help="强制全 Mock(离线演示)"),
    seed: Optional[int] = typer.Option(None, "--seed", help="mock 适配器随机种子(CI 确定性基线用)"),
    out_dir: str = typer.Option("runs", help="报告输出目录"),
):
    """执行一次体检:数据集 × 被测 Agent × 评测器,产出 JSON + Markdown 报告。"""
    cfg = _load_cfg(config)
    if mock:
        cfg.setdefault("agent", {})["adapter"] = "mock"
        for ev in cfg.get("evaluators", []):
            if ev.get("type") == "judge":
                ev["mode"] = "mock"
    if seed is not None:
        cfg.setdefault("agent", {})["seed"] = seed
    agent = build_adapter(cfg.get("agent", {}))
    evaluators = build_evaluators(cfg.get("evaluators", []))
    cases = load_dataset(cfg["dataset"])
    k = repeat or int(cfg.get("repeat", 1))
    runner = Runner(agent, evaluators, repeat=k, concurrency=int(cfg.get("concurrency", 4)))
    report = runner.run(cases, dataset=cfg["dataset"], config=cfg)
    path = save_report(report, out_dir)
    typer.echo(to_markdown(report))
    typer.echo(f"报告已保存: {path}(同名 .md 为可读版)")


@app.command()
def compare(
    base: str = typer.Argument(..., help="基线报告 JSON"),
    new: str = typer.Argument(..., help="新报告 JSON"),
    max_drop: float = typer.Option(0.02, help="pass rate / pass^k 允许的最大下降幅度"),
):
    """回归对比 + CI 门禁:指标下降超阈值或出现新失败用例则退出码 1。"""
    cmp = compare_reports(load_report(base), load_report(new))
    typer.echo(cmp_md(cmp))
    ok, msg = gate(cmp, max_drop)
    typer.echo(msg)
    if not ok:
        raise typer.Exit(code=1)


@app.command()
def rca(
    run_path: str = typer.Argument(..., help="报告 JSON 路径"),
    mode: str = typer.Option("mock", help="mock | llm(llm 模式用大模型逐条归因)"),
    model: str = typer.Option("gpt-4o-mini", help="llm 模式的归因模型"),
):
    """失败归因:读取失败轨迹 -> 按失败税onomy聚簇 -> 输出改进建议。"""
    report = load_report(run_path)
    analysis = analyze(report, mode=mode, cfg={"model": model})
    md = rca_md(analysis)
    out = Path(run_path).with_suffix(".rca.md")
    out.write_text(md, encoding="utf-8")
    typer.echo(md)
    typer.echo(f"归因报告已保存: {out}")


@app.command("export-dpo")
def export_dpo_cmd(
    run_path: str = typer.Argument(..., help="报告 JSON 路径"),
    out: str = typer.Option("dpo_pairs.jsonl", help="输出 JSONL 路径"),
):
    """把失败案例导出为 DPO 偏好对(prompt/chosen/rejected),打通评测->训练闭环。"""
    n = export_dpo(load_report(run_path), out)
    typer.echo(f"已导出 {n} 条偏好对 -> {out}")


@app.command()
def gen(
    seed: str = typer.Argument(..., help="种子数据集路径"),
    n: int = typer.Option(9, help="生成用例数量"),
    out: str = typer.Option("examples/generated.yaml", help="输出数据集路径"),
    mode: str = typer.Option("mock", help="mock | llm(llm 模式由出题 Agent 自主设计用例)"),
    model: str = typer.Option("gpt-4o-mini", help="llm 模式的出题模型"),
):
    """出题 Agent:基于种子用例自动扩增边界 / 对抗 / 多跳新用例。"""
    seeds = load_dataset(seed)
    cases = generate_cases(seeds, n=n, mode=mode, cfg={"model": model})
    save_dataset(cases, out)
    typer.echo(f"已生成 {len(cases)} 个用例 -> {out}")


@app.command()
def calibrate(
    run_path: str = typer.Argument(..., help="体检报告 JSON 路径"),
    annotations: str = typer.Option(..., "--annotations", "-a", help="人工标注 JSONL 路径"),
    threshold: float = typer.Option(3.5, help="判官 pass/fail 阈值(binary 标注时)"),
):
    """判官校准:计算判官打分与人工标注的 Cohen's κ(或加权 κ)。

    标注 JSONL 每行: {"case_id": "...", "repeat_index": 0, "passed": true} 或
    {"case_id": "...", "repeat_index": 1, "score": 4}。
    """
    from .calibration import calibrate as run_calibration
    from .calibration import load_annotations, to_markdown as cal_md

    report = load_report(run_path)
    ann = load_annotations(annotations)
    result = run_calibration(report, ann, threshold=threshold)
    typer.echo(cal_md(result))


@app.command()
def serve(
    runs_dir: str = typer.Option("runs", help="报告目录"),
    port: int = typer.Option(8000, help="端口"),
):
    """启动只读 API 服务,浏览历史体检报告(/runs)。"""
    import uvicorn

    from .server import create_app

    uvicorn.run(create_app(runs_dir), host="0.0.0.0", port=port)


if __name__ == "__main__":
    app()
