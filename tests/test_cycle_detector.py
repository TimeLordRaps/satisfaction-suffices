"""
Tests for satisfaction_suffices.logic.cycle_detector — Meta-Mirror 4-Cycle Detection.

Covers: VERDICT_BITS, CYCLE_STATES, FIXED_POINTS, classify_transition,
MetaMirrorDetector (strict + loose), detect_cycle, flag_degeneration,
measure_ratio, CycleAnalysis properties, CycleOccurrence.
"""

from __future__ import annotations

import pytest

from satisfaction_suffices.logic.cycle_detector import (
    CYCLE_STATES,
    FIXED_POINTS,
    VERDICT_BITS,
    CycleAnalysis,
    CycleOccurrence,
    MetaMirrorDetector,
    TransitionType,
    classify_transition,
    detect_cycle,
    flag_degeneration,
    measure_ratio,
)
from satisfaction_suffices.verifier.verify import Verdict

# Shorthand aliases for readability
S = Verdict.SHADOW_PARADOX    # 010
M = Verdict.MIRROR_PARADOX    # 011
P = Verdict.PARADOX           # 101
T = Verdict.TIMEOUT           # 110
V = Verdict.VERIFIED          # 111
X = Verdict.METAPARADOX       # 000
C = Verdict.CONTRADICTION     # 001
B = Verdict.BASE_FRAMES       # 100


# ═══════════════════════════════════════════════════════════════════
# Bit Encoding
# ═══════════════════════════════════════════════════════════════════

class TestVerdictBits:
    def test_all_verdicts_have_bits(self) -> None:
        for v in Verdict:
            if v.name == "REJECTED":
                continue  # back-compat alias
            assert v in VERDICT_BITS, f"{v} missing from VERDICT_BITS"

    def test_bit_values(self) -> None:
        assert VERDICT_BITS[Verdict.METAPARADOX] == 0b000
        assert VERDICT_BITS[Verdict.CONTRADICTION] == 0b001
        assert VERDICT_BITS[Verdict.SHADOW_PARADOX] == 0b010
        assert VERDICT_BITS[Verdict.MIRROR_PARADOX] == 0b011
        assert VERDICT_BITS[Verdict.BASE_FRAMES] == 0b100
        assert VERDICT_BITS[Verdict.PARADOX] == 0b101
        assert VERDICT_BITS[Verdict.TIMEOUT] == 0b110
        assert VERDICT_BITS[Verdict.VERIFIED] == 0b111

    def test_duality_pairs_are_complements(self) -> None:
        pairs = [
            (Verdict.VERIFIED, Verdict.METAPARADOX),
            (Verdict.PARADOX, Verdict.SHADOW_PARADOX),
            (Verdict.TIMEOUT, Verdict.CONTRADICTION),
            (Verdict.BASE_FRAMES, Verdict.MIRROR_PARADOX),
        ]
        for a, b in pairs:
            assert VERDICT_BITS[a] ^ VERDICT_BITS[b] == 0b111

    def test_xor_algebra_mirror_paradox_timeout(self) -> None:
        """MIRROR ⊕ PARADOX = 011 ⊕ 101 = 110 = TIMEOUT."""
        assert (VERDICT_BITS[M] ^ VERDICT_BITS[P]) == VERDICT_BITS[T]


# ═══════════════════════════════════════════════════════════════════
# Cycle States & Fixed Points
# ═══════════════════════════════════════════════════════════════════

class TestCycleStructure:
    def test_cycle_states_are_four(self) -> None:
        assert len(CYCLE_STATES) == 4
        assert set(CYCLE_STATES) == {S, M, P, T}

    def test_fixed_points_are_four(self) -> None:
        assert len(FIXED_POINTS) == 4
        assert FIXED_POINTS == frozenset({V, X, C, B})

    def test_cycle_and_fixed_disjoint(self) -> None:
        assert set(CYCLE_STATES) & FIXED_POINTS == set()

    def test_cycle_plus_fixed_is_all_verdicts(self) -> None:
        all_v = {v for v in Verdict if v.name != "REJECTED"}
        assert set(CYCLE_STATES) | FIXED_POINTS == all_v


# ═══════════════════════════════════════════════════════════════════
# Transition Classification
# ═══════════════════════════════════════════════════════════════════

