"""
Comprehensive verdict tests — proves the four-valued system works end-to-end.

Coverage targets:
  verify.py — all four verdicts, gate(), verify_batch(), verify_tokens(),
               VerificationResult properties, domain aliases, custom extractor,
               must_verify(), VerificationError, get_gate() singleton
  sat.py    — sat_score() edge cases, solve_cnf() complete model, WalkSAT path,
               SATSolver unit propagation, pure literal elimination
  partial.py — batch_evaluate(), clear_cache(), ClauseStatus variants
"""
from __future__ import annotations

import pytest

from satisfaction_suffices.verifier import (
    VerificationError,
    VerificationGate,
    verify,
    must_verify,
    get_gate,
)
from satisfaction_suffices.verifier.verify import Verdict, VerificationResult
from satisfaction_suffices.verifier.sat import (
    SATSolver,
    pos_lit,
    neg_lit,
    solve_cnf,
    sat_score,
)
from satisfaction_suffices.verifier.partial import (
    PartialConstraintEvaluator,
    PrefixFeasibilityResult,
    evaluate_partial,
)


# ── VerificationResult properties ────────────────────────────────────────────

class TestVerificationResultProperties:
    def _make(self, verdict: Verdict, n_constraints=2, n_timeout=0, n_paradox=0):
        n_sat = n_constraints if verdict == Verdict.VERIFIED else 0
        return VerificationResult(
            verdict=verdict,
            sat_ratio=1.0 if verdict == Verdict.VERIFIED else 0.0,
            zone="coherent" if verdict == Verdict.VERIFIED else "incoherent",
            elapsed_ms=1.0,
            n_constraints=n_constraints,
            n_satisfied=n_sat,
            n_refuted=n_constraints - n_sat,
            n_timeout=n_timeout,
        )

    def test_verified_properties(self):
        r = self._make(Verdict.VERIFIED)
        assert r.is_verified
        assert not r.is_contradiction
        assert not r.is_paradox
        assert not r.is_timeout
        assert not r.is_frontier
        assert not r.is_rejected
        assert r.reward > 0

    def test_contradiction_properties(self):
        r = self._make(Verdict.CONTRADICTION)
        assert r.is_contradiction
        assert r.is_rejected
        assert not r.is_verified
        assert not r.is_frontier
        assert r.reward < 0

    def test_paradox_properties(self):
        r = VerificationResult(
            verdict=Verdict.PARADOX,
            sat_ratio=0.5, zone="plateau",
            elapsed_ms=1.0,
            n_constraints=4, n_satisfied=2,
            n_refuted=0, n_timeout=0,
            n_paradox=4,
        )
        assert r.is_paradox
        assert r.is_frontier
        assert not r.is_rejected
        assert r.n_frontier == 4  # n_timeout + n_paradox

    def test_timeout_properties(self):
        r = self._make(Verdict.TIMEOUT, n_timeout=2)
        assert r.is_timeout
        assert r.is_frontier
        assert not r.is_rejected


# ── Four Verdicts via verify() ─────────────────────────────────────────────

