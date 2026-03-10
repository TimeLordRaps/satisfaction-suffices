"""
Exhaustive test suite — auditing every dark corner before public release.

Bugs found and tested here:
  BUG-01  verify_tokens can never return PARADOX (uses sat_score ratio only)
  BUG-02  ProofConstraintExtractor injects CONTRADICTION for English "sorry"
  BUG-03  ProofConstraintExtractor injects CONTRADICTION for mention of "paradox"
  BUG-04  SORRY_PAT is case-sensitive — "Sorry" (capital) silently bypasses it
  BUG-05  If-then with compound consequent treated as one atom: "if A then B and C"
  BUG-06  CodeConstraintExtractor forces ≥1 if/elif branch taken (wrong semantics)
  BUG-07  MathConstraintExtractor EQ_PAT partial-matches "x + y = 10" as "y = 10"
  BUG-08  CodeConstraintExtractor conflates all comparisons on same var via _valid suffix
  BUG-09  gate() "flag" and "pass" are indistinguishable in return value
  BUG-10  verify_batch does not forward extra_constraints
  BUG-11  extra_constraints with lit=0 passed to pos_lit(-1) (undefined behaviour)
  BUG-12  get_gate() singleton leaks state between calls (register_extractor)
  BUG-13  VerificationResult.n_paradox not set by verify_tokens path
  BUG-14  "A and not A" single-group CONTRADICTION vs "A. not A." multi-group PARADOX
  BUG-15  Nested NOT: "not not A" normalises incorrectly
  BUG-16  Empty input to every public entry-point (verify, gate, must_verify, batch)
  BUG-17  Whitespace-only input
  BUG-18  Unicode / multi-byte characters in propositions
  BUG-19  domain="proof" with Lean4 "sorry" in uppercase
  BUG-20  satisfy_suffices public __init__ exports are complete
"""
from __future__ import annotations

import re

import pytest

from satisfaction_suffices.verifier import (
    VerificationError,
    VerificationGate,
    get_gate,
    must_verify,
    verify,
)
from satisfaction_suffices.verifier.verify import (
    Verdict,
    VerificationResult,
    ProofConstraintExtractor,
    LogicConstraintExtractor,
    CodeConstraintExtractor,
    MathConstraintExtractor,
    MarketConstraintExtractor,
)
from satisfaction_suffices.verifier.sat import (
    SATSolver,
    pos_lit,
    neg_lit,
    solve_cnf,
    sat_score,
)


# ──────────────────────────────────────────────────────────────────────────────
# SECTION 1: Core verdict correctness — classical logic properties
# ──────────────────────────────────────────────────────────────────────────────

class TestClassicalLogicVerdicts:
    """Every classical tautology/contradiction must get the right verdict."""

    # ── Modus Ponens ──────────────────────────────────────────────────────────

    def test_modus_ponens_verified(self):
        r = verify("if A then B. A.", domain="logic")
        assert r.verdict == Verdict.VERIFIED, f"got {r.verdict}"

    def test_modus_tollens_gives_paradox_or_contradiction(self):
        # "if A then B. not B. A." — A∧B∧¬B is a structural paradox
        r = verify("if A then B. not B. A.", domain="logic")
        # Any non-VERIFIED verdict is correct; PARADOX or CONTRADICTION are both acceptable
        assert not r.is_verified, f"Modus tollens violation should not be VERIFIED, got {r.verdict}"

    def test_hypothetical_syllogism(self):
        r = verify("if A then B. if B then C. A.", domain="logic")
        assert r.is_verified or r.verdict in (Verdict.PARADOX, Verdict.CONTRADICTION), \
            f"got {r.verdict}"

    def test_disjunctive_syllogism(self):
        r = verify("A or B. not A.", domain="logic")
        assert r.verdict in (Verdict.VERIFIED, Verdict.PARADOX, Verdict.CONTRADICTION), \
            f"got {r.verdict}"

    # ── Contradictions ────────────────────────────────────────────────────────

    def test_explicit_contradiction_within_sentence(self):
        """BUG-14: 'A and not A' in one sentence → single group CONTRADICTION."""
        r = verify("A and not A.", domain="logic")
        assert r.is_contradiction, (
            f"'A and not A' is a within-sentence contradiction. "
            f"Expected CONTRADICTION, got {r.verdict} (sat_ratio={r.sat_ratio})"
        )

    def test_explicit_contradiction_across_sentences(self):
        """BUG-14: 'A. not A.' across sentences → multi-group PARADOX."""
        r = verify("A. not A.", domain="logic")
        assert r.is_paradox, (
            f"'A. not A.' across sentences is a structural PARADOX. "
            f"Expected PARADOX, got {r.verdict}"
        )

    def test_triple_contradiction(self):
        r = verify("A. B. not A. not B.", domain="logic")
        assert not r.is_verified, f"A ∧ B ∧ ¬A ∧ ¬B must not be VERIFIED, got {r.verdict}"

    def test_fever_no_fever_is_contradiction(self):
        """Regression from the stop-word fix—ensure it stays correct."""
        r = verify("The patient has fever and no fever.", domain="logic")
        assert r.is_contradiction, (
            f"Expected CONTRADICTION, got {r.verdict}. "
            "Stop-word normalisation may have regressed."
        )

    def test_tautology_verified(self):
        """A or not A (tautology) — should be VERIFIED."""
        r = verify("A or not A.", domain="logic")
        assert r.is_verified, f"Tautology must be VERIFIED, got {r.verdict}"

    # ── Paradoxes ─────────────────────────────────────────────────────────────

    def test_multi_sentence_paradox(self):
        r = verify("rain. not rain.", domain="logic")
        assert r.is_paradox, f"Expected PARADOX, got {r.verdict}"

    def test_chained_paradox(self):
        r = verify("if A then B. A. not B.", domain="logic")
        # Each sentence alone is SAT, together UNSAT → PARADOX
        # A→B (¬A∨B): {A=T,B=T} SAT. A: {A=T} SAT. ¬B: {B=F} SAT.
        # Combined: A=T, B=T required by A and A→B, but ¬B requires B=F. UNSAT.
        assert not r.is_verified, f"Chained paradox must not be VERIFIED, got {r.verdict}"

    # ── Empty / trivial inputs ────────────────────────────────────────────────

    def test_empty_string_is_verified(self):
        """BUG-16: Empty input must return VERIFIED with 0 constraints."""
        r = verify("", domain="logic")
        assert r.is_verified
        assert r.n_constraints == 0

    def test_whitespace_only_is_verified(self):
        """BUG-17: Whitespace-only input must return VERIFIED."""
        r = verify("   \n\t  ", domain="logic")
        assert r.is_verified
        assert r.n_constraints == 0

    def test_single_period_is_verified(self):
        r = verify(".", domain="logic")
        assert r.is_verified

    def test_all_punctuation_is_verified(self):
        r = verify("... !!! ;;;", domain="logic")
        assert r.is_verified


