#!/usr/bin/env python3
"""
AgentProbe 全流程演示: 评测 → 归因 → DPO导出 → 回归对比

用途:
  1. mock 模式(零 Key): python examples/full_pipeline.py --mock
  2. 真实模型: 设置 OPENAI_BASE_URL + OPENAI_API_KEY 后,
     python examples/full_pipeline.py -c configs/real_model.yaml

这个脚本是 BLOG.md 中描述的完整实践的代码实现。
"""

import argparse
import subprocess
import sys
from pathlib import Path


def run_cmd(cmd: str, desc: str = "") -> int:
    if desc:
        print(f"\n{'='*60}")
        print(f"  {desc}")
        print(f"{'='*60}")
    print(f"$ {cmd}")
    return subprocess.call(cmd, shell=True)


def main():
    parser = argparse.ArgumentParser(description="AgentProbe 全流程演示")
    parser.add_argument("-c", "--config", default="configs/example.yaml", help="评测配置文件")
    parser.add_argument("--mock", action="store_true", help="强制 mock 模式(零 API Key)")
    parser.add_argument("--repeat", type=int, default=3, help="每个用例重复次数(用于 pass^k)")
    parser.add_argument("--skip-compare", action="store_true", help="跳过回归对比(首次运行)")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    runs_dir = repo_root / "runs"
    baseline_dir = repo_root / "baselines"

    # Step 1: 体检
    mock_flag = " --mock" if args.mock else ""
    cmd = f"agentprobe run -c {args.config}{mock_flag} --repeat {args.repeat} --out-dir {runs_dir}"
    rc = run_cmd(cmd, "Step 1/5: 体检(Agent 评测)")
    if rc != 0:
        print("体检失败,终止")
        sys.exit(rc)

    # 找到最新的报告
    reports = sorted(runs_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not reports:
        print("错误: 未生成报告文件")
        sys.exit(1)
    latest = reports[0]
    print(f"\n报告: {latest}")

    # Step 2: 失败归因
    cmd = f"agentprobe rca {latest}"
    run_cmd(cmd, "Step 2/5: 失败归因(RCA 聚簇 + 改进建议)")

    # Step 3: DPO 偏好对导出
    dpo_path = runs_dir / f"{latest.stem}_dpo.jsonl"
    cmd = f"agentprobe export-dpo {latest} --out {dpo_path}"
    run_cmd(cmd, "Step 3/5: 导出 DPO 偏好对(评测→训练闭环)")

    if dpo_path.exists():
        with open(dpo_path, encoding="utf-8") as f:
            n = sum(1 for _ in f)
        print(f"  [OK] 已导出 {n} 条 DPO 偏好对")
        if n > 0:
            print(f"  -> 对接 TRL: load_dataset('json', data_files='{dpo_path}', split='train')")

    # Step 4: 回归对比(与基线)
    baseline = baseline_dir / "mock_baseline.json"
    if not args.skip_compare and baseline.exists():
        cmd = f"agentprobe compare {baseline} {latest}"
        rc = run_cmd(cmd, "Step 4/5: 回归对比(CI 门禁)")
        if rc != 0:
            print("[WARN] 门禁拦截: 指标下降或出现新失败用例")
    elif not baseline.exists():
        print(f"\n[WARN] 基线文件不存在: {baseline}")
        print(f"  提示: 首次运行,建议将当前报告设为基线:")
        print(f"  cp {latest} {baseline}")

    # Step 5: 生成用例(出题 Agent)
    cmd = f"agentprobe gen examples/dataset.yaml --n 6 --out {runs_dir}/generated_cases.yaml"
    run_cmd(cmd, "Step 5/5: 出题 Agent 扩增用例(边界/注入/多跳)")

    print(f"\n{'='*60}")
    print(f"  全流程完成!")
    print(f"{'='*60}")
    print(f"""
+----------------------------------------------------------+
|  评测报告:  {latest}
|  Markdown:  {latest.with_suffix('.md')}
|  RCA 报告:  {latest.with_suffix('.rca.md')}
|  DPO 数据:  {dpo_path}
|  扩增用例:  {runs_dir / 'generated_cases.yaml'}
+----------------------------------------------------------+

下一步:
  1. 查看 Markdown 报告了解详细的体检结果
  2. 根据 RCA 建议修复 Agent 的 prompt/tools
  3. 用 DPO 数据微调模型: TRL DPOTrainer
  4. 微调后再次 run -> compare,验证提升
  5. 把 agentprobe compare 挂到 GitHub Actions 做 CI 门禁
""")


if __name__ == "__main__":
    main()
