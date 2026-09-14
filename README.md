# AgentProbe

**面向 AI Agent 的自动化评测与质量回归平台。**

A lightweight evaluation & regression platform for AI Agents.

`Trace` · `Multi-level Evaluation` · `pass^k` · `Regression Gate` · `Failure RCA` · `DPO Export`

[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-220%20passed-brightgreen)](tests/)
[![CI](https://img.shields.io/badge/CI-eval%20gate-orange)](.github/workflows/eval-gate.yml)

声明式用例 → Trace → 三层评测 → 回归门禁 → 失败归因 →（可选）DPO 偏好对导出。单机可跑，无外部观测服务依赖。

---

## Demo

<p align="center">
  <img src="docs/assets/dashboard-overview.png" alt="Dashboard overview" width="880"/>
</p>

| Overview | Trace | Compare |
|:---:|:---:|:---:|
| <img src="docs/assets/dashboard-overview.png" width="260" alt="overview"/> | <img src="docs/assets/dashboard-trace.png" width="260" alt="trace"/> | <img src="docs/assets/dashboard-compare.png" width="260" alt="compare"/> |

```bash
agentprobe serve --port 8000   # http://localhost:8000/dashboard
```

---

## Capabilities

| Focus | In repo |
|---|---|
| Trace | `agentprobe/tracing.py` |
| Evaluation | `evaluators/` — rules · trajectory · LLM-as-Judge |
| Reliability | `stats.py` — pass rate · **pass^k** · Wilson / bootstrap CI |
| Regression | `regression.py` · [`.github/workflows/eval-gate.yml`](.github/workflows/eval-gate.yml) |
| RCA / DPO | `rca.py` · `dpo_export.py` · `scripts/dpo_train.py` |

```text
Dataset (YAML)
  → Runner (×k) + Agent adapter
  → Trace (Span tree)
  → Rules / Trajectory / Judge
  → Report
       ├─ compare → CI gate (exit 1)
       ├─ rca
       └─ export-dpo → prompt / chosen / rejected
```

---

## Quick Start — Reproducible Mock Benchmark

固定 `seed=21`，11 cases × 3 repeats。零 API Key，用于验证评测、统计、RCA、DPO 导出与 CI 流程。

```bash
git clone https://github.com/Xiaochenger01/AgentProbe.git
cd AgentProbe && pip install -e ".[dev]"

agentprobe run -c configs/example.yaml --mock
agentprobe rca runs/<run_id>.json
agentprobe export-dpo runs/<run_id>.json --out dpo_pairs.jsonl
```

| Metric | Value | Artifact |
|---|---:|---|
| Pass rate | **78.8%** (95% CI 62.3–89.3%) | [`baselines/mock_baseline.json`](baselines/mock_baseline.json) |
| Pass^k (k=3) | **72.7%** (8/11) | same |
| Judge mean | 4.09 / 5 | same |
| Failures → DPO | 7 pairs | `export-dpo` |

`weather_flaky`：pass rate 66.7%，**pass^k = 0**。生产要的是「每次都对」，不是「平均来说对」。

> 以上为 **Mock Benchmark**（可复现、刻意含缺陷），不是真实大模型结果。

---

## Real Agent Evaluation

**Qwen2.5-3B（Ollama）** + tool-calling agent。配置与基线：

| Run | Pass rate | Pass^k | Links |
|---|---:|---:|---|
| v1 · repeat=1 | **90.9%** | 90.9% | [`configs/ollama.yaml`](configs/ollama.yaml) · [`baselines/qwen_baseline.json`](baselines/qwen_baseline.json) |
| v1 · repeat=3 | **75.8%** | 72.7% | [`configs/ollama_k3.yaml`](configs/ollama_k3.yaml) · [`baselines/qwen_k3_baseline.json`](baselines/qwen_k3_baseline.json) |
| v2 · prompt change | **63.6%** | 63.6% | [`configs/ollama_v2.yaml`](configs/ollama_v2.yaml) · [`baselines/qwen_v2_regression.json`](baselines/qwen_v2_regression.json) |

```text
Qwen2.5-3B → openai_tools (ReAct) → AgentProbe
  → Trace → Rules / Trajectory / Judge → Report
```

```bash
ollama pull qwen2.5:3b && ollama serve
agentprobe run -c configs/ollama.yaml
```

细节：[`examples/real_agent/README.md`](examples/real_agent/README.md)

### Prompt regression (v1 → v2)

同一数据集上修改 system prompt 后：

| Version | Pass rate | Pass^k | Gate |
|---|---:|---:|---|
| v1 | 90.9% | 90.9% | — |
| v2 | 63.6% (−27.3 pp) | 63.6% | fail (exit 1) |

新失败：`kb_refund` · `unit_convert` · `kb_then_math` · `prompt_injection`  
修复：`ambiguous_file`

```bash
agentprobe compare baselines/qwen_baseline.json baselines/qwen_v2_regression.json
```

完整记录：[`docs/regression-experiment.md`](docs/regression-experiment.md)

---

## Positioning

AgentProbe 聚焦 **评测 → 回归 → 失败分析 → 训练反馈**，不替代托管观测平台。

| Direction | AgentProbe |
|---|---|
| Trace | 轻量内置 |
| Evaluation | 核心（rules / trajectory / judge） |
| Reliability | pass^k + CI |
| Regression | CI gate（新失败 / 显著下降 / pass^k） |
| Failure analysis | RCA taxonomy |
| Training feedback | DPO export |

可与 Langfuse / Phoenix 等观测后端配合使用。

---

## Layout

```
agentprobe/
├── tracing.py · schemas.py
├── adapters/          # mock · openai_tools · http
├── evaluators/        # rules · trajectory · judge
├── stats.py · calibration.py
├── runner.py · report.py · regression.py
├── rca.py · dpo_export.py
├── dashboard.py · server.py · cli.py
baselines/             # checked-in run artifacts
tests/                 # 220 tests
.github/workflows/eval-gate.yml
```

自定义 Agent：实现 `AgentAdapter.run()`（`adapters/base.py`）。

---

## Status

**Completed:** Trace · multi-level evaluation · pass^k · regression gate · RCA · DPO export · Dashboard · CI · judge calibration tooling

**Future:** LangGraph adapter · OTel exporter · multi-agent sessions · online sampling · judge vs human-label calibration

---

## FAQ

**Why mock by default?**  
Offline, deterministic CI baseline; intentional defects make the eval loop visible without an API key.

**Is the LLM judge reliable?**  
Gate decisions should prefer rules. Judge is a quality signal (voting, pairwise debias, `calibrate`). On 22 samples, LLM vs heuristic judge κ=0.861 — see [`docs/judge_agreement.md`](docs/judge_agreement.md). Human-label calibration still needs an annotation set.

**pytest?**  
pytest covers code; AgentProbe covers agent behavior. This repo runs both in CI.

## License

MIT