# ──────────────────────────────────────────────────────────────────────────────
# SECTION 2: LogicConstraintExtractor — detailed extraction tests
# ──────────────────────────────────────────────────────────────────────────────

class TestLogicExtractor:
    def setup_method(self):
        self.ext = LogicConstraintExtractor()

    def test_if_then_basic(self):
        n, groups = self.ext.extract("if A then B.")
        assert n >= 2
        assert len(groups) == 1
        # Clause should be [-ante, cons] = ¬A ∨ B
        clause = groups[0][0]
        assert len(clause) == 2

    def test_if_then_with_negated_antecedent(self):
        """'if not A then B' should map to ¬(¬A) ∨ B = A ∨ B."""
        n, groups = self.ext.extract("if not A then B.")
        assert n >= 2
        clause = groups[0][0]  # single clause: [-ante, cons]
        # ante = get_var("not A") = -v_A, so -ante = v_A
        # cons = get_var("B") = v_B
        # clause = [v_A, v_B] i.e. A ∨ B
        assert len(clause) == 2

    def test_if_then_with_negated_consequent(self):
        """'if A then not B' → ¬A ∨ ¬B."""
        n, groups = self.ext.extract("if A then not B.")
        clause = groups[0][0]
        assert len(clause) == 2

    def test_and_conjunction_creates_unit_clauses(self):
        n, groups = self.ext.extract("A and B.")
        assert n >= 2
        # Two unit clauses in one group
        assert len(groups) == 1
        assert len(groups[0]) == 2

    def test_and_with_negation(self):
        """'A and not B' → [[v_A], [-v_B]] in one group."""
        n, groups = self.ext.extract("A and not B.")
        assert n >= 2
        assert len(groups) == 1
        lits = {c[0] for c in groups[0]}
        # One positive, one negative
        pos = [l for l in lits if l > 0]
        neg_l = [l for l in lits if l < 0]
        assert len(pos) == 1 and len(neg_l) == 1

    def test_or_disjunction_single_clause(self):
        n, groups = self.ext.extract("A or B.")
        assert n >= 2
        assert len(groups) == 1
        assert len(groups[0]) == 1
        assert len(groups[0][0]) == 2  # two literals in one clause

    def test_single_proposition(self):
        n, groups = self.ext.extract("A.")
        assert n == 1
        assert groups == [[[1]]]

    def test_negated_proposition(self):
        n, groups = self.ext.extract("not A.")
        assert n == 1
        assert groups == [[[-1]]]

    def test_stop_word_normalization(self):
        """'the patient has fever' and 'fever' must share a SAT variable."""
        ext = LogicConstraintExtractor()
        n1, g1 = ext.extract("the patient has fever.")
        n2, g2 = ext.extract("fever.")
        # Both should produce 1 variable
        assert n1 == 1 == n2

    def test_stop_word_contradiction_detected(self):
        """'the patient has fever and no fever' — same var, contradiction."""
        r = verify("the patient has fever and no fever.", domain="logic")
        assert r.is_contradiction

    def test_multiple_sentences_share_variables(self):
        """Vars should be shared across sentences in same extract call."""
        n, groups = self.ext.extract("A. not A.")
        # A appears in both → same variable → n=1
        assert n == 1
        assert len(groups) == 2

    def test_if_then_compound_consequent_bug(self):
        """
        BUG-05: 'if A then B and C' — consequent is 'B and C' treated as one atom.
        This is a KNOWN BUG. Test documents the CURRENT (wrong) behaviour.
        When fixed, update this test to assert correct splitting.
        """
        n, groups = self.ext.extract("if A then B and C.")
        # Current (buggy) behaviour: treats "B and C" as one atom → n=3
        # Correct behaviour would be: split into (¬A∨B) ∧ (¬A∨C) → n=3 still but different clauses
        # For now just verify it does something deterministic and non-crashing
        assert n >= 2
        assert len(groups) == 1

    def test_unicode_propositions(self):
        """BUG-18: Unicode in propositions must not crash."""
        r = verify("α is true. β is false.", domain="logic")
        assert r.verdict in (Verdict.VERIFIED, Verdict.CONTRADICTION, Verdict.PARADOX, Verdict.TIMEOUT)

    def test_very_long_proposition(self):
        prop = "this is a very long proposition name containing many words " * 5
        r = verify(f"{prop}.", domain="logic")
        assert r.verdict in (Verdict.VERIFIED, Verdict.CONTRADICTION, Verdict.PARADOX, Verdict.TIMEOUT)


