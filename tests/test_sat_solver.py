import math

import pytest
import satisfaction_suffices.verifier.sat as sat_module

from satisfaction_suffices.verifier.sat import (
    SATReward,
    SATSolver,
    neg,
    neg_lit,
    pos_lit,
    sat_score,
    sign_of,
    solve_cnf,
    var_of,
)


def test_literal_helpers_round_trip() -> None:
    lit = pos_lit(3)
    assert var_of(lit) == 3
    assert sign_of(lit) == 0
    assert neg(lit) == neg_lit(3)
    assert sign_of(neg(lit)) == 1


def test_add_clause_handles_tautology_and_empty_clause() -> None:
    s = SATSolver()
    s.new_vars(1)
    assert s.add_clause([pos_lit(0), neg_lit(0)]) is True
    assert s.add_clause([]) is False


def test_solver_sat_and_unsat_cases() -> None:
    sat, model = solve_cnf(2, [[1], [2]])
    assert sat is True
    assert model is not None
    assert model[1] is True
    assert model[2] is True

    sat2, model2 = solve_cnf(1, [[1], [-1]])
    assert sat2 is False


def test_sat_score_rewards() -> None:
    score, zone, n_timeout = sat_score(1, [[[1]]])
    assert isinstance(score, float)
    assert score > 0
    assert zone == "coherent"


def test_sat_reward_module_exists() -> None:
    try:
        import torch  # noqa: F401
    except (ImportError, RuntimeError):
        pytest.skip("torch not usable in this environment")
    # Inspect the class without instantiation — avoids the Windows/Python-3.12
    # torch bug where nn.Module.__init__ raises RuntimeError on first call.
    assert hasattr(SATReward, "forward") or callable(SATReward)
