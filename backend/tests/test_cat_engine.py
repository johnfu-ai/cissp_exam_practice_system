"""Pure unit tests for the CAT engine (no DB)."""

import math

from app.services import cat_engine as ce


def test_initial_ability_is_median():
    assert ce.initial_ability() == 3.0


def test_default_difficulty():
    assert ce.default_difficulty(3) == 3
    assert ce.default_difficulty(None) == 3
    assert ce.default_difficulty(7) == 3  # out of range -> 3
    assert ce.default_difficulty(0) == 3
    assert ce.default_difficulty(5) == 5
    assert ce.default_difficulty(1) == 1


def test_update_ability_direction_and_shrinkage_and_clamp():
    p = ce.DEFAULT_PARAMS
    # correct raises, wrong lowers
    up = ce.update_ability(3.0, 3, True, 0, p)
    down = ce.update_ability(3.0, 3, False, 0, p)
    assert up > 3.0
    assert down < 3.0
    # step shrinks as more items answered
    step0 = up - 3.0
    step_later = ce.update_ability(3.0, 3, True, 20, p) - 3.0
    assert step_later < step0
    # clamps to [1, 5]
    hi = ce.update_ability(4.9, 3, True, 0, p)
    assert hi == 5.0
    lo = ce.update_ability(1.1, 3, False, 0, p)
    assert lo == 1.0


def test_sem_decreases_and_floored():
    p = ce.DEFAULT_PARAMS
    s1 = ce.sem(1, p)
    s10 = ce.sem(100, p)
    assert s10 < s1
    assert s10 >= 0.05  # floor


def test_passing_ability():
    assert ce.passing_ability(700, 1000) == 3.8
    assert ce.passing_ability(0, 1000) == 1.0
    assert ce.passing_ability(1000, 1000) == 5.0


def test_confidence_interval_clamps():
    lo, hi = ce.confidence_interval(1.2, 1.0)
    assert lo == 1.0
    assert math.isclose(hi, 2.2)
    lo2, hi2 = ce.confidence_interval(4.8, 1.0)
    assert hi2 == 5.0


def test_scaled_score():
    assert ce.scaled_score(3.0, 1000) == 500
    assert ce.scaled_score(5.0, 1000) == 1000
    assert ce.scaled_score(1.0, 1000) == 0


def test_readiness_level_bands():
    assert ce.readiness_level(4.5) == "ready"
    assert ce.readiness_level(3.6) == "almost_ready"
    assert ce.readiness_level(3.0) == "developing"
    assert ce.readiness_level(2.0) == "needs_work"


def test_termination_time_up():
    p = ce.DEFAULT_PARAMS
    d = ce.decide_termination(50, 3.0, 0.5, 100, 150, True, 3.8, p)
    assert d.must_stop is True
    assert d.reason == "time_up"


def test_termination_max_items():
    p = ce.DEFAULT_PARAMS
    d = ce.decide_termination(150, 3.0, 0.5, 100, 150, False, 3.8, p)
    assert d.must_stop is True
    assert d.reason == "max_items"


def test_termination_converged_pass():
    # ability high, CI entirely above passing line
    p = ce.DEFAULT_PARAMS
    # answered >= min_items, lo > pa
    d = ce.decide_termination(100, 4.5, 0.1, 100, 150, False, 3.8, p)
    assert d.must_stop is True
    assert d.reason == "converged"


def test_termination_converged_fail():
    p = ce.DEFAULT_PARAMS
    # ability low, CI entirely below passing line (hi < pa)
    d = ce.decide_termination(100, 2.0, 0.1, 100, 150, False, 3.8, p)
    assert d.must_stop is True
    assert d.reason == "converged"


def test_termination_continue_below_min_items():
    p = ce.DEFAULT_PARAMS
    d = ce.decide_termination(5, 5.0, 0.05, 100, 150, False, 3.8, p)
    assert d.must_stop is False
    assert d.reason == "continue"


