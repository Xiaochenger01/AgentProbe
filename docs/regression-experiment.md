# Prompt Regression Experiment

同一数据集上，比较 Qwen Agent **v1** 与修改 system prompt 后的 **v2**。

## Setup

| Version | Config | Prompt |
|---|---|---|
| v1 | [`configs/ollama.yaml`](../configs/ollama.yaml) | baseline system prompt |
| v2 | [`configs/ollama_v2.yaml`](../configs/ollama_v2.yaml) | stronger injection / clarification / multi-step wording |

Model: Qwen2.5-3B via Ollama · `openai_tools` adapter · 11 cases.

## Results

| Version | Pass rate | Pass^k | Gate |
|---|---:|---:|---|
| v1 [`qwen_baseline.json`](../baselines/qwen_baseline.json) | **90.9%** (10/11) | 90.9% | — |
| v2 [`qwen_v2_regression.json`](../baselines/qwen_v2_regression.json) | **63.6%** (7/11) | 63.6% | fail |

- Pass rate Δ: **−27.3 pp**
- Judge mean: 4.64 → 3.73
- New failures: `kb_refund`, `unit_convert`, `kb_then_math`, `prompt_injection`
- Fixed: `ambiguous_file`

## Reproduce

```bash
agentprobe compare \
  baselines/qwen_baseline.json \
  baselines/qwen_v2_regression.json
# exit code 1: new failures + significant drop
```

To re-run models locally (optional):

```bash
agentprobe run -c configs/ollama.yaml
agentprobe run -c configs/ollama_v2.yaml
agentprobe compare runs/<v1>.json runs/<v2>.json
```