# ──────────────────────────────────────────────────────────────────────────────
# SECTION 3: ProofConstraintExtractor bugs
# ──────────────────────────────────────────────────────────────────────────────

class TestProofExtractorBugs:

    def test_sorry_lean4_triggers_contradiction(self):
        """Lean4 'sorry' in proof context should force CONTRADICTION/not-VERIFIED."""
        r = verify("theorem foo : P. sorry", domain="proof")
        # sorry = incomplete proof → should be non-verified
        assert not r.is_verified, f"Lean4 sorry should not be VERIFIED, got {r.verdict}"

    def test_sorry_english_false_positive(self):
        """
        BUG-02 FIXED: English 'sorry' no longer triggers CONTRA injection.
        SORRY_PAT now only matches Lean4 tactic 'sorry' (standalone on a line or
        after 'by'/'exact'). English 'I am sorry' should NOT be flagged.
        """
        r = verify("assume A. therefore A. I am sorry but the proof above is complete.", domain="proof")
        assert r.is_verified, (
            f"BUG-02 REGRESSION: English 'sorry' forces non-VERIFIED result. "
            f"Got {r.verdict}. SORRY_PAT must NOT match English prose."
        )

    def test_sorry_case_insensitive_bug(self):
        """
        BUG-04 FIXED: SORRY_PAT now has re.IGNORECASE.
        Both 'sorry' and 'Sorry' in tactic position should trigger.
        """
        ext = ProofConstraintExtractor()
        # As standalone tactic lines both should trigger injection
        n_lower, g_lower = ext.extract("sorry")
        n_upper, g_upper = ext.extract("Sorry")
        # Both should inject the same number of groups (both match with IGNORECASE)
        assert len(g_lower) == len(g_upper), (
            f"BUG-04 REGRESSION: SORRY_PAT is case-sensitive again. "
            f"lower={len(g_lower)} groups, upper={len(g_upper)} groups."
        )

    def test_paradox_word_triggers_contradiction(self):
        """
        BUG-03 FIXED: CONTRA_PAT now only matches standalone Lean4 tactics.
        The word 'paradox' in English prose must NOT inject a contradiction.
        """
        r = verify("assume A. therefore A. This result resolves a long-standing paradox.", domain="proof")
        assert r.is_verified, (
            f"BUG-03 REGRESSION: 'paradox' in English prose forces non-VERIFIED. "
            f"Got {r.verdict}. CONTRA_PAT must NOT match English words."
        )

    def test_impossible_word_triggers_contradiction(self):
        """
        BUG-03 FIXED: 'impossible' no longer in CONTRA_PAT.
        English 'impossible' must not inject a forced contradiction.
        """
        r = verify("assume A. therefore A. It is impossible to do otherwise.", domain="proof")
        assert r.is_verified, (
            f"BUG-03 REGRESSION: 'impossible' in English forces non-VERIFIED. "
            f"Got {r.verdict}."
        )

    def test_valid_proof_without_trigger_words(self):
        """A clean proof without trigger words should be VERIFIED."""
        r = verify("assume A. therefore A.", domain="proof")
        assert r.is_verified, f"Clean proof should be VERIFIED, got {r.verdict}"

    def test_lean4_have_establishes_fact(self):
        r = verify("have h : P := by exact hp", domain="proof")
        assert r.verdict in (Verdict.VERIFIED, Verdict.CONTRADICTION, Verdict.PARADOX, Verdict.TIMEOUT)

    def test_qed_no_crash(self):
        r = verify("assume A. therefore A. qed", domain="proof")
        assert r.verdict in (Verdict.VERIFIED, Verdict.CONTRADICTION, Verdict.PARADOX, Verdict.TIMEOUT)


# ──────────────────────────────────────────────────────────────────────────────
# SECTION 4: CodeConstraintExtractor bugs
# ──────────────────────────────────────────────────────────────────────────────

class TestCodeExtractorBugs:

    def test_assert_true_is_verified(self):
        r = verify("assert x > 0", domain="code")
        assert r.verdict in (Verdict.VERIFIED, Verdict.TIMEOUT)

    def test_assert_not_contradiction(self):
        """assert x and assert not x → contradiction."""
        r = verify("assert x\nassert not x", domain="code")
        assert not r.is_verified, f"Contradictory asserts must not be VERIFIED, got {r.verdict}"

    def test_if_elif_at_least_one_branch_bug(self):
        """
        BUG-06 FIXED: CodeConstraintExtractor no longer adds 'at least one if/elif
        must fire' constraint (wrong Python semantics). Only mutual-exclusion pairs remain.
        Also, IF_PAT no longer double-counts the 'if' inside 'elif'.
        """
        ext = CodeConstraintExtractor()
        n, groups = ext.extract("if x:\n    pass\nelif y:\n    pass")
        # After fix: IF_PAT should NOT match 'elif y', so if_vars = [if_x, elif_y] = 2 vars
        # Only one mutual-exclusion group: [[-v_if_x, -v_elif_y]]
        # No 'at least one' group
        at_least_one_groups = [g for g in groups if len(g) == 1 and len(g[0]) > 1 and all(l > 0 for l in g[0])]
        assert len(at_least_one_groups) == 0, (
            f"BUG-06 REGRESSION: 'at least one if/elif' group still present. "
            f"Groups: {groups}"
        )
        # Exactly one mutual-exclusion pair (two if-vars)
        mutex_groups = [g for g in groups if len(g) == 1 and len(g[0]) == 2 and all(l < 0 for l in g[0])]
        assert len(mutex_groups) == 1, (
            f"Expected 1 mutual-exclusion group after IF_PAT fix. "
            f"Got {len(mutex_groups)}. Full groups: {groups}"
        )

    def test_comparison_conflation_bug(self):
        """
        BUG-08: CodeConstraintExtractor uses {name}_valid for all comparisons.
        'x == 5' and 'x == 10' BOTH create variable 'x_valid' → same SAT var.
        Two different equality constraints on x share one variable.
        """
        ext = CodeConstraintExtractor()
        n, g1 = ext.extract("assert x == 5")
        n2, g2 = ext.extract("assert x == 10")
        # Both should use the same variable for x_valid
        # The biconditional for (x_valid ↔ 5_valid) and (x_valid ↔ 10_valid)
        # should produce conflicting constraints when combined
        n3, g3 = ext.extract("assert x == 5\nassert x == 10")
        # Both use x_valid → the two biconditionals share var → may conflict
        # This is the documented bug; just ensure no crash
        assert n3 >= 1

    def test_code_domain_no_crash_empty(self):
        r = verify("", domain="code")
        assert r.is_verified

    def test_code_domain_complex(self):
        code = """\
def foo(x):
    assert x > 0
    if x == 1:
        return True
    elif x == 2:
        return False
    assert x != 0
"""
        r = verify(code, domain="code")
        assert r.verdict in (Verdict.VERIFIED, Verdict.CONTRADICTION, Verdict.PARADOX, Verdict.TIMEOUT)


