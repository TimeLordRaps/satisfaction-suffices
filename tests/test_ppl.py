"""
Tests for satisfaction_suffices.logic.ppl — Pigeonhole Paradox Logic.

Covers: ContradictionLevel, AttractorState, Contradiction, ParadoxAnalysis,
ContradictionDetector, ParadoxScorer, pigeonhole_cnf, test_paradox_hardness,
MetaParadox, MORAL_AXIOMS, analyze_paradox, detect_contradictions.
"""

from __future__ import annotations

import pytest

from satisfaction_suffices.logic.ppl import (
    MORAL_AXIOMS,
    AttractorState,
    Contradiction,
    ContradictionDetector,
    ContradictionLevel,
    MetaParadox,
    ParadoxAnalysis,
    ParadoxScorer,
    analyze_paradox,
    detect_contradictions,
    get_scorer,
    pigeonhole_cnf,
    test_paradox_hardness as _bench_paradox_hardness,
)
from satisfaction_suffices.verifier.verify import Verdict


# ═══════════════════════════════════════════════════════════════════
# ContradictionLevel / AttractorState / Contradiction dataclass
# ═══════════════════════════════════════════════════════════════════

class TestContradictionLevel:
    def test_surface_resolvable(self) -> None:
        c = Contradiction(
            level=ContradictionLevel.SURFACE,
            description="test",
            clause_indices=[0, 1],
        )
        assert c.is_resolvable is True
        assert c.is_paradox is False

    def test_structural_resolvable(self) -> None:
        c = Contradiction(
            level=ContradictionLevel.STRUCTURAL,
            description="test",
            clause_indices=[0, 1, 2],
        )
        assert c.is_resolvable is True

    def test_deep_is_paradox(self) -> None:
        c = Contradiction(
            level=ContradictionLevel.DEEP,
            description="test",
            clause_indices=[0],
        )
        assert c.is_paradox is True
        assert c.is_resolvable is False

    def test_none_not_paradox(self) -> None:
        c = Contradiction(
            level=ContradictionLevel.NONE,
            description="none",
            clause_indices=[],
        )
        assert c.is_resolvable is False
        assert c.is_paradox is False


class TestMetaParadox:
    def test_all_five_exist(self) -> None:
        assert len(MetaParadox) == 5
        assert MetaParadox.CONTAINER_GENERATION is not None
        assert MetaParadox.LEVEL_TRANSCENDENCE is not None
        assert MetaParadox.SELF_MODIFICATION is not None
        assert MetaParadox.INFINITE_OVERFLOW is not None
        assert MetaParadox.FOUNDATION_BOOTSTRAP is not None


class TestMoralAxioms:
    def test_all_axioms_present(self) -> None:
        assert "innocence" in MORAL_AXIOMS
        assert "imagination" in MORAL_AXIOMS
        assert "irreversibility" in MORAL_AXIOMS
        assert "children_as_value" in MORAL_AXIOMS
        assert len(MORAL_AXIOMS) == 4


# ═══════════════════════════════════════════════════════════════════
# ParadoxAnalysis
# ═══════════════════════════════════════════════════════════════════

class TestParadoxAnalysis:
    def test_no_contradictions(self) -> None:
        from satisfaction_suffices.verifier.verify import get_gate
        gate = get_gate()
        result = gate.verify("if A then B. A.", domain="logic")
        pa = ParadoxAnalysis(
            contradictions=[],
            tolerance_score=0.0,
            attractor_state=AttractorState.STABLE,
            verification=result,
            suggested_strategy="none",
        )
        assert pa.has_paradox is False
        assert pa.resolvable_count == 0
        assert pa.deep_count == 0

    def test_has_deep_paradox(self) -> None:
        from satisfaction_suffices.verifier.verify import get_gate
        gate = get_gate()
        result = gate.verify("A. not A.", domain="logic")
        deep = Contradiction(
            level=ContradictionLevel.DEEP,
            description="deep",
            clause_indices=[0, 1],
        )
        surface = Contradiction(
            level=ContradictionLevel.SURFACE,
            description="surface",
            clause_indices=[2, 3],
        )
        pa = ParadoxAnalysis(
            contradictions=[deep, surface],
            tolerance_score=0.6,
            attractor_state=AttractorState.FIXED_POINT,
            verification=result,
            suggested_strategy="axiom_introduction",
        )
        assert pa.has_paradox is True
        assert pa.deep_count == 1
        assert pa.resolvable_count == 1


# ═══════════════════════════════════════════════════════════════════
# pigeonhole_cnf
# ═══════════════════════════════════════════════════════════════════