class TestClassifyTransition:
    def test_convergence(self) -> None:
        assert classify_transition(S, M) == TransitionType.CONVERGENCE

    def test_degeneration_steps(self) -> None:
        assert classify_transition(M, P) == TransitionType.DEGENERATION_STEP_1
        assert classify_transition(P, T) == TransitionType.DEGENERATION_STEP_2
        assert classify_transition(T, S) == TransitionType.DEGENERATION_STEP_3

    def test_fixed_point_transitions(self) -> None:
        assert classify_transition(V, S) == TransitionType.FIXED_POINT
        assert classify_transition(M, V) == TransitionType.FIXED_POINT
        assert classify_transition(X, C) == TransitionType.FIXED_POINT

    def test_other_transitions(self) -> None:
        assert classify_transition(S, P) == TransitionType.OTHER
        assert classify_transition(M, T) == TransitionType.OTHER
        assert classify_transition(P, M) == TransitionType.OTHER


# ═══════════════════════════════════════════════════════════════════
# Strict Detection — Empty / Trivial Traces
# ═══════════════════════════════════════════════════════════════════

class TestEmptyTraces:
    def test_empty_trace(self) -> None:
        result = detect_cycle([])
        assert result.trace_length == 0
        assert result.convergence_count == 0
        assert result.degeneration_count == 0
        assert not result.is_cycling
        assert result.ratio is None
        assert result.cycle_fraction == 0.0

    def test_single_verdict(self) -> None:
        result = detect_cycle([S])
        assert result.trace_length == 1
        assert result.convergence_count == 0
        assert not result.is_cycling
        assert result.time_in_cycle == 1
        assert result.time_in_fixed == 0

    def test_all_fixed_points(self) -> None:
        trace = [V, C, B, X, V, V]
        result = detect_cycle(trace)
        assert result.time_in_cycle == 0
        assert result.time_in_fixed == 6
        assert result.convergence_count == 0
        assert result.cycle_fraction == 0.0


# ═══════════════════════════════════════════════════════════════════
# Strict Detection — Convergence
# ═══════════════════════════════════════════════════════════════════

class TestConvergenceDetection:
    def test_single_convergence(self) -> None:
        trace = [V, S, M, V]
        result = detect_cycle(trace)
        assert result.convergence_count == 1
        assert result.convergence_events == [(1, 2)]

    def test_multiple_convergences(self) -> None:
        trace = [S, M, P, T, S, M]
        result = detect_cycle(trace)
        assert result.convergence_count == 2
        assert result.convergence_events == [(0, 1), (4, 5)]

    def test_no_convergence_shadow_alone(self) -> None:
        trace = [S, P, T, S]
        result = detect_cycle(trace)
        assert result.convergence_count == 0


# ═══════════════════════════════════════════════════════════════════
# Strict Detection — Degeneration
# ═══════════════════════════════════════════════════════════════════

class TestDegenerationDetection:
    def test_single_degeneration(self) -> None:
        trace = [M, P, T, S]
        result = detect_cycle(trace)
        assert result.degeneration_count == 1
        assert result.degeneration_events == [(0, 1, 2, 3)]

    def test_partial_degeneration_not_counted(self) -> None:
        """Incomplete degeneration (M→P→T but no S) should not count."""
        trace = [M, P, T, V]
        result = detect_cycle(trace)
        assert result.degeneration_count == 0

    def test_degeneration_requires_exact_order(self) -> None:
        """M→T→P→S is not a valid degeneration path."""
        trace = [M, T, P, S]
        result = detect_cycle(trace)
        assert result.degeneration_count == 0


# ═══════════════════════════════════════════════════════════════════
# Strict Detection — Full Cycles
# ═══════════════════════════════════════════════════════════════════

class TestFullCycleDetection:
    def test_single_full_cycle(self) -> None:
        trace = [S, M, P, T, S]
        result = detect_cycle(trace)
        assert result.is_cycling
        assert len(result.full_cycles) == 1
        cyc = result.full_cycles[0]
        assert cyc.start == 0
        assert cyc.end == 4
        assert cyc.convergence_idx == 0
        assert cyc.degen_start_idx == 1
        assert cyc.degen_mid_idx == 2
        assert cyc.degen_end_idx == 3

    def test_double_cycle(self) -> None:
        trace = [S, M, P, T, S, M, P, T, S]
        result = detect_cycle(trace)
        assert len(result.full_cycles) == 2
        assert result.full_cycles[0].start == 0
        assert result.full_cycles[0].end == 4
        assert result.full_cycles[1].start == 4
        assert result.full_cycles[1].end == 8

    def test_cycle_embedded_in_fixed_points(self) -> None:
        trace = [V, V, S, M, P, T, S, C, B]
        result = detect_cycle(trace)
        assert result.is_cycling
        assert len(result.full_cycles) == 1
        assert result.full_cycles[0].start == 2
        assert result.full_cycles[0].end == 6

    def test_no_cycle_without_closing_shadow(self) -> None:
        trace = [S, M, P, T, V]
        result = detect_cycle(trace)
        assert not result.is_cycling


# ═══════════════════════════════════════════════════════════════════
# CycleAnalysis Properties
# ═══════════════════════════════════════════════════════════════════

