# Real Agent Evaluation

Qwen2.5-3B (Ollama) + tool-calling agent, evaluated by AgentProbe.

```text
Qwen2.5-3B
  → openai_tools (ReAct + tools)
  → Runner (×k)
  → Trace
  → Rules / Trajectory / Judge
  → Report / compare / rca / export-dpo
```

## Configs

| File | Notes |
|---|---|
| [`configs/ollama.yaml`](../../configs/ollama.yaml) | v1, `repeat=1` |
| [`configs/ollama_k3.yaml`](../../configs/ollama_k3.yaml) | v1, `repeat=3` |
| [`configs/ollama_v2.yaml`](../../configs/ollama_v2.yaml) | v2 prompt, for regression |

## Baselines

| Artifact | Agent | repeat | Pass rate | Pass^k |
|---|---|---:|---:|---:|
| [`baselines/qwen_baseline.json`](../../baselines/qwen_baseline.json) | qwen-agent | 1 | **90.9%** | 90.9% (10/11) |
| [`baselines/qwen_k3_baseline.json`](../../baselines/qwen_k3_baseline.json) | qwen-agent | 3 | **75.8%** | 72.7% (8/11) |
| [`baselines/qwen_v2_regression.json`](../../baselines/qwen_v2_regression.json) | qwen-agent-v2 | 1 | **63.6%** | 63.6% (7/11) |

`repeat=1` at 90.9% vs `repeat=3` at 75.8%: single-shot scores overstate reliability.

## Run locally

```bash
ollama pull qwen2.5:3b
ollama serve
agentprobe run -c configs/ollama.yaml
agentprobe compare baselines/qwen_baseline.json runs/<new_run>.json
```

`OPENAI_BASE_URL` style endpoint: `http://localhost:11434/v1`.

Prompt regression write-up: [`docs/regression-experiment.md`](../../docs/regression-experiment.md).