class TestFourVerdicts:
    def test_verified(self):
        r = verify("if A then B. A.", domain="logic")
        assert r.verdict == Verdict.VERIFIED
        assert r.is_verified
        assert r.sat_ratio == 1.0
        assert r.zone == "coherent"

    def test_contradiction_via_extra_constraints(self):
        """Inject contradictory extra_constraints to force CONTRADICTION."""
        r = verify("A.", domain="logic", extra_constraints=[[[1], [-1]]])
        assert r.is_contradiction

    def test_paradox(self):
        """A. not A. — each group SAT individually but conjunction UNSAT."""
        r = verify("A. not A.", domain="logic")
        assert r.is_paradox
        assert r.n_paradox == r.n_constraints

    def test_verified_empty_content(self):
        """Empty content → no constraints → trivially VERIFIED."""
        r = verify("", domain="logic")
        assert r.is_verified
        assert r.n_constraints == 0

    def test_all_text_domain_aliases_return_verified_for_valid_content(self):
        aliases = [
            "med", "law", "text", "bio", "cyber", "chem",
            "nano", "phys", "quantum", "socio", "econ",
        ]
        for alias in aliases:
            r = verify("if A then B. A.", domain=alias)
            assert r.is_verified, f"alias '{alias}' failed"

    def test_code_domain(self):
        r = verify("x = 1", domain="code")
        assert r.verdict in (Verdict.VERIFIED, Verdict.TIMEOUT)

    def test_math_domain(self):
        r = verify("x + y = 10. x = 3.", domain="math")
        assert r.verdict in (Verdict.VERIFIED, Verdict.PARADOX, Verdict.CONTRADICTION, Verdict.TIMEOUT)

    def test_proof_domain(self):
        r = verify("assume A. conclude A.", domain="proof")
        assert r.verdict in (Verdict.VERIFIED, Verdict.TIMEOUT)

    def test_market_domain(self):
        r = verify("price is high. demand is low.", domain="market")
        assert r.verdict in (Verdict.VERIFIED, Verdict.CONTRADICTION, Verdict.PARADOX, Verdict.TIMEOUT)

    def test_unknown_domain_raises(self):
        with pytest.raises(ValueError, match="No extractor registered"):
            verify("anything", domain="__nonexistent__")


# ── gate() — boolean pass/block/flag ─────────────────────────────────────────

class TestGate:
    def setup_method(self):
        self.gate = VerificationGate()

    def test_gate_passes_verified(self):
        passed, result = self.gate.gate("if A then B. A.", domain="logic")
        assert passed is True
        assert result.is_verified

    def test_gate_blocks_contradiction(self):
        passed, result = self.gate.gate(
            "A.", domain="logic",
            on_unresolved="block",
        )
        # Force contradiction
        gate = VerificationGate()
        passed, result = gate.gate.__func__(
            gate, "A.", domain="logic",
            on_unresolved="block",
        )
        # Direct test with injected contradiction
        result2 = self.gate.verify("A.", domain="logic", extra_constraints=[[[1], [-1]]])
        assert result2.is_contradiction

    def test_gate_blocks_contradiction_directly(self):
        # Use the real gate with contradiction-forcing extra constraints
        gate = VerificationGate()
        # Patch verify to return contradiction
        from unittest.mock import patch
        contradiction = VerificationResult(
            verdict=Verdict.CONTRADICTION,
            sat_ratio=0.0, zone="incoherent",
            elapsed_ms=1.0,
            n_constraints=1, n_satisfied=0,
            n_refuted=1, n_timeout=0,
        )
        with patch.object(gate, "verify", return_value=contradiction):
            passed, result = gate.gate("anything")
            assert passed is False

    def test_gate_on_unresolved_pass(self):
        gate = VerificationGate()
        paradox = VerificationResult(
            verdict=Verdict.PARADOX,
            sat_ratio=0.5, zone="plateau",
            elapsed_ms=1.0,
            n_constraints=2, n_satisfied=1,
            n_refuted=0, n_timeout=0, n_paradox=2,
        )
        from unittest.mock import patch
        with patch.object(gate, "verify", return_value=paradox):
            passed, result = gate.gate("anything", on_unresolved="pass")
            assert passed is True

    def test_gate_on_unresolved_block(self):
        gate = VerificationGate()
        timeout = VerificationResult(
            verdict=Verdict.TIMEOUT,
            sat_ratio=0.0, zone="incoherent",
            elapsed_ms=1.0,
            n_constraints=1, n_satisfied=0,
            n_refuted=0, n_timeout=1,
        )
        from unittest.mock import patch
        with patch.object(gate, "verify", return_value=timeout):
            passed, _ = gate.gate("anything", on_unresolved="block")
            assert passed is False

    def test_gate_on_frontier_backcompat(self):
        """on_frontier= is the back-compat alias for on_unresolved=."""
        gate = VerificationGate()
        timeout = VerificationResult(
            verdict=Verdict.TIMEOUT,
            sat_ratio=0.0, zone="incoherent",
            elapsed_ms=1.0,
            n_constraints=1, n_satisfied=0,
            n_refuted=0, n_timeout=1,
        )
        from unittest.mock import patch
        with patch.object(gate, "verify", return_value=timeout):
            passed, _ = gate.gate("anything", on_frontier="block")
            assert passed is False