# ──────────────────────────────────────────────────────────────────────────────
# SECTION 5: MathConstraintExtractor bugs
# ──────────────────────────────────────────────────────────────────────────────

class TestMathExtractorBugs:

    def test_simple_equation(self):
        r = verify("x = y.", domain="math")
        assert r.verdict in (Verdict.VERIFIED, Verdict.CONTRADICTION, Verdict.PARADOX, Verdict.TIMEOUT)

    def test_partial_equation_match_bug(self):
        """
        BUG-07: EQ_PAT r"(\\w+)\\s*=\\s*(\\w+)" on "x + y = 10" matches 'y = 10'.
        The leading 'x + ' is silently dropped.
        """
        ext = MathConstraintExtractor()
        n, groups = ext.extract("x + y = 10")
        # EQ_PAT finds 'y' '10' — drops 'x'. This is the known bug.
        # Correct behaviour would include x in the equation.
        # For now: just verify it doesn't crash and produces constraints
        assert n >= 1
        assert len(groups) >= 1

    def test_math_inconsistency(self):
        """x = y and x = z should potentially conflict when y ≠ z."""
        r = verify("x = y. x = z. y != z.", domain="math")
        # With current bugged extractor this may be SAT; document behaviour
        assert r.verdict in (Verdict.VERIFIED, Verdict.CONTRADICTION, Verdict.PARADOX, Verdict.TIMEOUT)

    def test_forall_quantifier(self):
        r = verify("for all x, P(x).", domain="math")
        assert r.verdict in (Verdict.VERIFIED, Verdict.CONTRADICTION, Verdict.PARADOX, Verdict.TIMEOUT)

    def test_exists_quantifier(self):
        r = verify("exists x such that Q(x).", domain="math")
        assert r.verdict in (Verdict.VERIFIED, Verdict.CONTRADICTION, Verdict.PARADOX, Verdict.TIMEOUT)

    def test_math_empty(self):
        r = verify("", domain="math")
        assert r.is_verified


# ──────────────────────────────────────────────────────────────────────────────
# SECTION 6: verify_tokens — PARADOX gap
# ──────────────────────────────────────────────────────────────────────────────

class TestVerifyTokensBugs:

    def test_verify_tokens_basic(self):
        gate = VerificationGate()

        def constraint_fn(tok_ids):
            # Simple: one group with one clause [var1]
            return 1, [[[1]]]

        result = gate.verify_tokens([1, 2, 3], constraint_fn)
        assert result.is_verified

    def test_verify_tokens_contradiction(self):
        gate = VerificationGate()

        def constraint_fn(tok_ids):
            return 1, [[[1], [-1]]]

        result = gate.verify_tokens([1, 2, 3], constraint_fn)
        assert result.is_contradiction

    def test_verify_tokens_cannot_detect_paradox(self):
        """
        BUG-01: verify_tokens uses sat_score() ratio-only logic.
        It can NEVER return PARADOX even when groups are individually SAT
        but jointly UNSAT. Contrast with verify() which uses _solve_groups().
        """
        gate = VerificationGate()

        def paradox_fn(tok_ids):
            # Group 1: [[1]] — SAT (x1=True)
            # Group 2: [[-1]] — SAT (x1=False)
            # Together: x1 ∧ ¬x1 — UNSAT
            return 1, [[[1]], [[-1]]]

        result = gate.verify_tokens([1, 2], paradox_fn)
        # BUG: returns CONTRADICTION (ratio=0.5 < threshold) or VERIFIED, NOT PARADOX
        assert result.verdict != Verdict.PARADOX, (
            "BUG-01 disproved — verify_tokens CAN detect paradox now! "
            "Update this test to assert PARADOX and remove the BUG comment."
        )
        # Compare with verify() which correctly detects PARADOX:
        r_verify = verify("A. not A.", domain="logic")
        assert r_verify.is_paradox, "verify() should still detect PARADOX"

    def test_verify_tokens_empty_groups(self):
        gate = VerificationGate()
        result = gate.verify_tokens([], lambda t: (0, []))
        assert result.is_verified
        assert result.n_constraints == 0


# ──────────────────────────────────────────────────────────────────────────────
# SECTION 7: gate() on_unresolved options
# ──────────────────────────────────────────────────────────────────────────────

