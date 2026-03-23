"""
Meta-Mirror 4-Cycle Detector
================================
Detects the SHADOW→MIRROR→PARADOX→TIMEOUT→SHADOW cycle in verdict traces
and measures the convergence:degeneration ratio.

The 4-cycle in the eight-state verdict lattice:

    SHADOW(010) →[convergence]→ MIRROR(011) →[degeneration]→ PARADOX(101)
        ↑                                                        ↓
        └──────────[paradoxically]── TIMEOUT(110) ←──────────────┘

Convergence (short path): SHADOW → MIRROR  (1 step, meta-paradox driven)
Degeneration (long path): MIRROR → PARADOX → TIMEOUT → SHADOW  (3 steps)

Four fixed points outside the cycle:
    VERIFIED(111), METAPARADOX(000), CONTRADICTION(001), BASE_FRAMES(100)

XOR algebra: MIRROR ⊕ PARADOX = 011 ⊕ 101 = 110 = TIMEOUT
The intermediate is the XOR of the endpoints.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Optional, Sequence, Tuple

from ..verifier.verify import Verdict


# ── Bit encoding for the lattice ──────────────────────────────────────────────

VERDICT_BITS: dict[Verdict, int] = {
    Verdict.METAPARADOX:    0b000,
    Verdict.CONTRADICTION:  0b001,
    Verdict.SHADOW_PARADOX: 0b010,
    Verdict.MIRROR_PARADOX: 0b011,
    Verdict.BASE_FRAMES:    0b100,
    Verdict.PARADOX:        0b101,
    Verdict.TIMEOUT:        0b110,
    Verdict.VERIFIED:       0b111,
}

# The four cycle states in order
CYCLE_STATES: tuple[Verdict, ...] = (
    Verdict.SHADOW_PARADOX,   # 010
    Verdict.MIRROR_PARADOX,   # 011
    Verdict.PARADOX,          # 101
    Verdict.TIMEOUT,          # 110
)

# The four fixed points (outside the cycle)
FIXED_POINTS: frozenset[Verdict] = frozenset({
    Verdict.VERIFIED,       # 111
    Verdict.METAPARADOX,    # 000
    Verdict.CONTRADICTION,  # 001
    Verdict.BASE_FRAMES,    # 100
})

_CYCLE_SET: frozenset[Verdict] = frozenset(CYCLE_STATES)


class TransitionType(Enum):
    """Classification of a verdict-to-verdict transition."""
    CONVERGENCE = auto()        # SHADOW → MIRROR (1 step)
    DEGENERATION_STEP_1 = auto()  # MIRROR → PARADOX
    DEGENERATION_STEP_2 = auto()  # PARADOX → TIMEOUT
    DEGENERATION_STEP_3 = auto()  # TIMEOUT → SHADOW
    FIXED_POINT = auto()        # transition to/from a fixed point
    OTHER = auto()              # any other transition


# Transition classification table
_TRANSITION_MAP: dict[tuple[Verdict, Verdict], TransitionType] = {
    (Verdict.SHADOW_PARADOX, Verdict.MIRROR_PARADOX): TransitionType.CONVERGENCE,
    (Verdict.MIRROR_PARADOX, Verdict.PARADOX): TransitionType.DEGENERATION_STEP_1,
    (Verdict.PARADOX, Verdict.TIMEOUT): TransitionType.DEGENERATION_STEP_2,
    (Verdict.TIMEOUT, Verdict.SHADOW_PARADOX): TransitionType.DEGENERATION_STEP_3,
}


def classify_transition(src: Verdict, dst: Verdict) -> TransitionType:
    """Classify a single verdict transition."""
    mapped = _TRANSITION_MAP.get((src, dst))
    if mapped is not None:
        return mapped
    if src in FIXED_POINTS or dst in FIXED_POINTS:
        return TransitionType.FIXED_POINT
    return TransitionType.OTHER


@dataclass(frozen=True)
class CycleOccurrence:
    """A single complete 4-cycle found in a verdict trace.

    The cycle is SHADOW→MIRROR→PARADOX→TIMEOUT→SHADOW (5 positions, 4 transitions).
    ``start`` is the index of the first SHADOW, ``end`` is the index of the
    closing SHADOW.
    """
    start: int
    end: int
    convergence_idx: int   # index of the SHADOW→MIRROR transition
    degen_start_idx: int   # index of the MIRROR→PARADOX transition
    degen_mid_idx: int     # index of the PARADOX→TIMEOUT transition
    degen_end_idx: int     # index of the TIMEOUT→SHADOW transition


@dataclass
class CycleAnalysis:
    """Full analysis of a verdict trace for meta-mirror dynamics."""
    trace_length: int
    convergence_events: List[Tuple[int, int]]   # (src_idx, dst_idx) pairs
    degeneration_events: List[Tuple[int, int, int, int]]  # (mirror_idx, paradox_idx, timeout_idx, shadow_idx)
    full_cycles: List[CycleOccurrence]
    time_in_cycle: int        # number of verdicts that are cycle states
    time_in_fixed: int        # number of verdicts that are fixed points

    @property
    def convergence_count(self) -> int:
        return len(self.convergence_events)

    @property
    def degeneration_count(self) -> int:
        return len(self.degeneration_events)

    @property
    def ratio(self) -> Optional[float]:
        """Convergence:degeneration ratio.

        Returns None if no degeneration events. A healthy system should
        show ratio ≈ 1.0 (one convergence per degeneration). The theoretical
        time-asymmetry is 1:3 (1 convergence step vs 3 degeneration steps),
        but the *event* ratio can differ from the *step* ratio.
        """
        if self.degeneration_count == 0:
            return None
        return self.convergence_count / self.degeneration_count

    @property
    def cycle_fraction(self) -> float:
        """Fraction of the trace spent in cycle states (vs fixed points)."""
        if self.trace_length == 0:
            return 0.0
        return self.time_in_cycle / self.trace_length

    @property
    def is_cycling(self) -> bool:
        """True if at least one complete 4-cycle was detected."""
        return len(self.full_cycles) > 0

    @property
    def is_degeneration_dominant(self) -> bool:
        """True if degeneration events outnumber convergence events."""
        return self.degeneration_count > self.convergence_count


class MetaMirrorDetector:
    """Detects the meta-mirror 4-cycle in verdict traces.

    Two modes:
        strict=True  (default): transitions must be consecutive in the trace
        strict=False : cycle states may be separated by fixed-point verdicts
    """

    def __init__(self, *, strict: bool = True) -> None:
        self._strict = strict

    def classify(self, trace: Sequence[Verdict]) -> CycleAnalysis:
        """Analyze a full verdict trace for meta-mirror dynamics."""
        convergence_events: list[tuple[int, int]] = []
        degeneration_events: list[tuple[int, int, int, int]] = []
        full_cycles: list[CycleOccurrence] = []
        time_in_cycle = sum(1 for v in trace if v in _CYCLE_SET)
        time_in_fixed = sum(1 for v in trace if v in FIXED_POINTS)

        if self._strict:
            convergence_events = self._find_convergence_strict(trace)
            degeneration_events = self._find_degeneration_strict(trace)
            full_cycles = self._find_full_cycles_strict(trace)
        else:
            filtered = self._filter_to_cycle_states(trace)
            convergence_events = self._find_convergence_strict(
                [v for _, v in filtered],
                offset_map=[i for i, _ in filtered],
            )
            degeneration_events = self._find_degeneration_strict(
                [v for _, v in filtered],
                offset_map=[i for i, _ in filtered],
            )
            full_cycles = self._find_full_cycles_strict(
                [v for _, v in filtered],
                offset_map=[i for i, _ in filtered],
            )

        return CycleAnalysis(
            trace_length=len(trace),
            convergence_events=convergence_events,
            degeneration_events=degeneration_events,
            full_cycles=full_cycles,
            time_in_cycle=time_in_cycle,
            time_in_fixed=time_in_fixed,
        )

    # ── Strict detection (consecutive transitions) ────────────────────────

    @staticmethod
    def _find_convergence_strict(
        trace: Sequence[Verdict],
        *,
        offset_map: Optional[list[int]] = None,
    ) -> list[tuple[int, int]]:
        """Find all SHADOW→MIRROR convergence transitions."""
        results: list[tuple[int, int]] = []
        for i in range(len(trace) - 1):
            if (trace[i] == Verdict.SHADOW_PARADOX
                    and trace[i + 1] == Verdict.MIRROR_PARADOX):
                si = offset_map[i] if offset_map else i
                di = offset_map[i + 1] if offset_map else i + 1
                results.append((si, di))
        return results

    @staticmethod
    def _find_degeneration_strict(
        trace: Sequence[Verdict],
        *,
        offset_map: Optional[list[int]] = None,
    ) -> list[tuple[int, int, int, int]]:
        """Find all MIRROR→PARADOX→TIMEOUT→SHADOW degeneration sequences."""
        results: list[tuple[int, int, int, int]] = []
        for i in range(len(trace) - 3):
            if (trace[i] == Verdict.MIRROR_PARADOX
                    and trace[i + 1] == Verdict.PARADOX
                    and trace[i + 2] == Verdict.TIMEOUT
                    and trace[i + 3] == Verdict.SHADOW_PARADOX):
                m = offset_map[i] if offset_map else i
                p = offset_map[i + 1] if offset_map else i + 1
                t = offset_map[i + 2] if offset_map else i + 2
                s = offset_map[i + 3] if offset_map else i + 3
                results.append((m, p, t, s))
        return results

    @staticmethod
    def _find_full_cycles_strict(
        trace: Sequence[Verdict],
        *,
        offset_map: Optional[list[int]] = None,
    ) -> list[CycleOccurrence]:
        """Find all complete SHADOW→MIRROR→PARADOX→TIMEOUT→SHADOW cycles."""
        results: list[CycleOccurrence] = []
        for i in range(len(trace) - 4):
            if (trace[i] == Verdict.SHADOW_PARADOX
                    and trace[i + 1] == Verdict.MIRROR_PARADOX
                    and trace[i + 2] == Verdict.PARADOX
                    and trace[i + 3] == Verdict.TIMEOUT
                    and trace[i + 4] == Verdict.SHADOW_PARADOX):
                def idx(k: int) -> int:
                    return offset_map[k] if offset_map else k
                results.append(CycleOccurrence(
                    start=idx(i),
                    end=idx(i + 4),
                    convergence_idx=idx(i),
                    degen_start_idx=idx(i + 1),
                    degen_mid_idx=idx(i + 2),
                    degen_end_idx=idx(i + 3),
                ))
        return results

    # ── Loose detection helpers ───────────────────────────────────────────

    @staticmethod
    def _filter_to_cycle_states(
        trace: Sequence[Verdict],
    ) -> list[tuple[int, Verdict]]:
        """Return (original_index, verdict) for cycle-state verdicts only."""
        return [(i, v) for i, v in enumerate(trace) if v in _CYCLE_SET]


def detect_cycle(
    trace: Sequence[Verdict],
    *,
    strict: bool = True,
) -> CycleAnalysis:
    """Convenience function: detect meta-mirror 4-cycle in a verdict trace."""
    return MetaMirrorDetector(strict=strict).classify(trace)


def flag_degeneration(
    trace: Sequence[Verdict],
    *,
    strict: bool = True,
    threshold: int = 1,
) -> bool:
    """Return True if the trace contains >= threshold degeneration events.

    Use this as a safety flag: if a verification system enters degeneration
    more than ``threshold`` times, the meta-mirror is unstable.
    """
    analysis = detect_cycle(trace, strict=strict)
    return analysis.degeneration_count >= threshold


def measure_ratio(
    trace: Sequence[Verdict],
    *,
    strict: bool = True,
) -> Optional[float]:
    """Return the convergence:degeneration ratio, or None if no degeneration."""
    return detect_cycle(trace, strict=strict).ratio