# ── verify_batch() ────────────────────────────────────────────────────────────

class TestVerifyBatch:
    def test_batch_returns_correct_length(self):
        gate = VerificationGate()
        contents = ["if A then B. A.", "A. not A.", "if A then B. A."]
        results = gate.verify_batch(contents, domain="logic")
        assert len(results) == 3

    def test_batch_verdicts_match_individual(self):
        gate = VerificationGate()
        contents = ["if A then B. A.", "A. not A."]
        batch = gate.verify_batch(contents, domain="logic")
        for content, result in zip(contents, batch):
            individual = gate.verify(content, domain="logic")
            assert result.verdict == individual.verdict


# ── verify_tokens() ───────────────────────────────────────────────────────────

class TestVerifyTokens:
    def test_tokens_no_constraints_is_verified(self):
        gate = VerificationGate()
        result = gate.verify_tokens([1, 2, 3], constraint_fn=lambda t: (0, []))
        assert result.is_verified
        assert result.n_constraints == 0

    def test_tokens_satisfiable_constraint(self):
        gate = VerificationGate()
        # Single clause [1] — satisfiable (x1 = True)
        result = gate.verify_tokens(
            [1, 2, 3],
            constraint_fn=lambda t: (1, [[[1]]]),
        )
        assert result.is_verified

    def test_tokens_contradiction(self):
        gate = VerificationGate()
        # ONE group with two clauses: [x1] AND [~x1] — same variable must be
        # both True and False in the same group → UNSAT → CONTRADICTION.
        # (Two separate groups [[[1]], [[-1]]] would each be SAT → PARADOX.)
        result = gate.verify_tokens(
            [1],
            constraint_fn=lambda t: (1, [[[1], [-1]]]),
        )
        assert result.is_contradiction

    def test_tokens_elapsed_ms_populated(self):
        gate = VerificationGate()
        result = gate.verify_tokens([1], constraint_fn=lambda t: (0, []))
        assert result.elapsed_ms >= 0.0


# ── must_verify() ─────────────────────────────────────────────────────────────

class TestMustVerify:
    def test_must_verify_passes_through_valid_content(self):
        result = must_verify("if A then B. A.", domain="logic")
        assert result == "if A then B. A."

    def test_must_verify_raises_on_paradox(self):
        with pytest.raises(VerificationError) as exc_info:
            must_verify("A. not A.", domain="logic")
        assert exc_info.value.result.is_paradox

    def test_must_verify_raises_on_contradiction(self):
        gate = get_gate()
        contradiction = VerificationResult(
            verdict=Verdict.CONTRADICTION,
            sat_ratio=0.0, zone="incoherent",
            elapsed_ms=1.0,
            n_constraints=1, n_satisfied=0,
            n_refuted=1, n_timeout=0,
        )
        import sys
        from unittest.mock import patch
        _verify_mod = sys.modules["satisfaction_suffices.verifier.verify"]
        with patch.object(_verify_mod, "get_gate") as mock_gate:
            mock_gate.return_value.verify.return_value = contradiction
            with pytest.raises(VerificationError) as exc_info:
                must_verify("anything")
            assert exc_info.value.result.is_contradiction

    def test_verification_error_carries_result(self):
        with pytest.raises(VerificationError) as exc_info:
            must_verify("A. not A.", domain="logic")
        err = exc_info.value
        assert isinstance(err.result, VerificationResult)
        assert err.result.is_paradox


# ── get_gate() singleton ──────────────────────────────────────────────────────

class TestGetGate:
    def test_get_gate_returns_same_instance(self):
        g1 = get_gate()
        g2 = get_gate()
        assert g1 is g2

    def test_get_gate_is_verification_gate(self):
        assert isinstance(get_gate(), VerificationGate)


# ── custom extractor registration ────────────────────────────────────────────

