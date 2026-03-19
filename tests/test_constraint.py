"""
Tests for satisfaction_suffices.logic.constraint — constraint algebra.

Covers: PartialResult lattice, PrefixFeasibility, SATConstraint, FunctionConstraint,
ConjunctiveConstraint, DisjunctiveConstraint, NegatedConstraint, SequentialConstraint,
ConstraintAlgebra, algebra singleton.
"""

from __future__ import annotations

import pytest

from satisfaction_suffices.logic.constraint import (
    ConstraintAlgebra,
    ConjunctiveConstraint,
    DisjunctiveConstraint,
    FunctionConstraint,
    NegatedConstraint,
    PartialResult,
    PrefixFeasibility,
    SATConstraint,
    SequentialConstraint,
    _partial_join,
    _partial_meet,
    algebra,
    SAT_COHERENT,
    SAT_PLATEAU_LO,
)
from satisfaction_suffices.verifier.verify import Verdict


# ═══════════════════════════════════════════════════════════════════
# PartialResult lattice operations
# ═══════════════════════════════════════════════════════════════════

class TestPartialResultLattice:
    def test_meet_prunable_dominates(self) -> None:
        assert _partial_meet(PartialResult.EXTENDABLE, PartialResult.PRUNABLE) == PartialResult.PRUNABLE
        assert _partial_meet(PartialResult.PRUNABLE, PartialResult.UNRESOLVED) == PartialResult.PRUNABLE

    def test_meet_unresolved_middle(self) -> None:
        assert _partial_meet(PartialResult.EXTENDABLE, PartialResult.UNRESOLVED) == PartialResult.UNRESOLVED

    def test_meet_extendable_identity(self) -> None:
        assert _partial_meet(PartialResult.EXTENDABLE, PartialResult.EXTENDABLE) == PartialResult.EXTENDABLE

    def test_join_extendable_dominates(self) -> None:
        assert _partial_join(PartialResult.EXTENDABLE, PartialResult.PRUNABLE) == PartialResult.EXTENDABLE
        assert _partial_join(PartialResult.EXTENDABLE, PartialResult.UNRESOLVED) == PartialResult.EXTENDABLE

    def test_join_unresolved_middle(self) -> None:
        assert _partial_join(PartialResult.PRUNABLE, PartialResult.UNRESOLVED) == PartialResult.UNRESOLVED

    def test_join_prunable_identity(self) -> None:
        assert _partial_join(PartialResult.PRUNABLE, PartialResult.PRUNABLE) == PartialResult.PRUNABLE


# ═══════════════════════════════════════════════════════════════════
# PrefixFeasibility
# ═══════════════════════════════════════════════════════════════════

class TestPrefixFeasibility:
    def test_from_sat_ratio_extendable(self) -> None:
        pf = PrefixFeasibility.from_sat_ratio(1.0)
        assert pf.is_extendable
        assert not pf.is_prunable
        assert not pf.is_unresolved
        assert pf.confidence > 0

    def test_from_sat_ratio_prunable(self) -> None:
        pf = PrefixFeasibility.from_sat_ratio(0.0)
        assert pf.is_prunable
        assert not pf.is_extendable

    def test_from_sat_ratio_unresolved(self) -> None:
        midpoint = (SAT_COHERENT + SAT_PLATEAU_LO) / 2.0
        pf = PrefixFeasibility.from_sat_ratio(midpoint)
        assert pf.is_unresolved

    def test_is_frontier_alias(self) -> None:
        pf = PrefixFeasibility.from_sat_ratio(0.87)
        assert pf.is_frontier == pf.is_unresolved

    def test_with_text(self) -> None:
        pf = PrefixFeasibility.from_sat_ratio(1.0, text="if A then B")
        assert pf.text == "if A then B"

    def test_clause_counts(self) -> None:
        pf = PrefixFeasibility.from_sat_ratio(
            0.9, clauses_free=10, clauses_fixed=5, clauses_dead=2
        )
        assert pf.clauses_free == 10
        assert pf.clauses_fixed == 5
        assert pf.clauses_dead == 2