def test_termination_continue_ci_straddles():
    p = ce.DEFAULT_PARAMS
    # ability 3.8, sem 1.0 -> CI [2.8, 4.8] straddles pa=3.8
    d = ce.decide_termination(120, 3.8, 1.0, 100, 150, False, 3.8, p)
    assert d.must_stop is False
    assert d.reason == "continue"


def test_termination_early_stop_disabled():
    p = {**ce.DEFAULT_PARAMS, "early_stop_enabled": False}
    d = ce.decide_termination(120, 5.0, 0.05, 100, 150, False, 3.8, p)
    assert d.must_stop is False  # convergence disabled, below max
    assert d.reason == "continue"


import random


def _cand(cid, difficulty=None, domain_id="d1", kp=None, source=None):
    return {"id": cid, "difficulty": difficulty, "domain_id": domain_id,
            "knowledge_point_id": kp, "source": source}


def test_select_first_item_prefers_medium():
    candidates = [_cand("hard", 5), _cand("easy", 1), _cand("mid", 3)]
    rng = random.Random(0)
    assert ce.select_first_item(candidates, rng) == "mid"


def test_select_first_item_falls_back_to_closest():
    candidates = [_cand("hard", 5), _cand("easy", 1)]
    rng = random.Random(0)
    # closest to 3 is 5 (dist 2) vs 1 (dist 2) -> tie, rng picks one of them
    choice = ce.select_first_item(candidates, rng)
    assert choice in {"hard", "easy"}


def test_select_first_item_empty_pool():
    assert ce.select_first_item([], random.Random(0)) is None


def test_select_next_item_excludes_seen():
    candidates = [_cand("a", 3), _cand("b", 3)]
    rng = random.Random(0)
    choice = ce.select_next_item(
        candidates, 3.0, {"d1": 2}, {}, ["a"], None, None, rng)
    assert choice == "b"


def test_select_next_item_closest_difficulty():
    candidates = [_cand("a", 1), _cand("b", 4), _cand("c", 5)]
    rng = random.Random(0)
    # ability 4.2 -> closest is b (4)
    choice = ce.select_next_item(
        candidates, 4.2, {"d1": 3}, {}, [], None, None, rng)
    assert choice == "b"


def test_select_next_item_domain_deficit_priority():
    # Two domains; d2 is behind on coverage -> pick from d2 even though its
    # item is farther from ability.
    candidates = [
        _cand("a1", 3, domain_id="d1"),
        _cand("b1", 5, domain_id="d2"),
    ]
    rng = random.Random(0)
    # targets: d1=1, d2=2; answered: d1=1, d2=0 -> d2 has larger deficit
    choice = ce.select_next_item(
        candidates, 3.0, {"d1": 1, "d2": 2}, {"d1": 1},
        [], None, None, rng)
    assert choice == "b1"


def test_select_next_item_empty_pool():
    rng = random.Random(0)
    assert ce.select_next_item([], 3.0, {}, {}, [], None, None, rng) is None


def test_select_next_item_anti_cluster_prefers_different_kp_and_source():
    # Two items equally close to ability; one shares kp+source with last.
    candidates = [
        _cand("same", 3, kp="k1", source="s1"),
        _cand("fresh", 3, kp="k2", source="s2"),
    ]
    rng = random.Random(0)
    choice = ce.select_next_item(
        candidates, 3.0, {"d1": 2}, {}, [], "k1", "s1", rng)
    assert choice == "fresh"


def test_select_next_item_anti_cluster_falls_back_when_all_same():
    candidates = [_cand("only", 3, kp="k1", source="s1")]
    rng = random.Random(0)
    choice = ce.select_next_item(
        candidates, 3.0, {"d1": 1}, {}, [], "k1", "s1", rng)
    assert choice == "only"


def test_select_next_item_domain_with_no_candidates_falls_to_other():
    # d1 has candidates but d2 (higher deficit) has none -> fall back to d1.
    candidates = [_cand("a1", 3, domain_id="d1")]
    rng = random.Random(0)
    choice = ce.select_next_item(
        candidates, 3.0, {"d1": 1, "d2": 5}, {"d2": 0},
        [], None, None, rng)
    assert choice == "a1"