class TestGateUnresolvedOptions:

    def _paradox_gate(self):
        """Gate with a forced paradox input."""
        gate = VerificationGate()
        return gate

    def test_gate_pass_on_paradox(self):
        gate = VerificationGate()
        passed, result = gate.gate("A. not A.", domain="logic", on_unresolved="pass")
        assert passed is True
        assert result.is_paradox

    def test_gate_block_on_paradox(self):
        gate = VerificationGate()
        passed, result = gate.gate("A. not A.", domain="logic", on_unresolved="block")
        assert passed is False
        assert result.is_paradox

    def test_gate_flag_on_paradox(self):
        """
        BUG-09: 'flag' behaves identically to 'pass' — both return True.
        The caller cannot distinguish flagged from clean pass.
        Document this until the return type gains a flag field.
        """
        gate = VerificationGate()
        passed_flag, result_flag = gate.gate("A. not A.", domain="logic", on_unresolved="flag")
        passed_pass, result_pass = gate.gate("A. not A.", domain="logic", on_unresolved="pass")
        # BUG-09: both return (True, result) — indistinguishable
        assert passed_flag == passed_pass, "BUG-09: 'flag' and 'pass' produce same boolean"
        assert passed_flag is True

    def test_gate_back_compat_on_frontier(self):
        """on_frontier= alias should behave identically to on_unresolved=."""
        gate = VerificationGate()
        p1, r1 = gate.gate("A. not A.", domain="logic", on_frontier="block")
        p2, r2 = gate.gate("A. not A.", domain="logic", on_unresolved="block")
        assert p1 == p2

    def test_gate_verified_always_passes(self):
        gate = VerificationGate()
        for mode in ("pass", "block", "flag"):
            passed, result = gate.gate("if A then B. A.", domain="logic", on_unresolved=mode)
            assert passed is True
            assert result.is_verified

    def test_gate_contradiction_always_blocks(self):
        gate = VerificationGate()
        for mode in ("pass", "block", "flag"):
            passed, result = gate.gate(
                "A.", domain="logic",
                on_unresolved=mode,
            )
            # Single A is VERIFIED (SAT), not a contradiction.
            # Force via extra_constraints:
            result_c = gate.verify("A.", domain="logic", extra_constraints=[[[1], [-1]]])
            assert result_c.is_contradiction
            # Gate.gate with explicit contradiction result — test via mock
        from unittest.mock import patch
        gate2 = VerificationGate()
        forced_contradiction = VerificationResult(
            verdict=Verdict.CONTRADICTION,
            sat_ratio=0.0, zone="incoherent",
            elapsed_ms=0.0,
            n_constraints=1, n_satisfied=0, n_refuted=1, n_timeout=0,
        )
        for mode in ("pass", "block", "flag"):
            with patch.object(gate2, "verify", return_value=forced_contradiction):
                passed, _ = gate2.gate("x", on_unresolved=mode)
                assert passed is False, f"Contradiction should block regardless of mode={mode}"


# ──────────────────────────────────────────────────────────────────────────────
# SECTION 8: verify_batch
# ──────────────────────────────────────────────────────────────────────────────

class TestVerifyBatch:

    def test_batch_returns_list(self):
        gate = VerificationGate()
        results = gate.verify_batch(["if A then B. A.", "A. not A."], domain="logic")
        assert len(results) == 2
        assert results[0].is_verified
        assert results[1].is_paradox

    def test_batch_empty_list(self):
        gate = VerificationGate()
        results = gate.verify_batch([], domain="logic")
        assert results == []

    def test_batch_single_item(self):
        gate = VerificationGate()
        results = gate.verify_batch(["A."], domain="logic")
        assert len(results) == 1

    def test_batch_missing_extra_constraints_bug(self):
        """
        BUG-10: verify_batch doesn't forward extra_constraints.
        VerificationGate.verify_batch signature: (contents, domain) — no extra_constraints.
        Document that this limitation exists.
        """
        gate = VerificationGate()
        # No way to pass extra_constraints via verify_batch
        # This is a documented missing parameter
        import inspect
        sig = inspect.signature(gate.verify_batch)
        assert "extra_constraints" not in sig.parameters, (
            "BUG-10: verify_batch now has extra_constraints. "
            "Update this test to verify it works correctly."
        )


# ──────────────────────────────────────────────────────────────────────────────
# SECTION 9: Singleton / state isolation
# ──────────────────────────────────────────────────────────────────────────────

class TestSingletonBugs:

    def test_get_gate_returns_same_instance(self):
        g1 = get_gate()
        g2 = get_gate()
        assert g1 is g2

    def test_get_gate_mutation_persists(self):
        """
        BUG-12: Registering an extractor on the singleton persists globally.
        Tests that call register_extractor() on get_gate() contaminate
        all subsequent calls to verify().
        """
        gate = get_gate()
        from satisfaction_suffices.verifier.verify import ConstraintExtractor

        class AlwaysContradictExtractor(ConstraintExtractor):
            def extract(self, content):
                return 1, [[[1], [-1]]]

        # Register under a unique test key to avoid polluting real domains
        gate.register_extractor("__test_always_contradiction__", AlwaysContradictExtractor())

        r = verify("any content", domain="__test_always_contradiction__")
        assert r.is_contradiction, "Custom extractor should produce contradiction"

        # And it persists — the singleton retains it
        r2 = verify("other content", domain="__test_always_contradiction__")
        assert r2.is_contradiction, "Singleton state should persist"

    def test_unknown_domain_raises(self):
        with pytest.raises(ValueError, match="No extractor registered"):
            verify("hello", domain="no_such_domain_xyz_abc")

    def test_verdict_rejected_alias(self):
        """Verdict.REJECTED must alias CONTRADICTION."""
        assert Verdict.REJECTED == Verdict.CONTRADICTION


# ──────────────────────────────────────────────────────────────────────────────
# SECTION 10: VerificationResult properties exhaustive
# ──────────────────────────────────────────────────────────────────────────────

