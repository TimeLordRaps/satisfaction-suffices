"""
Tests for meta-mirror degeneration detection — integration-level scenarios.

Exercises the degeneration pathway (MIRROR→PARADOX→TIMEOUT→SHADOW) under
realistic verification trace patterns: phase transition oscillation,
sustained cycling, degeneration dominance, convergence recovery, and
the 1:3 step-asymmetry property.
"""

from __future__ import annotations

import pytest

from satisfaction_suffices.logic.cycle_detector import (
    CYCLE_STATES,
    FIXED_POINTS,
    VERDICT_BITS,
    CycleAnalysis,
    MetaMirrorDetector,
    TransitionType,
    classify_transition,
    detect_cycle,
    flag_degeneration,
    measure_ratio,
)
from satisfaction_suffices.verifier.verify import Verdict

# Shorthand
S = Verdict.SHADOW_PARADOX    # 010
M = Verdict.MIRROR_PARADOX    # 011
P = Verdict.PARADOX           # 101
T = Verdict.TIMEOUT           # 110
V = Verdict.VERIFIED          # 111
X = Verdict.METAPARADOX       # 000
C = Verdict.CONTRADICTION     # 001
B = Verdict.BASE_FRAMES       # 100


# ═══════════════════════════════════════════════════════════════════
# Scenario: Phase Transition Oscillation
# Near the ~4.267 clause-to-variable ratio, the system oscillates
# between cycle states and fixed points.
# ═══════════════════════════════════════════════════════════════════

class TestPhaseTransitionOscillation:
    """Simulates a solver operating near the SAT/UNSAT phase transition."""

    def test_oscillation_pattern(self) -> None:
        """System enters cycle, exits to VERIFIED, re-enters."""
        trace = [
            V, V, S, M, P, T, S,   # enters cycle from VERIFIED
            V, V,                    # escapes to VERIFIED
            S, M, P, T, S,          # re-enters
            V,                       # final escape
        ]
        result = detect_cycle(trace)
        assert result.is_cycling
        assert len(result.full_cycles) == 2
        assert result.convergence_count == 2
        assert result.degeneration_count == 2
        assert result.ratio == pytest.approx(1.0)

    def test_asymmetric_oscillation(self) -> None:
        """System converges frequently but degenerates rarely — stable mirror."""
        trace = [
            S, M, V,       # converge, escape
            S, M, V,       # converge, escape
            S, M, P, T, S, # converge + degenerate once
        ]
        result = detect_cycle(trace)
        assert result.convergence_count == 3
        assert result.degeneration_count == 1
        assert result.ratio == pytest.approx(3.0)
        assert not result.is_degeneration_dominant


# ═══════════════════════════════════════════════════════════════════
# Scenario: Sustained Cycling
# The system enters the 4-cycle and stays locked in it.
# ═══════════════════════════════════════════════════════════════════

class TestSustainedCycling:
    """Persistent cycling — the system cannot escape the 4-cycle."""

    def test_triple_cycle(self) -> None:
        trace = [S, M, P, T] * 3 + [S]
        result = detect_cycle(trace)
        assert len(result.full_cycles) == 3
        assert result.cycle_fraction == 1.0

    def test_long_sustained_cycle(self) -> None:
        """10 consecutive cycles — system is locked."""
        n_cycles = 10
        trace = [S, M, P, T] * n_cycles + [S]
        result = detect_cycle(trace)
        assert len(result.full_cycles) == n_cycles
        assert result.convergence_count == n_cycles
        assert result.degeneration_count == n_cycles
        assert result.ratio == pytest.approx(1.0)
        assert result.cycle_fraction == 1.0


# ═══════════════════════════════════════════════════════════════════
# Scenario: Degeneration Dominance
# Degeneration events outnumber convergence — mirror instability.
# ═══════════════════════════════════════════════════════════════════

