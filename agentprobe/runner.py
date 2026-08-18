from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .adapters.base import AgentAdapter
from .evaluators.base import Evaluator
from .schemas import CaseResult, RunReport, Score, TestCase, Trace
from .tracing import Tracer


class Runner:
    """评测执行器:数据集 × 被测 Agent × 评测器,支持并发与 k 次重复(用于 pass^k)。"""

    def __init__(
        self,
        agent: AgentAdapter,
        evaluators: list[Evaluator],
        repeat: int = 1,
        concurrency: int = 4,
    ):
        self.agent = agent
        self.evaluators = evaluators
        self.repeat = max(1, int(repeat))
        self.concurrency = max(1, int(concurrency))

    def run(self, cases: list[TestCase], dataset: str = "", config: dict | None = None) -> RunReport:
        jobs = [(case, r) for case in cases for r in range(self.repeat)]
        with ThreadPoolExecutor(max_workers=self.concurrency) as ex:
            results = list(ex.map(self._one, jobs))
        return RunReport(
            agent=self.agent.name,
            model=self.agent.model,
            dataset=str(dataset),
            repeat=self.repeat,
            config=config or {},
            results=results,
        )

    def _one(self, job: tuple[TestCase, int]) -> CaseResult:
        case, ri = job
        tracer = Tracer(Trace(case_id=case.id, agent=self.agent.name, model=self.agent.model))
        # 供适配器做可复现随机性(如 mock 的 seed)使用;自定义适配器可忽略
        tracer.repeat_index = ri
        try:
            output = self.agent.run(case, tracer)
        except Exception as e:  # noqa: BLE001
            output = f"[AGENT_ERROR] {e.__class__.__name__}: {e}"
        trace = tracer.finish(output)

        scores: list[Score] = []
        if output.startswith("[AGENT_ERROR]"):
            scores.append(Score(evaluator="runner", metric="no_crash", passed=False, reason=output[:150]))
        for ev in self.evaluators:
            try:
                scores.extend(ev.evaluate(case, output, trace))
            except Exception as e:  # noqa: BLE001
                scores.append(
                    Score(evaluator=ev.name, metric="evaluator_error", passed=False, reason=str(e)[:150])
                )
        gating = [s for s in scores if s.passed is not None]
        passed = bool(gating) and all(s.passed for s in gating)
        return CaseResult(
            case=case, repeat_index=ri, output=output, trace=trace, scores=scores, passed=passed
        )


def save_report(report: RunReport, out_dir: str | Path = "runs") -> Path:
    from .report import to_markdown

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    json_path = out / f"{report.run_id}.json"
    json_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    (out / f"{report.run_id}.md").write_text(to_markdown(report), encoding="utf-8")
    return json_path