class TestPigeonholeCNF:
    def test_php_3_2_is_unsat(self) -> None:
        from satisfaction_suffices.verifier.sat import solve_cnf
        n_vars, clauses = pigeonhole_cnf(3, 2)
        assert n_vars == 6  # 3 pigeons * 2 holes
        sat, _ = solve_cnf(n_vars, clauses, budget=5000)
        assert sat is False

    def test_php_2_2_is_sat(self) -> None:
        from satisfaction_suffices.verifier.sat import solve_cnf
        n_vars, clauses = pigeonhole_cnf(2, 2)
        assert n_vars == 4
        sat, _ = solve_cnf(n_vars, clauses, budget=5000)
        assert sat is True

    def test_php_2_3_is_sat(self) -> None:
        from satisfaction_suffices.verifier.sat import solve_cnf
        n_vars, clauses = pigeonhole_cnf(2, 3)
        sat, _ = solve_cnf(n_vars, clauses, budget=5000)
        assert sat is True

    def test_clause_structure(self) -> None:
        n_vars, clauses = pigeonhole_cnf(3, 2)
        # 3 "at least one hole" clauses + exclusion clauses
        at_least = [c for c in clauses if all(lit > 0 for lit in c)]
        assert len(at_least) == 3  # one per pigeon
        exclusion = [c for c in clauses if any(lit < 0 for lit in c)]
        assert len(exclusion) > 0


class TestParadoxHardness:
    def test_basic_run(self) -> None:
        result = _bench_paradox_hardness(n=3, budget=5000)
        assert result["n_pigeons"] == 4
        assert result["n_holes"] == 3
        assert result["expected_unsat"] is True
        assert result["is_correct"] is True
        assert result["satisfiable"] is False
        assert result["elapsed_ms"] >= 0
# ═══════════════════════════════════════════════════════════════════
# ContradictionDetector
# ═══════════════════════════════════════════════════════════════════

class TestContradictionDetector:
    def test_no_contradiction(self) -> None:
        detector = ContradictionDetector()
        results = detector.detect("if A then B. A.")
        assert results == []

    def test_surface_contradiction(self) -> None:
        detector = ContradictionDetector()
        results = detector.detect("A. not A.")
        assert len(results) >= 1
        assert results[0].level in (
            ContradictionLevel.SURFACE,
            ContradictionLevel.STRUCTURAL,
        )

    def test_empty_text(self) -> None:
        detector = ContradictionDetector()
        results = detector.detect("")
        assert results == []

    def test_moral_domain_deep(self) -> None:
        detector = ContradictionDetector()
        results = detector.detect(
            "The child was helped. The child was harmed. "
            "Both statements are simultaneously true."
        )
        # If a contradiction is found involving child-related text, it should be DEEP
        for r in results:
            if r.level != ContradictionLevel.NONE:
                assert r.level == ContradictionLevel.DEEP

    def test_self_referential_deep(self) -> None:
        detector = ContradictionDetector()
        results = detector.detect(
            "This statement is false. This statement is true. "
            "Both refer to itself."
        )
        for r in results:
            if r.level != ContradictionLevel.NONE:
                assert r.level == ContradictionLevel.DEEP


# ═══════════════════════════════════════════════════════════════════
# ParadoxScorer
# ═══════════════════════════════════════════════════════════════════

class TestParadoxScorer:
    def test_consistent_text(self) -> None:
        scorer = ParadoxScorer()
        pa = scorer.score("if A then B. A.")
        assert pa.tolerance_score == 0.0
        assert pa.attractor_state == AttractorState.STABLE
        assert pa.suggested_strategy == "none"
        assert pa.contradictions == []

    def test_contradictory_text(self) -> None:
        scorer = ParadoxScorer()
        pa = scorer.score("A. not A.")
        assert pa.tolerance_score > 0.0
        assert len(pa.contradictions) >= 1

    def test_deep_paradox_fixed_point(self) -> None:
        scorer = ParadoxScorer()
        pa = scorer.score(
            "This statement is a paradox. This statement is false. "
            "This statement refers to itself."
        )
        if pa.contradictions:
            if any(c.level == ContradictionLevel.DEEP for c in pa.contradictions):
                assert pa.attractor_state == AttractorState.FIXED_POINT


# ═══════════════════════════════════════════════════════════════════
# Convenience functions
# ═══════════════════════════════════════════════════════════════════

class TestConvenienceFunctions:
    def test_get_scorer_singleton(self) -> None:
        s1 = get_scorer()
        s2 = get_scorer()
        assert s1 is s2

    def test_analyze_paradox_consistent(self) -> None:
        pa = analyze_paradox("if A then B. A.")
        assert pa.tolerance_score == 0.0

    def test_analyze_paradox_contradiction(self) -> None:
        pa = analyze_paradox("A. not A.")
        assert pa.tolerance_score > 0.0

    def test_detect_contradictions_clean(self) -> None:
        results = detect_contradictions("if A then B. A.")
        assert results == []

    def test_detect_contradictions_found(self) -> None:
        results = detect_contradictions("A. not A.")
        assert len(results) >= 1