class TestDegenerationDominance:
    """When degeneration outpaces convergence, the mirror is unstable."""

    def test_degeneration_without_convergence(self) -> None:
        """System starts at MIRROR (injected) and immediately degenerates."""
        trace = [M, P, T, S, M, P, T, S]
        result = detect_cycle(trace)
        # No SHADOW→MIRROR convergence (starts at M), but M appears at idx 4
        # after S at idx 3 — that IS a convergence: (3, 4)
        assert result.convergence_count == 1
        assert result.degeneration_count == 2
        assert result.is_degeneration_dominant

    def test_pure_degeneration_no_convergence(self) -> None:
        """Only the degeneration path, no convergence at all."""
        trace = [M, P, T, S]
        result = detect_cycle(trace)
        assert result.convergence_count == 0
        assert result.degeneration_count == 1
        assert result.ratio == pytest.approx(0.0)  # 0 convergence / 1 degeneration
        assert result.is_degeneration_dominant

    def test_flag_triggers(self) -> None:
        trace = [M, P, T, S, M, P, T, S]
        assert flag_degeneration(trace, threshold=1)
        assert flag_degeneration(trace, threshold=2)


# ═══════════════════════════════════════════════════════════════════
# Scenario: Convergence Recovery
# System converges (SHADOW→MIRROR) and the mirror holds — no degeneration.
# ═══════════════════════════════════════════════════════════════════

class TestConvergenceRecovery:
    """Mirror stabilizes: convergence without subsequent degeneration."""

    def test_stable_mirror(self) -> None:
        """SHADOW→MIRROR→VERIFIED: mirror holds, promotes to verified."""
        trace = [S, M, V, V, V]
        result = detect_cycle(trace)
        assert result.convergence_count == 1
        assert result.degeneration_count == 0
        assert not result.is_cycling
        assert result.ratio is None

    def test_multiple_stable_convergences(self) -> None:
        trace = [S, M, V, S, M, V, S, M, V]
        result = detect_cycle(trace)
        assert result.convergence_count == 3
        assert result.degeneration_count == 0
        assert not result.is_degeneration_dominant


# ═══════════════════════════════════════════════════════════════════
# Scenario: 1:3 Step Asymmetry
# The convergence path is 1 step, degeneration is 3 steps.
# Each full cycle therefore has 4 transitions total.
# ═══════════════════════════════════════════════════════════════════

class TestStepAsymmetry:
    """Verify the structural 1:3 convergence:degeneration step ratio."""

    def test_single_cycle_step_count(self) -> None:
        """A single cycle: 1 convergence transition + 3 degeneration transitions."""
        trace = [S, M, P, T, S]
        transitions = []
        for i in range(len(trace) - 1):
            transitions.append(classify_transition(trace[i], trace[i + 1]))

        convergence_steps = sum(
            1 for t in transitions if t == TransitionType.CONVERGENCE
        )
        degeneration_steps = sum(
            1 for t in transitions
            if t in (TransitionType.DEGENERATION_STEP_1,
                     TransitionType.DEGENERATION_STEP_2,
                     TransitionType.DEGENERATION_STEP_3)
        )
        assert convergence_steps == 1
        assert degeneration_steps == 3
        assert degeneration_steps / convergence_steps == 3.0

    def test_n_cycles_step_ratio(self) -> None:
        """N cycles always have N convergence steps and 3N degeneration steps."""
        for n in [1, 5, 10, 50]:
            trace = [S, M, P, T] * n + [S]
            transitions = []
            for i in range(len(trace) - 1):
                transitions.append(classify_transition(trace[i], trace[i + 1]))
            conv = sum(1 for t in transitions if t == TransitionType.CONVERGENCE)
            degen = sum(
                1 for t in transitions
                if t in (TransitionType.DEGENERATION_STEP_1,
                         TransitionType.DEGENERATION_STEP_2,
                         TransitionType.DEGENERATION_STEP_3)
            )
            assert conv == n
            assert degen == 3 * n


