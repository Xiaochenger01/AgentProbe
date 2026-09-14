# Regression Experiment: Prompt 改坏了，门禁拦得住吗？

用仓库内 **真实 Qwen2.5-3B** 两次运行回答这个问题（不是 mock）。

## 设置

| 版本 | 配置 | 改动 |
|---|---|---|
| **v1** | [`configs/ollama.yaml`](../configs/ollama.yaml) | 原始 system prompt |
| **v2** | [`configs/ollama_v2.yaml`](../configs/ollama_v2.yaml) | 强化注入防御 / 澄清措辞 / 多步推理说明 |

意图是「改 prompt 修好缺陷」。实际结果：**修了 1 个，却新挂了 4 个** —— 正是回归门禁要抓的情况。

## 结果（仓库基线）

| Version | Pass rate | Pass^k | Gate |
|---|---:|---:|---|
| v1 [`qwen_baseline.json`](../baselines/qwen_baseline.json) | **90.9%** (10/11) | 90.9% | — |
| v2 [`qwen_v2_regression.json`](../baselines/qwen_v2_regression.json) | **63.6%** (7/11) | 63.6% | ❌ 拦截 |

- Pass rate 下降 **−27.3 pp**
- 判官均分 4.64 → 3.73

### 用例级变化

| 变化 | Case IDs |
|---|---|
| 新失败（门禁证据） | `kb_refund`, `unit_convert`, `kb_then_math`, `prompt_injection` |
| 被修复 | `ambiguous_file` |

## 复现命令

```bash
# 需本地 Ollama + qwen2.5:3b；也可直接对仓库基线 compare
agentprobe compare \
  baselines/qwen_baseline.json \
  baselines/qwen_v2_regression.json
# 预期: 退出码 1（新失败用例 + 显著下降）
```

## 结论

AgentProbe 不只是「打分工具」：在真实 Agent 上改 prompt 后，`compare` 能用 **新失败用例 + 显著性下降** 拦住退化，适合挂进 CI。
