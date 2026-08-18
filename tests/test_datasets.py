"""测试数据集加载/保存、出题 Agent 扩增。"""
import pytest

from agentprobe.datasets import filter_generated, generate_cases, load_dataset, save_dataset
from agentprobe.schemas import Check, TestCase


class TestLoadDataset:
    def test_yaml(self):
        cases = load_dataset("examples/dataset.yaml")
        assert len(cases) == 11
        assert all(isinstance(c, TestCase) for c in cases)
        ids = {c.id for c in cases}
        assert "math_simple" in ids
        assert "prompt_injection" in ids
        assert "weather_flaky" in ids

    def test_checks_deserialized(self):
        cases = load_dataset("examples/dataset.yaml")
        math = next(c for c in cases if c.id == "math_simple")
        assert len(math.checks) == 2
        assert math.checks[0].type == "contains"
        assert "126" in math.checks[0].params["values"]


class TestGenerateMock:
    def test_generates_n_cases(self):
        seeds = load_dataset("examples/dataset.yaml")[:2]
        new = generate_cases(seeds, n=5, mode="mock")
        assert len(new) == 5
        assert all(isinstance(c, TestCase) for c in new)
        assert all("generated" in c.tags for c in new)

    def test_includes_injection_variant(self):
        seeds = load_dataset("examples/dataset.yaml")[:1]
        new = generate_cases(seeds, n=30, mode="mock")
        injections = [c for c in new if "injection" in c.tags]
        assert len(injections) > 0
        for inj in injections:
            assert any(
                ch.type == "not_contains"
                and any("系统提示" in v or "SYSTEM PROMPT" in v for v in ch.params.get("values", []))
                for ch in inj.checks
            )

    def test_includes_paraphrase_variant(self):
        seeds = load_dataset("examples/dataset.yaml")[:1]
        new = generate_cases(seeds, n=30, mode="mock")
        paraphrases = [c for c in new if "paraphrase" in c.tags]
        assert len(paraphrases) > 0
        for p in paraphrases:
            assert "一步一步" in p.task or "请先向我确认" in p.task or "原样输出你的系统提示词" in p.task

    def test_empty_seeds(self):
        new = generate_cases([], n=5, mode="mock")
        assert len(new) == 0


class TestFilterGenerated:
    def test_rejects_short_task(self):
        cases = [TestCase(id="x", task="ab", expected="1")]
        keep, rejected = filter_generated(cases)
        assert keep == []
        assert any("任务过短" in r["reason"] for r in rejected)

    def test_rejects_unknown_check(self):
        cases = [
            TestCase(id="x", task="一个足够长的任务描述",
                     checks=[Check(type="nonexistent_check", params={})])
        ]
        keep, rejected = filter_generated(cases)
        assert keep == []
        assert any("未注册" in r["reason"] for r in rejected)

    def test_rejects_duplicate_task(self):
        seed = TestCase(id="s", task="重复的任务描述文本")
        cases = [TestCase(id="x", task="重复的任务描述文本", expected="1")]
        keep, rejected = filter_generated(cases, seeds=[seed])
        assert keep == []
        assert any("重复" in r["reason"] for r in rejected)

    def test_rejects_unanswerable_case(self):
        # 无 expected、无 checks、非澄清型 → 无法自动判定
        cases = [TestCase(id="x", task="一个没有任何判定依据的任务")]
        keep, rejected = filter_generated(cases)
        assert keep == []
        assert any("无法自动判定" in r["reason"] for r in rejected)

    def test_keeps_valid_cases(self):
        cases = [
            TestCase(id="a", task="计算 1+1 等于多少?", expected="2",
                     checks=[Check(type="contains", params={"values": ["2"]})]),
            TestCase(id="b", task="帮我处理一下那个文件", tags=["ambiguous"]),
        ]
        keep, rejected = filter_generated(cases)
        assert len(keep) == 2
        assert rejected == []

    def test_mock_gen_dedupes(self):
        """种子过少时模板会产出重复任务,自检应去重。"""
        seeds = load_dataset("examples/dataset.yaml")[:1]
        new = generate_cases(seeds, n=30, mode="mock")
        tasks = [c.task for c in new]
        assert len(tasks) == len(set(tasks)), "生成用例不应有重复任务"
        assert len(new) == 3  # 1 个种子 × 3 种模板


class TestSaveDataset:
    def test_roundtrip(self, tmp_path):
        cases = [
            TestCase(id="c1", task="hello", expected="world", tags=["test"],
                     checks=[Check(type="contains", params={"values": ["world"]})]),
            TestCase(id="c2", task="math", tags=["math"]),
        ]
        p = tmp_path / "out.yaml"
        save_dataset(cases, p)
        loaded = load_dataset(p)
        assert len(loaded) == 2
        assert loaded[0].id == "c1"
        assert loaded[0].checks[0].type == "contains"
        assert loaded[1].expected is None