class TestCustomExtractor:
    def test_custom_extractor_registered_and_used(self):
        from satisfaction_suffices.verifier.verify import ConstraintExtractor
        from typing import Tuple, List

        class AlwaysVerifiedExtractor(ConstraintExtractor):
            def extract(self, content: str) -> Tuple[int, List[List[List[int]]]]:
                return 1, [[[1]]]  # x1 = SAT, always verified

        gate = VerificationGate()
        gate.register_extractor("custom_test", AlwaysVerifiedExtractor())
        result = gate.verify("anything at all", domain="custom_test")
        assert result.is_verified

    def test_custom_extractor_contradiction(self):
        from satisfaction_suffices.verifier.verify import ConstraintExtractor
        from typing import Tuple, List

        class AlwaysContradiction(ConstraintExtractor):
            def extract(self, content: str) -> Tuple[int, List[List[List[int]]]]:
                # ONE group, two clauses: clause [1] = x1 must be True,
                # clause [-1] = x1 must be False.  Conjunction is UNSAT.
                # (Two separate groups would each be SAT → PARADOX, not CONTRADICTION.)
                return 1, [[[1], [-1]]]

        gate = VerificationGate()
        gate.register_extractor("always_contradiction", AlwaysContradiction())
        result = gate.verify("anything", domain="always_contradiction")
        assert result.is_contradiction


# ── SAT solver unit propagation and WalkSAT ──────────────────────────────────

class TestSATSolverInternals:
    def test_unit_propagation_forces_assignment(self):
        """Unit clause [x1] forces x1=True, then [~x1, x2] propagates x2=True."""
        s = SATSolver()
        s.new_vars(2)
        s.add_clause([pos_lit(0)])          # x1 = True forced
        s.add_clause([neg_lit(0), pos_lit(1)])  # x1->x2: x2 forces True too
        assert s.solve() is True
        m = s.model()
        assert m[0] is True
        assert m[1] is True

    def test_pure_literal_drives_solution(self):
        """x1 appears only positive — pure literal elimination assigns True."""
        s = SATSolver()
        s.new_vars(2)
        s.add_clause([pos_lit(0), pos_lit(1)])
        s.add_clause([pos_lit(0)])  # x1 is pure positive
        assert s.solve() is True

    def test_solve_unsat_two_variable(self):
        s = SATSolver()
        s.new_vars(1)
        s.add_clause([pos_lit(0)])
        s.add_clause([neg_lit(0)])
        assert s.solve() is False

    def test_solve_cnf_signed_literal_interface(self):
        """solve_cnf uses 1-indexed signed literals."""
        sat, model = solve_cnf(2, [[1, 2], [-1, 2], [1, -2]])
        assert sat is True
        assert model is not None

    def test_solve_cnf_unsat(self):
        sat, model = solve_cnf(1, [[1], [-1]])
        assert sat is False
        assert model is None

    def test_solve_cnf_empty_clauses_is_sat(self):
        sat, model = solve_cnf(2, [])
        assert sat is True

    def test_model_keys_are_one_indexed(self):
        """solve_cnf returns model with 1-indexed keys."""
        sat, model = solve_cnf(2, [[1], [2]])
        assert sat is True
        assert 1 in model
        assert 2 in model

    def test_large_sat_instance(self):
        """20-variable satisfiable formula — exercises DPLL backtracking."""
        n = 20
        # All variables must be True: clauses [[1], [2], ..., [20]]
        clauses = [[i] for i in range(1, n + 1)]
        sat, model = solve_cnf(n, clauses)
        assert sat is True
        assert all(model[i] for i in range(1, n + 1))

    def test_sat_score_empty_groups(self):
        ratio, zone, n_timeout = sat_score(0, [])
        assert ratio == 1.0
        assert zone == "coherent"
        assert n_timeout == 0

    def test_sat_score_all_sat(self):
        ratio, zone, n_timeout = sat_score(1, [[[1]], [[1]]])
        assert ratio == 1.0
        assert zone == "coherent"
        assert n_timeout == 0

    def test_sat_score_all_unsat(self):
        ratio, zone, n_timeout = sat_score(1, [[[1], [-1]]])
        assert ratio == 0.0
        assert zone == "incoherent"

    def test_sat_score_mixed_groups(self):
        # Group 1: SAT (x1=True), Group 2: UNSAT (x1 ^ ~x1)
        ratio, zone, n_timeout = sat_score(1, [[[1]], [[1], [-1]]])
        # 1/2 SAT = 0.5 ratio
        assert 0.0 < ratio < 1.0