# ═══════════════════════════════════════════════════════════════════
# SATConstraint
# ═══════════════════════════════════════════════════════════════════

class TestSATConstraint:
    def test_call_verified(self) -> None:
        c = SATConstraint(domain="logic")
        assert c("if A then B. A.") == Verdict.VERIFIED

    def test_call_contradiction(self) -> None:
        c = SATConstraint(domain="logic")
        result = c("A. not A.")
        # "A. not A." may be CONTRADICTION or PARADOX depending on extraction
        assert result in (Verdict.CONTRADICTION, Verdict.PARADOX)

    def test_partial_eval_extendable(self) -> None:
        c = SATConstraint(domain="logic")
        pf = c.partial_eval("if A then B. A.")
        assert isinstance(pf, PrefixFeasibility)

    def test_partial_eval_empty(self) -> None:
        c = SATConstraint(domain="logic")
        pf = c.partial_eval("")
        assert isinstance(pf, PrefixFeasibility)


# ═══════════════════════════════════════════════════════════════════
# FunctionConstraint
# ═══════════════════════════════════════════════════════════════════

class TestFunctionConstraint:
    def test_true_returns_verified(self) -> None:
        c = FunctionConstraint(lambda text: True)
        assert c("anything") == Verdict.VERIFIED

    def test_false_returns_contradiction(self) -> None:
        c = FunctionConstraint(lambda text: False)
        assert c("anything") == Verdict.CONTRADICTION

    def test_partial_no_fn_conservative(self) -> None:
        c = FunctionConstraint(lambda text: True)
        pf = c.partial_eval("prefix")
        assert pf.is_extendable

    def test_partial_with_fn(self) -> None:
        c = FunctionConstraint(
            lambda text: True,
            partial_fn=lambda prefix: PartialResult.PRUNABLE,
        )
        pf = c.partial_eval("prefix")
        assert pf.is_prunable

    def test_partial_unresolved(self) -> None:
        c = FunctionConstraint(
            lambda text: True,
            partial_fn=lambda prefix: PartialResult.UNRESOLVED,
        )
        pf = c.partial_eval("prefix")
        assert pf.is_unresolved


# ═══════════════════════════════════════════════════════════════════
# Compositional Constraints
# ═══════════════════════════════════════════════════════════════════

class TestConjunctiveConstraint:
    def test_both_verified(self) -> None:
        c = FunctionConstraint(lambda t: True) & FunctionConstraint(lambda t: True)
        assert c("x") == Verdict.VERIFIED

    def test_left_contradiction(self) -> None:
        c = FunctionConstraint(lambda t: False) & FunctionConstraint(lambda t: True)
        assert c("x") == Verdict.CONTRADICTION

    def test_right_contradiction(self) -> None:
        c = FunctionConstraint(lambda t: True) & FunctionConstraint(lambda t: False)
        assert c("x") == Verdict.CONTRADICTION

    def test_partial_eval_meet(self) -> None:
        c1 = FunctionConstraint(lambda t: True, partial_fn=lambda p: PartialResult.EXTENDABLE)
        c2 = FunctionConstraint(lambda t: True, partial_fn=lambda p: PartialResult.PRUNABLE)
        conj = c1 & c2
        pf = conj.partial_eval("x")
        # Meet: EXTENDABLE ∧ PRUNABLE = average ratio → probably PRUNABLE
        assert isinstance(pf, PrefixFeasibility)


class TestDisjunctiveConstraint:
    def test_either_verified(self) -> None:
        c = FunctionConstraint(lambda t: True) | FunctionConstraint(lambda t: False)
        assert c("x") == Verdict.VERIFIED

    def test_both_contradiction(self) -> None:
        c = FunctionConstraint(lambda t: False) | FunctionConstraint(lambda t: False)
        assert c("x") == Verdict.CONTRADICTION

    def test_partial_eval_join(self) -> None:
        c1 = FunctionConstraint(lambda t: True, partial_fn=lambda p: PartialResult.PRUNABLE)
        c2 = FunctionConstraint(lambda t: True, partial_fn=lambda p: PartialResult.EXTENDABLE)
        disj = c1 | c2
        pf = disj.partial_eval("x")
        assert isinstance(pf, PrefixFeasibility)


