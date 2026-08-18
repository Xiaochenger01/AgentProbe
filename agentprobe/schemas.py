from __future__ import annotations

import time
import uuid
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


def new_id() -> str:
    return uuid.uuid4().hex[:12]


class SpanKind(str, Enum):
    AGENT = "agent"
    LLM = "llm"
    TOOL = "tool"
    RETRIEVER = "retriever"
    JUDGE = "judge"


class Span(BaseModel):
    """一次原子操作(LLM 调用 / 工具调用)的记录,字段命名尽量贴近 OTel GenAI 语义约定。"""

    id: str = Field(default_factory=new_id)
    parent_id: Optional[str] = None
    kind: SpanKind
    name: str
    input: Any = None
    output: Any = None
    error: Optional[str] = None
    start: float = Field(default_factory=time.time)
    end: Optional[float] = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost: float = 0.0
    meta: dict = Field(default_factory=dict)

    def latency_ms(self) -> float:
        return 0.0 if self.end is None else (self.end - self.start) * 1000.0


class Trace(BaseModel):
    """一次完整 Agent 执行的链路(span 树),数据模型对齐 Langfuse 的 trace->typed observations 思路。"""

    id: str = Field(default_factory=new_id)
    case_id: str = ""
    agent: str = ""
    model: str = ""
    spans: list[Span] = Field(default_factory=list)
    final_output: str = ""
    started: float = Field(default_factory=time.time)
    ended: Optional[float] = None

    def spans_of(self, kind: SpanKind) -> list[Span]:
        return [s for s in self.spans if s.kind == kind]

    def tool_calls(self) -> list[Span]:
        return self.spans_of(SpanKind.TOOL)

    def llm_calls(self) -> list[Span]:
        return self.spans_of(SpanKind.LLM)

    def total_tokens(self) -> int:
        return sum(s.prompt_tokens + s.completion_tokens for s in self.spans)

    def total_cost(self) -> float:
        return sum(s.cost for s in self.spans)

    def duration_ms(self) -> float:
        return 0.0 if self.ended is None else (self.ended - self.started) * 1000.0

    def has_error(self) -> bool:
        return any(s.error for s in self.spans)

    def digest(self, max_chars: int = 1600) -> str:
        """轨迹摘要,供 LLM 判官 / 归因 Agent 阅读。"""
        lines = []
        for s in self.spans:
            inp = "" if s.input is None else str(s.input)[:100]
            out = "" if s.output is None else str(s.output)[:100]
            mark = f" !ERROR:{s.error}" if s.error else ""
            lines.append(f"[{s.kind.value}] {s.name} in={inp} out={out}{mark}")
        return "\n".join(lines)[:max_chars]


class Check(BaseModel):
    """数据集中声明式的规则检查,如 {type: contains, params: {values: ['126']}}。"""

    type: str
    params: dict = Field(default_factory=dict)


class TestCase(BaseModel):
    __test__ = False  # 防止 pytest 误收集

    id: str = Field(default_factory=new_id)
    task: str
    expected: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    checks: list[Check] = Field(default_factory=list)
    meta: dict = Field(default_factory=dict)


class Score(BaseModel):
    evaluator: str
    metric: str
    value: float = 0.0
    passed: Optional[bool] = None  # None = 仅观测指标,不参与通过判定
    reason: str = ""


class CaseResult(BaseModel):
    case: TestCase
    repeat_index: int = 0
    output: str = ""
    trace: Trace
    scores: list[Score] = Field(default_factory=list)
    passed: bool = False

    def first_failure(self) -> Optional[Score]:
        for s in self.scores:
            if s.passed is False:
                return s
        return None


class RunReport(BaseModel):
    run_id: str = Field(default_factory=new_id)
    created: float = Field(default_factory=time.time)
    agent: str = ""
    model: str = ""
    dataset: str = ""
    repeat: int = 1
    config: dict = Field(default_factory=dict)
    results: list[CaseResult] = Field(default_factory=list)
