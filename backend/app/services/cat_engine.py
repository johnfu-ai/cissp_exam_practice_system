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


def select_first_item(candidates: list[dict], rng) -> str | None:
    """FR-CAT-04: start from a medium-difficulty item; fall back to closest-to-3."""
    if not candidates:
        return None
    medium = [c for c in candidates if default_difficulty(c.get("difficulty")) == 3]
    if medium:
        return rng.choice(medium)["id"]
    # fall back to the candidate whose difficulty is closest to 3
    best_diff = min(abs(default_difficulty(c.get("difficulty")) - 3) for c in candidates)
    tied = [c for c in candidates if abs(default_difficulty(c.get("difficulty")) - 3) == best_diff]
    return rng.choice(tied)["id"]


def select_next_item(
    candidates: list[dict],
    ability: float,
    domain_targets: dict,
    domain_answered: dict,
    seen: list,
    last_kp,
    last_source,
    rng,
) -> str | None:
    """FR-CAT-05 + §11.1.5: pick by domain coverage deficit, then closest
    difficulty to current ability, with anti-clustering by knowledge point
    and source among ties."""
    seen_set = set(seen)
    eligible = [c for c in candidates if c["id"] not in seen_set]
    if not eligible:
        return None

    by_domain: dict[str | None, list[dict]] = {}
    for c in eligible:
        by_domain.setdefault(c.get("domain_id"), []).append(c)

    def deficit(did) -> int:
        target = domain_targets.get(did, 0) if domain_targets else 0
        return target - domain_answered.get(did, 0)

    # Among domains that still have eligible candidates, pick the largest deficit.
    best_domain = max(by_domain.keys(), key=lambda did: (deficit(did), did or ""))
    pool = by_domain[best_domain]

    def diff(c) -> float:
        return abs(default_difficulty(c.get("difficulty")) - ability)

    best_diff = min(diff(c) for c in pool)
    tied = [c for c in pool if diff(c) == best_diff]

    fresh = [
        c for c in tied
        if c.get("knowledge_point_id") != last_kp and c.get("source") != last_source
    ]
    chosen_pool = fresh if fresh else tied
    return rng.choice(chosen_pool)["id"]
