from __future__ import annotations

import requests

from ..schemas import TestCase
from ..tracing import Tracer
from .base import AgentAdapter, register_adapter


@register_adapter("http")
class HTTPAgent(AgentAdapter):
    """把任意已部署的 Agent 服务接入体检:POST {url} {"task": ...} -> {"output": ...}。"""

    def run(self, case: TestCase, tracer: Tracer) -> str:
        url = self.cfg["url"]
        with tracer.span("agent", "http_call", input=case.task) as sp:
            r = requests.post(url, json={"task": case.task}, timeout=int(self.cfg.get("timeout", 120)))
            r.raise_for_status()
            data = r.json()
            out = str(data.get("output", data))
            sp.output = out[:400]
        return out
