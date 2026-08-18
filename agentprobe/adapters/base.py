from __future__ import annotations

from abc import ABC, abstractmethod

from ..schemas import TestCase
from ..tracing import Tracer

ADAPTERS: dict[str, type] = {}


def register_adapter(name: str):
    def deco(cls):
        ADAPTERS[name] = cls
        return cls

    return deco


class AgentAdapter(ABC):
    """被测 Agent 的统一接入协议:任何 Agent 只要实现 run() 即可被 AgentProbe 体检。"""

    def __init__(self, cfg: dict):
        self.cfg = cfg or {}
        self.name = self.cfg.get("name", self.cfg.get("adapter", "agent"))
        self.model = self.cfg.get("model", "")

    @abstractmethod
    def run(self, case: TestCase, tracer: Tracer) -> str:
        """执行一个用例并返回最终答案;过程中的 LLM/工具调用需通过 tracer 记录。"""


def build_adapter(cfg: dict) -> AgentAdapter:
    kind = (cfg or {}).get("adapter", "mock")
    if kind not in ADAPTERS:
        raise KeyError(f"未知 adapter: {kind},可选: {sorted(ADAPTERS)}")
    return ADAPTERS[kind](cfg)
