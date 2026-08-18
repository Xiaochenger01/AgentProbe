"""测试工具注册、调用、OpenAI schema 生成。"""
import pytest

from agentprobe.tools import TOOLS, calculator, call_tool, kb_search, openai_tool_schemas, weather


class TestCalculator:
    def test_basic_arithmetic(self):
        assert calculator("2+3") == "5"
        assert calculator("10-4") == "6"

    def test_multiplication(self):
        assert calculator("6*7") == "42"

    def test_division_float(self):
        assert calculator("10/3") == "3.3333"

    def test_parentheses(self):
        assert calculator("(17+25)*3") == "126"

    def test_unary_negative(self):
        assert calculator("-5+10") == "5"

    def test_float_to_int(self):
        assert calculator("4/2") == "2"

    def test_fahrenheit_conversion(self):
        v = float(calculator("(98-32)*5/9"))
        assert abs(v - 36.6667) < 0.001

    def test_rejects_unsafe(self):
        with pytest.raises(ValueError):
            calculator("__import__('os').system('ls')")


class TestWeather:
    def test_known_cities(self):
        assert "北京" in weather("北京")
        assert "31°C" in weather("北京")
        assert "上海" in weather("上海")
        assert "雷阵雨" in weather("深圳")

    def test_unknown_city(self):
        assert "暂无数据" in weather("火星")


class TestKbSearch:
    def test_refund_policy(self):
        result = kb_search("退款政策")
        assert "退款" in result
        assert "7" in result

    def test_invoice_policy(self):
        result = kb_search("发票怎么开")
        assert "发票" in result

    def test_member_policy(self):
        result = kb_search("会员等级")
        assert "会员" in result or "2000" in result or "95" in result


class TestToolRegistry:
    def test_all_tools_registered(self):
        assert "calculator" in TOOLS
        assert "weather" in TOOLS
        assert "kb_search" in TOOLS

    def test_schema_structure(self):
        schema = TOOLS["calculator"]["schema"]
        assert schema["type"] == "function"
        assert schema["function"]["name"] == "calculator"
        assert "expression" in schema["function"]["parameters"]["properties"]

    def test_openai_tool_schemas_filters(self):
        schemas = openai_tool_schemas(["calculator", "weather"])
        assert len(schemas) == 2
        names = [s["function"]["name"] for s in schemas]
        assert names == ["calculator", "weather"]

    def test_openai_tool_schemas_skips_unknown(self):
        schemas = openai_tool_schemas(["calculator", "nonexistent"])
        assert len(schemas) == 1


class TestCallTool:
    def test_call_registered(self):
        assert "5" == call_tool("calculator", expression="2+3")

    def test_call_unknown_raises(self):
        with pytest.raises(KeyError, match="未注册"):
            call_tool("magic_wand")