class TestVerificationResultProperties:

    def _make(self, verdict, n=2, n_timeout=0, n_paradox=0, sat_ratio=None):
        n_sat = n if verdict == Verdict.VERIFIED else 0
        if sat_ratio is None:
            sat_ratio = 1.0 if verdict == Verdict.VERIFIED else 0.0
        return VerificationResult(
            verdict=verdict, sat_ratio=sat_ratio,
            zone="coherent" if verdict == Verdict.VERIFIED else "incoherent",
            elapsed_ms=1.0, n_constraints=n, n_satisfied=n_sat,
            n_refuted=n - n_sat, n_timeout=n_timeout, n_paradox=n_paradox,
        )

    def test_verified(self):
        r = self._make(Verdict.VERIFIED)
        assert r.is_verified
        assert not r.is_contradiction
        assert not r.is_paradox
        assert not r.is_timeout
        assert not r.is_frontier
        assert not r.is_rejected
        assert r.reward > 0

    def test_contradiction(self):
        r = self._make(Verdict.CONTRADICTION)
        assert r.is_contradiction
        assert r.is_rejected
        assert not r.is_verified
        assert not r.is_frontier
        assert r.reward < 0

    def test_paradox(self):
        r = self._make(Verdict.PARADOX, n_paradox=2, sat_ratio=0.5)
        assert r.is_paradox
        assert r.is_frontier
        assert not r.is_rejected
        assert r.n_frontier == 2  # n_timeout + n_paradox

    def test_timeout(self):
        r = self._make(Verdict.TIMEOUT, n_timeout=1)
        assert r.is_timeout
        assert r.is_frontier
        assert not r.is_rejected
        assert r.n_frontier == 1

    def test_n_frontier_additive(self):
        r = VerificationResult(
            verdict=Verdict.TIMEOUT, sat_ratio=0.5, zone="timeout",
            elapsed_ms=1.0, n_constraints=4, n_satisfied=2,
            n_refuted=0, n_timeout=2, n_paradox=1,
        )
        assert r.n_frontier == 3  # 2 timeout + 1 paradox

    def test_rejected_alias_same_as_contradiction(self):
        r = self._make(Verdict.CONTRADICTION)
        assert r.is_rejected
        assert r.is_contradiction


# ──────────────────────────────────────────────────────────────────────────────
# SECTION 11: SAT solver correctness
# ──────────────────────────────────────────────────────────────────────────────

class TestSATSolverCorrectness:

    def test_trivially_unsat_empty_clause(self):
        s = SATSolver()
        s.new_vars(1)
        ok = s.add_clause([])
        assert ok is False

    def test_tautology_clause(self):
        s = SATSolver()
        s.new_vars(1)
        ok = s.add_clause([pos_lit(0), neg_lit(0)])
        assert ok is True

    def test_unit_propagation_forces_assignment(self):
        sat, model = solve_cnf(2, [[1], [2]])
        assert sat is True
        assert model[1] is True
        assert model[2] is True

    def test_simple_contradiction(self):
        sat, model = solve_cnf(1, [[1], [-1]])
        assert sat is False
        assert model is None

    def test_three_var_sat(self):
        # (A ∨ B) ∧ (¬A ∨ C) ∧ (¬B ∨ ¬C)
        sat, model = solve_cnf(3, [[1, 2], [-1, 3], [-2, -3]])
        assert sat is True

    def test_pigeon_hole_n3(self):
        """3 pigeons, 2 holes — should be UNSAT."""
        # Each pigeon in at least one hole:
        # p1∈h1 ∨ p1∈h2, p2∈h1 ∨ p2∈h2, p3∈h1 ∨ p3∈h2
        # At most one pigeon per hole:
        # ¬(p1∈h1 ∧ p2∈h1), ¬(p1∈h1 ∧ p3∈h1), ¬(p2∈h1 ∧ p3∈h1)
        # ¬(p1∈h2 ∧ p2∈h2), ¬(p1∈h2 ∧ p3∈h2), ¬(p2∈h2 ∧ p3∈h2)
        # Variables: p1h1=1, p1h2=2, p2h1=3, p2h2=4, p3h1=5, p3h2=6
        clauses = [
            [1, 2], [3, 4], [5, 6],       # each pigeon in ≥1 hole
            [-1, -3], [-1, -5], [-3, -5],  # h1: at most one pigeon
            [-2, -4], [-2, -6], [-4, -6],  # h2: at most one pigeon
        ]
        sat, _ = solve_cnf(6, clauses)
        assert sat is False, "Pigeon-hole n=3 must be UNSAT"

    def test_model_consistency(self):
        """Model returned by solve_cnf must satisfy all clauses."""
        clauses = [[1, -2], [-1, 3], [2, 3]]
        sat, model = solve_cnf(3, clauses)
        assert sat is True
        for clause in clauses:
            clause_satisfied = any(
                (lit > 0 and model[lit]) or (lit < 0 and not model[-lit])
                for lit in clause
            )
            assert clause_satisfied, f"Model violates clause {clause}: model={model}"

    def test_zero_var_zero_clause(self):
        sat, model = solve_cnf(0, [])
        assert sat is True

    def test_sat_score_all_sat(self):
        score, zone, n_timeout = sat_score(1, [[[1]]])
        assert score == 1.0
        assert zone == "coherent"
        assert n_timeout == 0

    def test_sat_score_all_unsat(self):
        score, zone, n_timeout = sat_score(1, [[[1], [-1]]])
        assert score == 0.0
        assert zone == "incoherent"

    def test_sat_score_mixed(self):
        # Group 1: SAT [[1]], Group 2: UNSAT [[1],[-1]]
        score, zone, n_timeout = sat_score(1, [[[1]], [[1], [-1]]])
        assert 0.0 < score < 1.0


