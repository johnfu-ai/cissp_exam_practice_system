"""CAT engine: rule-driven, simplified ability estimation (PRD §11.1).

Pure functions only — no SQLAlchemy, no DB. The service layer
(`app/services/exam.py`) owns DB access and delegates math here so the
engine is trivially unit-testable with synthetic inputs.

This is NOT 3PL IRT (Phase 5, out of P0 scope). Ability is a transparent
1–5 scale updated by shrunk additive steps; SEM shrinks as 1/sqrt(n).
"""

from __future__ import annotations

import math
from dataclasses import dataclass


DEFAULT_PARAMS = {
    "k0": 0.5,            # base ability step
    "decay": 0.1,         # step shrinkage rate with items answered
    "base_se": 1.0,       # SEM numerator
    "early_stop_enabled": True,
}

DISCLAIMER = (
    "本 CAT 模拟为学习评估工具，其通过/未通过结果不代表 ISC2 官方评分算法的预测。"
)

MIN_ITEMS_DEFAULT = 100
MAX_ITEMS_DEFAULT = 150
ABILITY_MIN = 1.0
ABILITY_MAX = 5.0
SEM_FLOOR = 0.05


@dataclass(frozen=True)
class TerminationDecision:
    must_stop: bool
    reason: str  # "time_up" | "max_items" | "converged" | "continue"


def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def initial_ability() -> float:
    """PRD §11.1.2: learner initial ability is the midpoint of 1–5."""
    return 3.0


def default_difficulty(d) -> int:
    """Map a Question.difficulty (int|None, range 1–5) to a valid 1–5 int; missing/invalid -> 3."""
    if isinstance(d, int) and 1 <= d <= 5:
        return d
    return 3


def update_ability(ability: float, difficulty, correct: bool, answered: int, params: dict) -> float:
    """PRD §11.1.3: ability rises on correct, falls on wrong; step shrinks with items answered."""
    k_n = params["k0"] / (1.0 + params["decay"] * max(0, answered))
    step = k_n
    new = ability + (step if correct else -step)
    return clamp(new, ABILITY_MIN, ABILITY_MAX)


def sem(answered: int, params: dict) -> float:
    """Standard error of measurement: shrinks as 1/sqrt(n), floored."""
    n = max(1, answered)
    return max(SEM_FLOOR, params["base_se"] / math.sqrt(n))


def passing_ability(passing_score: int, max_score: int) -> float:
    """Map the 0–max_score passing line onto the 1–5 ability space.

    700/1000 -> 3.8.
    """
    if max_score <= 0:
        return ABILITY_MIN
    ratio = min(1.0, max(0.0, passing_score / max_score))
    return ABILITY_MIN + ratio * (ABILITY_MAX - ABILITY_MIN)


def confidence_interval(ability: float, sem_value: float) -> tuple[float, float]:
    lo = clamp(ability - sem_value, ABILITY_MIN, ABILITY_MAX)
    hi = clamp(ability + sem_value, ABILITY_MIN, ABILITY_MAX)
    return lo, hi


def scaled_score(ability: float, max_score: int) -> int:
    """Ability-based scaled score (adaptive exams are scored on ability, not raw correct)."""
    ratio = (clamp(ability, ABILITY_MIN, ABILITY_MAX) - ABILITY_MIN) / (ABILITY_MAX - ABILITY_MIN)
    return round(ratio * max_score)


def readiness_level(ability: float) -> str:
    """PRD §11.3: prefer readiness framing over pass/fail."""
    if ability >= 4.0:
        return "ready"
    if ability >= 3.5:
        return "almost_ready"
    if ability >= 3.0:
        return "developing"
    return "needs_work"


def decide_termination(
    answered: int,
    ability: float,
    sem_value: float,
    min_items: int,
    max_items: int,
    time_up: bool,
    pass_ability: float,
    params: dict,
) -> TerminationDecision:
    """PRD §11.1.6/7: end at 150 items or 3h; may end >=100 if ability has converged."""
    if time_up:
        return TerminationDecision(True, "time_up")
    if answered >= max_items:
        return TerminationDecision(True, "max_items")
    if params.get("early_stop_enabled", True) and answered >= min_items:
        lo, hi = confidence_interval(ability, sem_value)
        if hi < pass_ability or lo > pass_ability:
            return TerminationDecision(True, "converged")
    return TerminationDecision(False, "continue")
