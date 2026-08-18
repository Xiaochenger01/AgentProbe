from .base import EVALUATORS, Evaluator, build_evaluators, register_evaluator
from . import judge, rules, trajectory  # noqa: F401  触发注册

__all__ = ["EVALUATORS", "Evaluator", "build_evaluators", "register_evaluator"]
