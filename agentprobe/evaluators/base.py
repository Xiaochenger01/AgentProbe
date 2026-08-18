from __future__ import annotations

from abc import ABC, abstractmethod

from ..schemas import Score, TestCase, Trace

EVALUATORS: dict[str, type] = {}


def register_evaluator(name: str):
    def deco(cls):
        EVALUATORS[name] = cls
        cls.name = name
        return cls

    return deco


class Evaluator(ABC):
    name: str = "evaluator"

    def __init__(self, cfg: dict):
        self.cfg = cfg or {}

    @abstractmethod
    def evaluate(self, case: TestCase, output: str, trace: Trace) -> list[Score]:
        ...


def build_evaluators(cfgs: list[dict]) -> list[Evaluator]:
    evs: list[Evaluator] = []
    for c in cfgs or []:
        t = c.get("type")
        if t not in EVALUATORS:
            raise KeyError(f"未知 evaluator: {t},可选: {sorted(EVALUATORS)}")
        evs.append(EVALUATORS[t](c))
    return evs