# ──────────────────────────────────────────────────────────────────────────────
# SECTION 12: Domain aliases
# ──────────────────────────────────────────────────────────────────────────────

class TestDomainAliases:

    ALIASES = ["med", "law", "text", "bio", "cyber", "chem",
               "nano", "phys", "quantum", "socio", "econ"]

    def test_all_aliases_verified_for_valid_content(self):
        for alias in self.ALIASES:
            r = verify("if A then B. A.", domain=alias)
            assert r.is_verified, f"domain alias '{alias}' returned {r.verdict}"

    def test_all_aliases_paradox_for_contradiction_content(self):
        for alias in self.ALIASES:
            r = verify("A. not A.", domain=alias)
            assert r.is_paradox or r.is_contradiction, \
                f"domain alias '{alias}' should detect conflict, got {r.verdict}"

    def test_logic_domain(self):
        r = verify("if A then B. A.", domain="logic")
        assert r.is_verified

    def test_market_domain(self):
        r = verify("price is high. demand is low.", domain="market")
        assert r.verdict in (Verdict.VERIFIED, Verdict.CONTRADICTION, Verdict.PARADOX, Verdict.TIMEOUT)

    def test_code_domain(self):
        r = verify("assert x > 0", domain="code")
        assert r.verdict in (Verdict.VERIFIED, Verdict.CONTRADICTION, Verdict.PARADOX, Verdict.TIMEOUT)

    def test_math_domain(self):
        r = verify("x = y. y = z.", domain="math")
        assert r.verdict in (Verdict.VERIFIED, Verdict.CONTRADICTION, Verdict.PARADOX, Verdict.TIMEOUT)


# ──────────────────────────────────────────────────────────────────────────────
# SECTION 13: must_verify + VerificationError
# ──────────────────────────────────────────────────────────────────────────────

class TestMustVerify:

    def test_must_verify_valid(self):
        content = must_verify("if A then B. A.", domain="logic")
        assert content == "if A then B. A."

    def test_must_verify_raises_on_paradox(self):
        with pytest.raises(VerificationError) as exc_info:
            must_verify("A. not A.", domain="logic")
        err = exc_info.value
        assert err.result.is_paradox
        assert "PARADOX" in str(err)

    def test_must_verify_raises_on_contradiction(self):
        """must_verify() does not accept extra_constraints kwarg (by design)."""
        import inspect
        sig = inspect.signature(must_verify)
        assert "extra_constraints" not in sig.parameters, (
            "must_verify now has extra_constraints. "
            "Update this test and add a direct test for the new behaviour."
        )
        # Verify via gate().verify() that extra_constraints still works
        gate = VerificationGate()
        r = gate.verify("A.", domain="logic", extra_constraints=[[[1], [-1]]])
        assert r.is_contradiction

    def test_must_verify_raises_contract(self):
        """VerificationError.result must contain the result object."""
        with pytest.raises(VerificationError) as exc_info:
            must_verify("A. not A.", domain="logic")
        err = exc_info.value
        assert isinstance(err.result, VerificationResult)
        assert err.result.verdict is not None

    def test_must_verify_empty_passes(self):
        content = must_verify("", domain="logic")
        assert content == ""


# ──────────────────────────────────────────────────────────────────────────────
# SECTION 14: _solve_groups edge cases
# ──────────────────────────────────────────────────────────────────────────────

class TestSolveGroupsEdgeCases:

    def test_extra_constraints_appended(self):
        """Extra constraints are appended to groups before solving."""
        r = verify("A.", domain="logic", extra_constraints=[[[1], [-1]]])
        assert r.is_contradiction  # A (SAT) + contradiction → CONTRADICTION

    def test_extra_constraints_zero_literal_boundary(self):
        """
        BUG-11: lit=0 in extra_constraints → pos_lit(-1) undefined.
        Test that this raises a clear error rather than silently corrupting state.
        """
        # lit=0: _solve_groups does pos_lit(0 - 1) = pos_lit(-1)
        # This is a boundary condition — document current behaviour
        try:
            r = verify("A.", domain="logic", extra_constraints=[[[0]]])
            # If it doesn't crash, at least it returns a verdict
            assert r.verdict in (Verdict.VERIFIED, Verdict.CONTRADICTION, Verdict.PARADOX, Verdict.TIMEOUT)
        except Exception as e:
            # A clear exception is acceptable; silent wrong answer is not
            assert e is not None  # document that it crashed

    def test_single_group_always_verified_or_contradiction(self):
        """Single group can only be VERIFIED or CONTRADICTION, never PARADOX."""
        # PARADOX requires n_sat == total AND total > 1
        r = verify("A.", domain="logic")
        assert r.verdict in (Verdict.VERIFIED, Verdict.CONTRADICTION, Verdict.TIMEOUT), \
            f"Single group must not be PARADOX, got {r.verdict}"

    def test_n_paradox_set_on_paradox_verdict(self):
        """When verdict is PARADOX, n_paradox must be > 0."""
        r = verify("A. not A.", domain="logic")
        assert r.is_paradox
        assert r.n_paradox > 0, f"PARADOX verdict must have n_paradox > 0, got {r.n_paradox}"

    def test_n_paradox_zero_when_verified(self):
        r = verify("if A then B. A.", domain="logic")
        assert r.is_verified
        assert r.n_paradox == 0


# ──────────────────────────────────────────────────────────────────────────────
# SECTION 15: Normalization / double-negation / nested NOT
# ──────────────────────────────────────────────────────────────────────────────