class TestCycleAnalysisProperties:
    def test_ratio_balanced(self) -> None:
        """One convergence + one degeneration → ratio 1.0."""
        trace = [S, M, P, T, S]
        result = detect_cycle(trace)
        assert result.ratio == pytest.approx(1.0)

    def test_ratio_convergence_heavy(self) -> None:
        """Two convergences + one degeneration → ratio 2.0."""
        trace = [S, M, V, S, M, P, T, S]
        result = detect_cycle(trace)
        assert result.convergence_count == 2
        assert result.degeneration_count == 1
        assert result.ratio == pytest.approx(2.0)

    def test_ratio_degeneration_heavy(self) -> None:
        """One convergence, two degenerations → ratio 0.5."""
        # Build: S→M (convergence), M→P→T→S (degen1), then M→P→T→S (degen2)
        # Need the second degen to start with M: inject M after first degen
        trace = [S, M, P, T, S, M, P, T, S]
        result = detect_cycle(trace)
        # convergence: (0,1) and (4,5) = 2
        # degeneration: (1,2,3,4) and (5,6,7,8) = 2
        assert result.ratio == pytest.approx(1.0)

    def test_ratio_none_without_degeneration(self) -> None:
        trace = [S, M, V, S, M, V]
        result = detect_cycle(trace)
        assert result.convergence_count == 2
        assert result.degeneration_count == 0
        assert result.ratio is None

    def test_cycle_fraction(self) -> None:
        trace = [V, S, M, P, T, S, V, V]
        result = detect_cycle(trace)
        # 5 cycle states (S, M, P, T, S), 3 fixed (V, V, V)
        assert result.cycle_fraction == pytest.approx(5 / 8)

    def test_is_degeneration_dominant_true(self) -> None:
        # One degeneration, zero convergence
        trace = [M, P, T, S]
        result = detect_cycle(trace)
        assert result.is_degeneration_dominant

    def test_is_degeneration_dominant_false(self) -> None:
        # One convergence, zero degeneration
        trace = [S, M, V]
        result = detect_cycle(trace)
        assert not result.is_degeneration_dominant


# ═══════════════════════════════════════════════════════════════════
# Loose Mode (non-strict)
# ═══════════════════════════════════════════════════════════════════

class TestLooseMode:
    def test_convergence_through_fixed_points(self) -> None:
        """SHADOW, then some fixed points, then MIRROR → detected in loose mode."""
        trace = [S, V, V, M]
        result = detect_cycle(trace, strict=False)
        assert result.convergence_count == 1
        # Original indices should be preserved
        assert result.convergence_events == [(0, 3)]

    def test_degeneration_through_fixed_points(self) -> None:
        """MIRROR→(fixed)→PARADOX→(fixed)→TIMEOUT→(fixed)→SHADOW in loose mode."""
        trace = [M, V, P, C, T, B, S]
        result = detect_cycle(trace, strict=False)
        assert result.degeneration_count == 1
        assert result.degeneration_events == [(0, 2, 4, 6)]

    def test_full_cycle_through_fixed_points(self) -> None:
        trace = [S, V, M, B, P, X, T, C, S]
        result = detect_cycle(trace, strict=False)
        assert result.is_cycling
        assert len(result.full_cycles) == 1
        cyc = result.full_cycles[0]
        assert cyc.start == 0
        assert cyc.end == 8

    def test_strict_misses_what_loose_finds(self) -> None:
        """Same trace: strict finds nothing, loose finds the cycle."""
        trace = [S, V, M, V, P, V, T, V, S]
        strict_result = detect_cycle(trace, strict=True)
        loose_result = detect_cycle(trace, strict=False)
        assert not strict_result.is_cycling
        assert loose_result.is_cycling


# ═══════════════════════════════════════════════════════════════════
# Convenience Functions
# ═══════════════════════════════════════════════════════════════════

class TestConvenienceFunctions:
    def test_flag_degeneration_true(self) -> None:
        trace = [M, P, T, S]
        assert flag_degeneration(trace) is True

    def test_flag_degeneration_false(self) -> None:
        trace = [S, M, V, V]
        assert flag_degeneration(trace) is False

    def test_flag_degeneration_threshold(self) -> None:
        trace = [M, P, T, S, M, P, T, S]
        assert flag_degeneration(trace, threshold=1) is True
        assert flag_degeneration(trace, threshold=2) is True
        assert flag_degeneration(trace, threshold=3) is False

    def test_measure_ratio(self) -> None:
        trace = [S, M, P, T, S]
        assert measure_ratio(trace) == pytest.approx(1.0)

    def test_measure_ratio_none(self) -> None:
        trace = [V, V, V]
        assert measure_ratio(trace) is None
