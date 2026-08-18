"""AgentProbe 评测→训练闭环:把 export-dpo 产出的偏好对微调成新 Agent。

用法(需要 trl + peft + datasets,消费级显卡即可):
    pip install trl peft datasets
    python scripts/dpo_train.py \
        --data runs/<run_id>_dpo.jsonl \
        --model Qwen/Qwen2.5-0.5B-Instruct \
        --out ./agent-dpo-v1 --epochs 2

本地模型(如已下载的 Ollama 目录)可以用 --model /path/to/model 直接指向本地路径。
微调完成后,把新模型端点填回 configs/*.yaml,再 `agentprobe run` + `agentprobe compare`
验证提升——完成"评测 → 归因 → 造数 → 训练 → 再评测"飞轮。
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def load_pairs(data_path: Path, min_pairs: int = 4) -> list[dict]:
    """读取 export-dpo 产出的 JSONL,裁剪为 TRL DPOTrainer 约定的三列。"""
    pairs: list[dict] = []
    for line in data_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        if not all(k in item for k in ("prompt", "chosen", "rejected")):
            raise ValueError(f"偏好对缺少 prompt/chosen/rejected 字段: {item}")
        pairs.append(
            {"prompt": item["prompt"], "chosen": item["chosen"], "rejected": item["rejected"]}
        )
    if len(pairs) < min_pairs:
        raise SystemExit(
            f"偏好对只有 {len(pairs)} 条(< {min_pairs}),DPO 需要至少数十条才有效果。\n"
            "建议:多跑几轮体检累积失败样本,或用 gen 扩增对抗用例后重新 export-dpo。"
        )
    print(f"loaded {len(pairs)} DPO pairs from {data_path}")
    return pairs


def main() -> None:
    parser = argparse.ArgumentParser(description="AgentProbe DPO 微调脚本(TRL + LoRA)")
    parser.add_argument("--data", required=True, help="export-dpo 产出的 JSONL 路径")
    parser.add_argument("--model", default="Qwen/Qwen2.5-0.5B-Instruct",
                        help="基础模型(HF id 或本地路径)")
    parser.add_argument("--out", default="./agent-dpo-v1", help="输出目录")
    parser.add_argument("--epochs", type=float, default=2.0)
    parser.add_argument("--lr", type=float, default=5e-6)
    parser.add_argument("--lora-r", type=int, default=8)
    parser.add_argument("--lora-alpha", type=int, default=16)
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--grad-accum", type=int, default=4)
    parser.add_argument("--max-length", type=int, default=1024)
    args = parser.parse_args()

    try:
        from datasets import load_dataset
        from trl import DPOConfig, DPOTrainer
        import torch
    except ImportError as e:
        raise SystemExit(
            f"缺少依赖({e.name if hasattr(e, 'name') else e})。请先安装:\n"
            "  pip install trl peft datasets torch"
        )

    pairs = load_pairs(Path(args.data))
    tmp = Path(args.out) / "train.json"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_text(
        "\n".join(json.dumps(p, ensure_ascii=False) for p in pairs), encoding="utf-8"
    )
    dataset = load_dataset("json", data_files=str(tmp), split="train")

    dpo_config = DPOConfig(
        output_dir=args.out,
        per_device_train_batch_size=args.batch_size,
        gradient_accumulation_steps=args.grad_accum,
        num_train_epochs=args.epochs,
        learning_rate=args.lr,
        lr_scheduler_type="cosine",
        warmup_ratio=0.1,
        logging_steps=5,
        save_strategy="epoch",
        max_length=args.max_length,
        max_prompt_length=512,
        bf16=torch.cuda.is_available() and torch.cuda.is_bf16_supported(),
        report_to=[],
    )

    trainer = DPOTrainer(
        model=args.model,
        ref_model=None,  # 自动加载同款参考模型
        args=dpo_config,
        train_dataset=dataset,
        peft_config=None,  # TRL 新版用 peft_config=None 走全参;需要 LoRA 见下方注释
    )
    # LoRA 模式(显存不够时): pip install peft 后改为:
    #   from peft import LoraConfig
    #   trainer = DPOTrainer(..., peft_config=LoraConfig(
    #       r=args.lora_r, lora_alpha=args.lora_alpha,
    #       target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
    #       task_type="CAUSAL_LM"))
    trainer.train()
    trainer.save_model(args.out)
    print(f"DPO 训练完成,模型已保存到 {args.out}")
    print("下一步:把新模型端点填回 configs/*.yaml → agentprobe run → agentprobe compare")


if __name__ == "__main__":
    main()
