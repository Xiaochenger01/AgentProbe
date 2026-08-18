"""测试 LLM 工具函数:extract_json 容错解析 / LLMError。"""
import json

import pytest

from agentprobe.llm import LLMError, extract_json


class TestExtractJson:
    def test_plain_json_object(self):
        result = extract_json('{"score": 5, "reason": "完全正确"}')
        assert result == {"score": 5, "reason": "完全正确"}

    def test_plain_json_array(self):
        result = extract_json('[{"task": "hello"}]')
        assert result == [{"task": "hello"}]

    def test_with_markdown_fence(self):
        result = extract_json('```json\n{"score": 3}\n```')
        assert result == {"score": 3}

    def test_with_markdown_fence_no_lang(self):
        result = extract_json('```\n{"score": 4}\n```')
        assert result == {"score": 4}

    def test_with_noise_before(self):
        result = extract_json('解释: 这个答案正确。\n{"score": 5, "reason": "很好"}')
        assert result == {"score": 5, "reason": "很好"}

    def test_with_noise_after(self):
        result = extract_json('{"score": 2} 这是补充说明')
        assert result == {"score": 2}

    def test_truncated_json_recovery(self):
        """末尾截断时回退找最后一个 }。"""
        result = extract_json('{"score": 4, "reason": "基本正确"} 多余的字符')
        assert result == {"score": 4, "reason": "基本正确"}

    def test_nested_json(self):
        result = extract_json('{"result": {"score": 5, "detail": "ok"}}')
        assert result == {"result": {"score": 5, "detail": "ok"}}

    def test_invalid_json_raises(self):
        with pytest.raises(LLMError, match="无法从模型输出解析 JSON"):
            extract_json("这不是 JSON")

    def test_empty_string_raises(self):
        with pytest.raises(LLMError, match="无法从模型输出解析 JSON"):
            extract_json("")

    def test_none_coerced_to_empty(self):
        with pytest.raises(LLMError):
            extract_json(None)

    def test_with_code_block_and_lang(self):
        result = extract_json("```json\n{\"key\": \"value\"}\n```")
        assert result == {"key": "value"}

    def test_array_in_markdown(self):
        result = extract_json("```json\n[{\"a\": 1}, {\"b\": 2}]\n```")
        assert result == [{"a": 1}, {"b": 2}]

    def test_whitespace_handling(self):
        result = extract_json('  \n  {"score": 5}  \n  ')
        assert result == {"score": 5}