# ═══════════════════════════════════════════════════════════════════
# Scenario: Mixed Traces with All Eight Verdicts
# ═══════════════════════════════════════════════════════════════════

class TestMixedTraces:
    """Traces that include all eight verdict types."""

    def test_all_verdicts_present(self) -> None:
        trace = [V, C, B, X, S, M, P, T, S, V]
        result = detect_cycle(trace)
        assert result.is_cycling
        assert result.time_in_cycle == 5  # S, M, P, T, S
        assert result.time_in_fixed == 5  # V, C, B, X, V

    def test_fixed_points_dont_break_cycle_count(self) -> None:
        """Fixed-point verdicts between cycle states don't affect strict detection."""
        trace_with = [V, S, M, P, T, S, V]
        trace_without = [S, M, P, T, S]
        r1 = detect_cycle(trace_with)
        r2 = detect_cycle(trace_without)
        assert r1.is_cycling == r2.is_cycling
        assert len(r1.full_cycles) == len(r2.full_cycles)


# ═══════════════════════════════════════════════════════════════════
# Scenario: Loose Mode Integration
# ═══════════════════════════════════════════════════════════════════

class TestLooseModeIntegration:
    """Loose mode detects cycles through intervening fixed-point noise."""

    def test_noisy_cycle(self) -> None:
        """Cycle with VERIFIED noise between every transition."""
        trace = [S, V, M, V, P, V, T, V, S]
        result = detect_cycle(trace, strict=False)
        assert result.is_cycling
        assert result.convergence_count == 1
        assert result.degeneration_count == 1

    def test_heavily_noisy_cycle(self) -> None:
        """Lots of fixed-point noise, but underlying cycle is present."""
        trace = [
            S, V, V, V,
            M, C, C,
            P, B, B, B, B,
            T, X,
            S,
        ]
        result = detect_cycle(trace, strict=False)
        assert result.is_cycling
        assert len(result.full_cycles) == 1
        # Original indices preserved:
        cyc = result.full_cycles[0]
        assert cyc.start == 0   # S at 0
        assert cyc.end == 14    # S at 14

    def test_loose_degeneration_flagging(self) -> None:
        """flag_degeneration with loose mode catches noisy degeneration."""
        trace = [M, V, P, V, T, V, S]
        assert flag_degeneration(trace, strict=True) is False
        assert flag_degeneration(trace, strict=False) is True


# ═══════════════════════════════════════════════════════════════════
# Scenario: Edge Cases
# ═══════════════════════════════════════════════════════════════════

class TestEdgeCases:
    def test_repeated_same_verdict(self) -> None:
        """Repeated same verdict — no transitions detected."""
        trace = [S, S, S, S, S]
        result = detect_cycle(trace)
        assert result.convergence_count == 0
        assert result.degeneration_count == 0
        assert not result.is_cycling

    def test_reverse_cycle_not_detected(self) -> None:
        """The reverse direction (S→T→P→M→S) is NOT the canonical cycle."""
        trace = [S, T, P, M, S]
        result = detect_cycle(trace)
        assert not result.is_cycling
        assert result.degeneration_count == 0
        assert result.convergence_count == 0

    def test_overlapping_cycles_share_shadow(self) -> None:
        """Consecutive cycles share the closing/opening SHADOW."""
        trace = [S, M, P, T, S, M, P, T, S]
        result = detect_cycle(trace)
        assert len(result.full_cycles) == 2
        # First cycle ends at idx 4, second starts at idx 4
        assert result.full_cycles[0].end == result.full_cycles[1].start

    def test_metaparadox_fixed_point(self) -> None:
        """METAPARADOX (000) is a fixed point — never part of a cycle."""
        trace = [X, X, X, X]
        result = detect_cycle(trace)
        assert result.time_in_fixed == 4
        assert result.time_in_cycle == 0
        assert not result.is_cycling