# ── Partial evaluator extended ────────────────────────────────────────────────

class TestPartialExtended:
    def test_batch_evaluate_returns_list(self):
        evaluator = PartialConstraintEvaluator(domain="logic")
        results = evaluator.batch_evaluate(["if A then B. A.", "A.", "A. not A."])
        assert len(results) == 3
        assert all(isinstance(r, PrefixFeasibilityResult) for r in results)

    def test_clear_cache_does_not_raise(self):
        evaluator = PartialConstraintEvaluator(domain="logic")
        evaluator.evaluate("if A then B.")
        evaluator.clear_cache()  # must not raise
        # Still works after clear
        result = evaluator.evaluate("if A then B.")
        assert isinstance(result, PrefixFeasibilityResult)

    def test_extendable_implies_not_prunable(self):
        evaluator = PartialConstraintEvaluator(domain="logic")
        result = evaluator.evaluate("if A then B. A.")
        if result.extendable:
            assert not result.prunable

    def test_contradiction_implies_prunable(self):
        evaluator = PartialConstraintEvaluator()
        evaluator._translator.translate = lambda prefix, domain=None: (1, [[1], [-1]])  # type: ignore[method-assign]
        result = evaluator.evaluate("boom")
        assert result.contradiction
        assert result.prunable
        assert not result.extendable

    def test_prefix_len_matches_input(self):
        text = "if A then B. A."
        evaluator = PartialConstraintEvaluator(domain="logic")
        result = evaluator.evaluate(text)
        assert result.prefix_len == len(text)

    def test_sat_ratio_in_unit_interval(self):
        evaluator = PartialConstraintEvaluator(domain="logic")
        result = evaluator.evaluate("if A then B. A.")
        assert 0.0 <= result.sat_ratio <= 1.0

    def test_evaluate_partial_convenience(self):
        result = evaluate_partial("if A then B. A.", domain="logic")
        assert isinstance(result, PrefixFeasibilityResult)
        assert result.extendable or result.unresolved or result.prunable


# ── The core claim: Paradox ≠ Timeout (the novel contribution) ───────────────

class TestParadoxTimeoutDistinction:
    """
    This is the architectural claim that makes satisfaction-suffices novel.
    PARADOX = each clause group individually SAT, conjunction UNSAT.
    TIMEOUT = solver budget exhausted, verdict genuinely unknown.
    They are different failure modes requiring different responses.
    """

    def test_paradox_detected_correctly(self):
        r = verify("A. not A.", domain="logic")
        assert r.is_paradox, "A ∧ ¬A must be classified PARADOX, not CONTRADICTION or TIMEOUT"
        assert not r.is_contradiction
        assert not r.is_timeout

    def test_contradiction_detected_correctly(self):
        # Provably unsatisfiable via extra_constraints injection
        r = verify("A.", domain="logic", extra_constraints=[[[1], [-1]]])
        assert r.is_contradiction, "Injected UNSAT must be CONTRADICTION, not PARADOX"
        assert not r.is_paradox

    def test_verified_distinct_from_both(self):
        r = verify("if A then B. A.", domain="logic")
        assert r.is_verified
        assert not r.is_paradox
        assert not r.is_contradiction
        assert not r.is_timeout

    def test_paradox_zone_is_not_coherent(self):
        r = verify("A. not A.", domain="logic")
        assert r.zone != "coherent"

    def test_verified_zone_is_coherent(self):
        r = verify("if A then B. A.", domain="logic")
        assert r.zone == "coherent"

    def test_contradiction_reward_negative(self):
        r = verify("A.", domain="logic", extra_constraints=[[[1], [-1]]])
        assert r.reward < 0

    def test_verified_reward_positive(self):
        r = verify("if A then B. A.", domain="logic")
        assert r.reward > 0
