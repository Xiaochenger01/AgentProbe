# Real Agent Example

用 **真实本地模型**（Qwen2.5-3B via Ollama）跑 AgentProbe，而不是 mock。

数据已落在仓库 `baselines/`，可直接核对；本地有 Ollama 时可复跑。

## 流水线

```text
Qwen2.5-3B (Ollama)
       ↓
openai_tools adapter (ReAct + tools)
       ↓
AgentProbe Runner (×k)
       ↓
Trace (LLM / Tool spans)
       ↓
Rules + Trajectory + Judge
       ↓
Report → compare / rca / export-dpo
```

## 配置

| 文件 | 说明 |
|---|---|
| [`configs/ollama.yaml`](../../configs/ollama.yaml) | Qwen Agent v1，`repeat=1` |
| [`configs/ollama_k3.yaml`](../../configs/ollama_k3.yaml) | 同上，`repeat=3`（测稳定性） |
| [`configs/ollama_v2.yaml`](../../configs/ollama_v2.yaml) | 改过 system prompt 的 v2（用于回归实验） |

## 已保存的运行结果

| 基线文件 | Agent | repeat | Pass rate | Pass^k |
|---|---|---:|---:|---:|
| [`baselines/qwen_baseline.json`](../../baselines/qwen_baseline.json) | qwen-agent | 1 | **90.9%** | 90.9% (10/11) |
| [`baselines/qwen_k3_baseline.json`](../../baselines/qwen_k3_baseline.json) | qwen-agent | 3 | **75.8%** | 72.7% (8/11) |
| [`baselines/qwen_v2_regression.json`](../../baselines/qwen_v2_regression.json) | qwen-agent-v2 | 1 | **63.6%** | 63.6% (7/11) |

要点：单次 90.9% 在 `repeat=3` 后降到 75.8% —— 单次结果会高估可靠性。

## 本地复跑（需 Ollama）

```bash
# 1. 启动模型
ollama pull qwen2.5:3b
ollama serve

# 2. 评测
agentprobe run -c configs/ollama.yaml

# 3. 稳定性（可选）
agentprobe run -c configs/ollama_k3.yaml

# 4. 与仓库基线对比（可选）
agentprobe compare baselines/qwen_baseline.json runs/<new_run>.json
```

无需 GPU 云服务；`base_url` 指向 `http://localhost:11434/v1` 即可。

## 相关：Prompt 回归实验

见 [`docs/regression-experiment.md`](../../docs/regression-experiment.md)：v1 → v2 改 prompt 后被门禁拦截。