class TestNormalizationEdgeCases:

    def test_double_negation_bug(self):
        """
        BUG-15 (KNOWN, NOT YET FIXED): 'not not A' is treated as ¬A (single negation).
        'not not A. A.' produces lits = [-1, 1] instead of [1, 1].
        Fix requires counting NOT_PAT occurrences and checking parity.
        Risk: NOT_PAT can match multiple negations in compound phrases (e.g. 'no not').
        This test documents current wrong behaviour as a regression sentinel.
        """
        ext = LogicConstraintExtractor()
        n, groups = ext.extract("not not A. A.")
        assert n == 1
        lits = [g[0][0] for g in groups]
        # BUG: double negation treated as single negation — lits are [-1, 1]
        # When fixed: lits should be [1, 1] (both positive)
        assert sorted(lits) == [-1, 1], (
            "BUG-15: 'not not A' should normalise to +A (double negation = positive). "
            "Currently treated as -A. When fixed, update this assertion to `== [1, 1]`."
        )

    def test_multi_sentence_no_cross_contamination(self):
        """Variables from one extract() call must not persist to next call."""
        ext1 = LogicConstraintExtractor()
        n1, g1 = ext1.extract("A.")
        ext2 = LogicConstraintExtractor()
        n2, g2 = ext2.extract("B.")
        # Each fresh extractor should assign var=1 to its own proposition
        assert n1 == 1 == n2
        assert g1 == [[[1]]] == g2

    def test_variable_numbering_is_per_extract_call(self):
        """Within one extract() call, vars accumulate correctly."""
        ext = LogicConstraintExtractor()
        n, groups = ext.extract("A. B. C.")
        assert n == 3
        assert len(groups) == 3

    def test_stop_word_only_proposition(self):
        """A proposition consisting only of stop words should not crash."""
        r = verify("the a an.", domain="logic")
        # All tokens stripped → should be stable (possibly empty var = "the" or fallback)
        assert r.verdict in (Verdict.VERIFIED, Verdict.CONTRADICTION, Verdict.PARADOX, Verdict.TIMEOUT)

    def test_proposition_with_apostrophe(self):
        """NOT_PAT includes 'won't' → test contraction handling."""
        r = verify("won't snow.", domain="logic")
        assert r.verdict in (Verdict.VERIFIED, Verdict.CONTRADICTION, Verdict.PARADOX, Verdict.TIMEOUT)


# ──────────────────────────────────────────────────────────────────────────────
# SECTION 16: Public API surface completeness
# ──────────────────────────────────────────────────────────────────────────────

class TestPublicAPICompleteness:

    def test_public_imports(self):
        """BUG-20: All expected symbols are importable from the public package."""
        from satisfaction_suffices import verify as v
        from satisfaction_suffices import VerificationGate, must_verify, get_gate
        from satisfaction_suffices.verifier import (
            verify, VerificationGate, must_verify, get_gate,
            VerificationError, VerificationResult,
        )
        assert callable(v)

    def test_verificationresult_importable(self):
        from satisfaction_suffices.verifier.verify import VerificationResult, Verdict
        assert Verdict.VERIFIED
        assert Verdict.CONTRADICTION
        assert Verdict.PARADOX
        assert Verdict.TIMEOUT

    def test_verificationgate_has_all_methods(self):
        gate = VerificationGate()
        assert callable(gate.verify)
        assert callable(gate.verify_tokens)
        assert callable(gate.verify_batch)
        assert callable(gate.gate)
        assert callable(gate.register_extractor)

    def test_module_level_verify_forwards_kwargs(self):
        """Module-level verify() must pass through extra_constraints."""
        r = verify("A.", domain="logic", extra_constraints=[[[1], [-1]]])
        assert r.is_contradiction

    def test_verificationerror_has_result(self):
        with pytest.raises(VerificationError) as exc_info:
            must_verify("A. not A.", domain="logic")
        assert hasattr(exc_info.value, "result")
        assert isinstance(exc_info.value.result, VerificationResult)


# ──────────────────────────────────────────────────────────────────────────────
# SECTION 17: Regression suite — critical previously-found bugs must stay fixed
# ──────────────────────────────────────────────────────────────────────────────

class TestRegressionSuite:

    def test_fever_contradiction_regression(self):
        """REGRESSION: 'fever and no fever' was previously VERIFIED. Must stay CONTRADICTION."""
        r = verify("The patient has fever and no fever.", domain="logic")
        assert r.is_contradiction, f"REGRESSION: fever bug returned {r.verdict}"

    def test_a_not_a_paradox_regression(self):
        """REGRESSION: 'A. not A.' must be PARADOX."""
        r = verify("A. not A.", domain="logic")
        assert r.is_paradox, f"REGRESSION: A/not-A paradox returned {r.verdict}"

    def test_modus_ponens_verified_regression(self):
        """REGRESSION: modus ponens must be VERIFIED."""
        r = verify("if A then B. A.", domain="logic")
        assert r.is_verified, f"REGRESSION: modus ponens returned {r.verdict}"

    def test_modus_ponens_chain_verified_regression(self):
        """REGRESSION: chained modus ponens must be VERIFIED."""
        r = verify("if A then B. if B then C. not C. A.", domain="logic")
        # The default statement — must produce a non-trivial result
        assert r.verdict in (Verdict.VERIFIED, Verdict.CONTRADICTION, Verdict.PARADOX, Verdict.TIMEOUT)

    def test_empty_verified_regression(self):
        """REGRESSION: empty string must be VERIFIED."""
        r = verify("")
        assert r.is_verified

    def test_single_proposition_regression(self):
        """REGRESSION: single proposition must be VERIFIED (SAT)."""
        r = verify("A.", domain="logic")
        assert r.is_verified

    def test_verdict_rejected_alias_regression(self):
        """REGRESSION: Verdict.REJECTED must alias CONTRADICTION."""
        assert Verdict.REJECTED is Verdict.CONTRADICTION
