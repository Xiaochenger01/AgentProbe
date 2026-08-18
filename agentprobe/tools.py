from __future__ import annotations

import ast
import operator as op
from typing import Callable

TOOLS: dict[str, dict] = {}


def register_tool(name: str, description: str, parameters: dict) -> Callable:
    """把一个 Python 函数注册为 Agent 可调用的工具(自动生成 OpenAI function schema)。"""

    def deco(fn: Callable) -> Callable:
        TOOLS[name] = {
            "fn": fn,
            "schema": {
                "type": "function",
                "function": {"name": name, "description": description, "parameters": parameters},
            },
        }
        return fn

    return deco


def openai_tool_schemas(names: list[str]) -> list[dict]:
    return [TOOLS[n]["schema"] for n in names if n in TOOLS]


def call_tool(name: str, **kwargs):
    if name not in TOOLS:
        raise KeyError(f"未注册的工具: {name}")
    return TOOLS[name]["fn"](**kwargs)


# ---------------- 内置演示工具 ----------------

_ALLOWED = {
    ast.Add: op.add,
    ast.Sub: op.sub,
    ast.Mult: op.mul,
    ast.Div: op.truediv,
    ast.Pow: op.pow,
    ast.USub: op.neg,
    ast.UAdd: op.pos,
}


def _safe_eval(node):
    if isinstance(node, ast.Expression):
        return _safe_eval(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED:
        return _ALLOWED[type(node.op)](_safe_eval(node.left), _safe_eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED:
        return _ALLOWED[type(node.op)](_safe_eval(node.operand))
    raise ValueError("表达式包含不允许的语法")


@register_tool(
    "calculator",
    "计算一个四则运算表达式,例如 (17+25)*3",
    {"type": "object", "properties": {"expression": {"type": "string"}}, "required": ["expression"]},
)
def calculator(expression: str) -> str:
    value = _safe_eval(ast.parse(expression, mode="eval"))
    if isinstance(value, float):
        value = round(value, 4)
        if value == int(value):
            value = int(value)
    return str(value)


_WEATHER = {
    "北京": {"cond": "晴", "temp": 31},
    "上海": {"cond": "多云", "temp": 33},
    "深圳": {"cond": "雷阵雨", "temp": 29},
}


@register_tool(
    "weather",
    "查询指定城市今天的天气",
    {"type": "object", "properties": {"city": {"type": "string"}}, "required": ["city"]},
)
def weather(city: str) -> str:
    info = _WEATHER.get(city)
    if not info:
        return f"{city}: 暂无数据"
    return f"{city}今天{info['cond']},气温 {info['temp']}°C"


_KB_DOCS = [
    "退款政策:自签收之日起 7 天内支持无理由退款,15 天内支持换货。",
    "发票政策:支持开具电子普通发票与增值税专用发票,下单后 30 天内可申请。",
    "会员政策:年度消费满 2000 元自动升级为金卡会员,享 95 折。",
]


@register_tool(
    "kb_search",
    "在企业知识库中检索相关政策条款",
    {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
)
def kb_search(query: str) -> str:
    def score(doc: str) -> int:
        return sum(1 for ch in set(query) if ch in doc)

    return max(_KB_DOCS, key=score)