class TestNegatedConstraint:
    def test_negate_verified(self) -> None:
        c = ~FunctionConstraint(lambda t: True)
        assert c("x") == Verdict.CONTRADICTION

    def test_negate_contradiction(self) -> None:
        c = ~FunctionConstraint(lambda t: False)
        assert c("x") == Verdict.VERIFIED

    def test_partial_eval_flips(self) -> None:
        c = ~FunctionConstraint(
            lambda t: True,
            partial_fn=lambda p: PartialResult.EXTENDABLE,
        )
        pf = c.partial_eval("x")
        assert pf.is_prunable

    def test_partial_eval_prunable_to_extendable(self) -> None:
        c = ~FunctionConstraint(
            lambda t: True,
            partial_fn=lambda p: PartialResult.PRUNABLE,
        )
        pf = c.partial_eval("x")
        assert pf.is_extendable

    def test_partial_eval_unresolved_stays(self) -> None:
        c = ~FunctionConstraint(
            lambda t: True,
            partial_fn=lambda p: PartialResult.UNRESOLVED,
        )
        pf = c.partial_eval("x")
        assert pf.is_unresolved


class TestSequentialConstraint:
    def test_all_verified(self) -> None:
        c1 = FunctionConstraint(lambda t: True)
        c2 = FunctionConstraint(lambda t: True)
        seq = SequentialConstraint(c1, c2)
        assert seq("x") == Verdict.VERIFIED

    def test_one_contradiction(self) -> None:
        c1 = FunctionConstraint(lambda t: True)
        c2 = FunctionConstraint(lambda t: False)
        seq = SequentialConstraint(c1, c2)
        assert seq("x") == Verdict.CONTRADICTION

    def test_partial_returns_worst(self) -> None:
        c1 = FunctionConstraint(lambda t: True, partial_fn=lambda p: PartialResult.EXTENDABLE)
        c2 = FunctionConstraint(lambda t: True, partial_fn=lambda p: PartialResult.PRUNABLE)
        seq = SequentialConstraint(c1, c2)
        pf = seq.partial_eval("prefix")
        assert pf.is_prunable


# ═══════════════════════════════════════════════════════════════════
# ConstraintAlgebra factory
# ═══════════════════════════════════════════════════════════════════

class TestConstraintAlgebra:
    def test_sat(self) -> None:
        a = ConstraintAlgebra()
        c = a.sat("logic")
        assert isinstance(c, SATConstraint)

    def test_fn(self) -> None:
        a = ConstraintAlgebra()
        c = a.fn(lambda t: True)
        assert isinstance(c, FunctionConstraint)

    def test_all_of(self) -> None:
        a = ConstraintAlgebra()
        c = a.all_of(a.fn(lambda t: True), a.fn(lambda t: True))
        assert c("x") == Verdict.VERIFIED

    def test_all_of_empty_raises(self) -> None:
        a = ConstraintAlgebra()
        with pytest.raises(ValueError):
            a.all_of()

    def test_any_of(self) -> None:
        a = ConstraintAlgebra()
        c = a.any_of(a.fn(lambda t: False), a.fn(lambda t: True))
        assert c("x") == Verdict.VERIFIED

    def test_any_of_empty_raises(self) -> None:
        a = ConstraintAlgebra()
        with pytest.raises(ValueError):
            a.any_of()

    def test_chain(self) -> None:
        a = ConstraintAlgebra()
        c = a.chain(a.fn(lambda t: True), a.fn(lambda t: True))
        assert isinstance(c, SequentialConstraint)

    def test_never(self) -> None:
        a = ConstraintAlgebra()
        c = a.never(a.fn(lambda t: True))
        assert isinstance(c, NegatedConstraint)
        assert c("x") == Verdict.CONTRADICTION

    def test_module_level_algebra(self) -> None:
        assert isinstance(algebra, ConstraintAlgebra)
        c = algebra.sat("logic")
        assert c("if A then B. A.") == Verdict.VERIFIED
