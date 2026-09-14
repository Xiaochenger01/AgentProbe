# AgentProbe

**A lightweight evaluation & regression platform for AI Agents.**

Trace · 3-layer evaluators · pass^k reliability · regression gate · failure RCA · DPO export

[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-220%20passed-brightgreen)](tests/)
[![CI](https://img.shields.io/badge/CI-eval%20gate-orange)](.github/workflows/eval-gate.yml)

面向 AI Agent 的轻量级**评测与回归测试**平台：跑声明式用例 → 记 Trace → 打分 → 对比门禁 → 失败归因 → 可选导出 DPO 偏好对。单机可跑，零外部观测服务依赖。

---

## Demo

<p align="center">
  <img src="docs/assets/dashboard-overview.png" alt="Dashboard overview" width="900"/>
</p>

| Overview | Trace | Regression |
|:---:|:---:|:---:|
| <img src="docs/assets/dashboard-overview.png" width="280"/> | <img src="docs/assets/dashboard-trace.png" width="280"/> | <img src="docs/assets/dashboard-compare.png" width="280"/> |

```bash
agentprobe serve --port 8000
# http://localhost:8000/dashboard
```

截图来自本仓库真实 Dashboard（`baselines/*.json` 载入后 Playwright 抓取）。

---

## What it does

| Capability | Evidence in repo |
|---|---|
| **Trace** | `agentprobe/tracing.py` — Span 树（LLM / Tool / Agent） |
| **Evaluation** | `evaluators/` — rules + trajectory + LLM-as-Judge |
| **Reliability** | `stats.py` — pass rate + **pass^k** + Wilson / bootstrap CI |
| **Regression** | `regression.py` + [`.github/workflows/eval-gate.yml`](.github/workflows/eval-gate.yml) |
| **RCA / DPO** | `rca.py` · `dpo_export.py` · `scripts/dpo_train.py` |

---

## Architecture

```text
Dataset (YAML)
    → Runner (×k repeats) + Agent adapter
    → Trace (Span tree)
    → Rules / Trajectory / Judge
    → Report (JSON + Markdown)
         ├─ compare  → CI gate (exit 1)
         ├─ rca      → failure clusters
         └─ export-dpo → prompt/chosen/rejected JSONL
```

数据模型：`RunReport → CaseResult(×case×k) → Trace → Span`。一次执行通过当且仅当**所有门禁指标**通过。

---

## Quick Start（可复现 Mock）

零 API Key，结果可复现（`seed=21`）：

```bash
git clone https://github.com/Xiaochenger01/AgentProbe.git
cd AgentProbe
pip install -e ".[dev]"

agentprobe run -c configs/example.yaml --mock
agentprobe rca runs/<run_id>.json
agentprobe export-dpo runs/<run_id>.json --out dpo_pairs.jsonl
```

### Reproducible Mock Benchmark

内置 mock Agent **刻意带缺陷**（注入泄露 / 不澄清 / 间歇偷懒），用于验证全链路：

| Metric | Value | Source |
|---|---:|---|
| Pass rate | **78.8%** (95% CI 62.3–89.3%) | [`baselines/mock_baseline.json`](baselines/mock_baseline.json) |
| Pass^k (k=3) | **72.7%** (8/11) | same |
| Judge mean | 4.09 / 5 | same |
| Failures → DPO | 7 pairs | `export-dpo` |

`weather_flaky`：pass rate 视角 66.7%，**pass^k = 0** —— 生产要的是「每次都对」，不是「平均来说对」。

> 这是 **真实跑通的 Mock 基线**，不是真实大模型结果。真实模型见下一节。

---

## Real Agent Experiment

本地 **Qwen2.5-3B（Ollama）** 真实推理结果已入库：

| Run | Pass rate | Pass^k | Config / baseline |
|---|---:|---:|---|
| Qwen v1, repeat=1 | **90.9%** | 90.9% | [`configs/ollama.yaml`](configs/ollama.yaml) · [`baselines/qwen_baseline.json`](baselines/qwen_baseline.json) |
| Qwen v1, repeat=3 | **75.8%** | 72.7% | [`configs/ollama_k3.yaml`](configs/ollama_k3.yaml) · [`baselines/qwen_k3_baseline.json`](baselines/qwen_k3_baseline.json) |
| Qwen v2 (prompt 改动) | **63.6%** | 63.6% | [`configs/ollama_v2.yaml`](configs/ollama_v2.yaml) · [`baselines/qwen_v2_regression.json`](baselines/qwen_v2_regression.json) |

单次 90.9% → 重复 3 次后 pass rate **75.8%**：单次评测会高估可靠性。

完整说明：[`examples/real_agent/README.md`](examples/real_agent/README.md)

```bash
ollama pull qwen2.5:3b && ollama serve
agentprobe run -c configs/ollama.yaml
```

---

## Before / After：回归门禁实战

改 system prompt 后对比（同一数据集、真实 Qwen）：

| Version | Pass rate | Pass^k | Gate |
|---|---:|---:|---|
| v1 | 90.9% | 90.9% | — |
| v2 | 63.6% (−27.3 pp) | 63.6% | ❌ **intercepted** |

- **新失败**：`kb_refund` · `unit_convert` · `kb_then_math` · `prompt_injection`
- **修好**：`ambiguous_file`
- 命令：`agentprobe compare baselines/qwen_baseline.json baselines/qwen_v2_regression.json` → 退出码 **1**

详见 [`docs/regression-experiment.md`](docs/regression-experiment.md)。

---

## vs related tools

| | Langfuse | DeepEval | promptfoo | **AgentProbe** |
|---|---|---|---|---|
| Focus | Hosted tracing | Metric library | CLI / red-team | Eval + regression loop |
| pass^k | ❌ | ❌ | ❌ | ✅ |
| Failure → DPO | ❌ | ❌ | ❌ | ✅ |
| CI regression gate | partial | ✅ | ✅ | ✅ (new-fail + significance) |

定位：**评测优先、可自托管的回归工具**；大规模观测可与 Langfuse / Phoenix 配合。

---

## Project structure

```
agentprobe/
├── tracing.py / schemas.py     # Trace & report models
├── adapters/                   # mock · openai_tools · http
├── evaluators/                 # rules · trajectory · judge
├── stats.py / calibration.py   # CI, z-test, Cohen's κ
├── runner.py / report.py
├── regression.py               # compare + gate
├── rca.py / dpo_export.py
├── dashboard.py / server.py / cli.py
baselines/                      # checked-in real run artifacts
tests/                          # 220 unit tests
.github/workflows/eval-gate.yml
```

接入自定义 Agent：实现 `AgentAdapter.run()` 即可（见 `adapters/base.py`）。

---

## Roadmap

**Completed**
- Core evaluation (rules / trajectory / judge)
- pass^k + confidence intervals
- Regression gate + CI workflow
- Failure RCA + DPO export
- Web Dashboard
- Judge pairwise debias + κ tooling (κ=0.861 judge–judge agreement)

**Future**
- OpenTelemetry exporter
- Multi-agent session evaluation
- Online traffic sampling
- Judge vs human-label calibration (needs annotation set)

---

## FAQ

**Why default mock?**  
Zero-cost, fully reproducible CI baseline, and intentional defects so the eval loop is demonstrable offline.

**Is the LLM judge reliable?**  
Use rules for gate decisions. Judge adds quality signal with self-consistency voting, pairwise position debias, and `calibrate` (κ). Experiment: LLM vs heuristic judge κ=0.861 on 22 samples — see [`docs/judge_agreement.md`](docs/judge_agreement.md). Human-label calibration is still future work.

**pytest vs AgentProbe?**  
pytest → code correctness; AgentProbe → agent behavior. Both belong in CI (this repo runs both).

## License

MIT
