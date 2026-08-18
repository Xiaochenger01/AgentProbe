from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Any, Iterator, Optional

from .schemas import Span, SpanKind, Trace


class Tracer:
    """极简链路追踪器:用 span 树记录 Agent 的每一次 LLM / 工具调用。"""

    def __init__(self, trace: Optional[Trace] = None):
        self.trace = trace or Trace()
        self._stack: list[str] = []

    @contextmanager
    def span(self, kind: SpanKind | str, name: str, input: Any = None) -> Iterator[Span]:
        sp = Span(
            kind=SpanKind(kind),
            name=name,
            input=input,
            parent_id=self._stack[-1] if self._stack else None,
        )
        self.trace.spans.append(sp)
        self._stack.append(sp.id)
        try:
            yield sp
        except Exception as e:  # noqa: BLE001
            sp.error = f"{e.__class__.__name__}: {e}"
            raise
        finally:
            sp.end = time.time()
            self._stack.pop()

    def finish(self, final_output: str) -> Trace:
        self.trace.final_output = final_output
        self.trace.ended = time.time()
        return self.trace
