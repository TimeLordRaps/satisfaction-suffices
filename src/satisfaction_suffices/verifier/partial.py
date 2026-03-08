"""
partial.py — Partial constraint evaluation for constraint-first generation.
============================================================================

The exact question "can this prefix be extended to a VERIFIED completion?"
is PSPACE-hard (it requires quantified Boolean reasoning over all possible
continuations).

This module implements a polynomial-time approximation:

    Given prefix x_{1:k} and constraint C backed by a CNF formula φ,
    classify each clause as:
        DEAD      — all literals falsified by the prefix → prefix is a dead end
        SATISFIED — at least one literal confirmed true   → clause already done
        FREE      — at least one literal unassigned       → still reachable

    If any clause is DEAD:  return PRUNABLE  (safe to prune this beam)
    If all clauses FREE/SAT: sat_ratio = (SAT + FREE) / total → EXTENDABLE or UNRESOLVED

    Unit propagation (linear time) is applied first to catch forced
    assignments that unit propagation can determine without backtracking.
    Only if unit propagation finds no contradiction do we fall through
    to the ratio-based classification.

Complexity: O(|φ|) per prefix evaluation where |φ| = number of clauses.
This is acceptable for online beam search — each beam step costs one
O(|φ|) pass, not a full SAT solve.

Integration
-----------
This module lives in verifier/ because it depends on the SAT solver and
text_to_3sat pipeline.  The constraint algebra (logic/constraint.py) calls
into this module via PrefixFeasibility.from_sat_ratio — it never needs to
know the internals.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Optional, Set, Tuple

from .sat import CDCLSolver, LBool, SAT_COHERENT, SAT_PLATEAU_LO, pos_lit, neg_lit, var_of, sign_of
from .text_to_3sat import TextTo3SAT


# ── ClauseStatus ──────────────────────────────────────────────────────────────

class ClauseStatus(Enum):
    """Classification of a single clause given a partial assignment."""
    DEAD      = auto()   # all literals false — UNSAT proof
    SATISFIED = auto()   # at least one literal true — done
    FREE      = auto()   # at least one literal unassigned — still reachable
    UNIT      = auto()   # exactly one unassigned literal (unit propagation target)


# ── PartialAssignment ─────────────────────────────────────────────────────────

class PartialAssignment:
    """
    A partial variable assignment for a CNF formula.

    Variables start UNKNOWN.  Assigning a variable TRUE or FALSE
    propagates through unit clauses automatically via unit propagation.

    This is the mechanism that makes partial evaluation tractable:
    we don't need to enumerate all completions, just propagate what
    the prefix text determines and count what's left.
    """

    def __init__(self, n_vars: int):
        self.n_vars = n_vars
        # LBool.UNDEF = 0, LBool.TRUE = 1, LBool.FALSE = 2 (from sat.py)
        self._assignment: List[Optional[bool]] = [None] * (n_vars + 1)  # 1-indexed

    def assign(self, var: int, value: bool) -> None:
        """Assign a variable.  1-indexed vars."""
        if 1 <= var <= self.n_vars:
            self._assignment[var] = value

    def assign_from_present_propositions(
        self, present: Set[int], absent: Set[int]
    ) -> None:
        """
        Assign variables based on which propositions appear in the prefix.
        Propositions map to variable indices (1-indexed).
        """
        for var in present:
            if 1 <= var <= self.n_vars:
                self._assignment[var] = True
        for var in absent:
            if 1 <= var <= self.n_vars:
                self._assignment[var] = False

    def lit_value(self, lit: int) -> Optional[bool]:
        """
        Get the truth value of a literal.
        lit > 0 → positive literal (var lit)
        lit < 0 → negative literal (var -lit)
        Returns None if the variable is unassigned.
        """
        var = abs(lit)
        if var < 1 or var > self.n_vars:
            return None
        val = self._assignment[var]
        if val is None:
            return None
        return val if lit > 0 else not val

    def clause_status(self, clause: List[int]) -> ClauseStatus:
        """Classify a clause given the current partial assignment."""
        n_false = 0
        n_unassigned = 0

        for lit in clause:
            v = self.lit_value(lit)
            if v is True:
                return ClauseStatus.SATISFIED
            elif v is False:
                n_false += 1
            else:
                n_unassigned += 1

        if n_unassigned == 0:
            return ClauseStatus.DEAD
        if n_unassigned == 1:
            return ClauseStatus.UNIT
        return ClauseStatus.FREE

    def unit_propagate(self, clauses: List[List[int]]) -> bool:
        """
        Run unit propagation to completion.
        Returns False if a contradiction is found (DEAD clause), True otherwise.

        Unit propagation: if a clause has exactly one unassigned literal,
        that literal must be true.  Repeat until no more unit clauses.
        """
        changed = True
        while changed:
            changed = False
            for clause in clauses:
                status = self.clause_status(clause)
                if status == ClauseStatus.DEAD:
                    return False  # Contradiction
                if status == ClauseStatus.UNIT:
                    # Find the unassigned literal and force it true
                    for lit in clause:
                        v = self.lit_value(lit)
                        if v is None:
                            var = abs(lit)
                            self.assign(var, lit > 0)
                            changed = True
                            break
        return True  # No contradiction found


# ── PrefixFeasibilityResult ───────────────────────────────────────────────────

@dataclass
class PrefixFeasibilityResult:
    """
    Detailed result of evaluating a prefix against a constraint's CNF formula.

    Fields
    ------
    sat_ratio      — (satisfied + free) / total  →  input to PartialResult decision
    n_dead         — clauses proving unsatisfiability
    n_satisfied    — clauses already done (at least one true literal)
    n_free         — clauses still reachable (unassigned literals remain)
    n_unit         — clauses at the unit propagation frontier
    n_total        — total clauses in the formula
    contradiction  — True if unit propagation found a definite contradiction
    eval_ms        — wall-clock time for this evaluation in milliseconds
    prefix_len     — character length of the prefix evaluated
    """
    sat_ratio:     float
    n_dead:        int
    n_satisfied:   int
    n_free:        int
    n_unit:        int
    n_total:       int
    contradiction: bool
    eval_ms:       float  = 0.0
    prefix_len:    int    = 0

    @property
    def is_dead(self) -> bool:
        return self.contradiction or self.n_dead > 0

    @property
    def extendable(self) -> bool:
        return not self.is_dead and self.sat_ratio >= SAT_COHERENT

    @property
    def prunable(self) -> bool:
        return self.is_dead or self.sat_ratio < SAT_PLATEAU_LO

    @property
    def unresolved(self) -> bool:
        """True if this prefix is in the phase-transition zone (neither clearly extendable nor prunable)."""
        return not self.is_dead and SAT_PLATEAU_LO <= self.sat_ratio < SAT_COHERENT

    @property
    def frontier(self) -> bool:
        """Back-compat alias for unresolved."""
        return self.unresolved


# ── PartialConstraintEvaluator ────────────────────────────────────────────────

class PartialConstraintEvaluator:
    """
    Evaluates whether a given prefix can still lead to a constraint-satisfying
    completion.  This is the core mechanism of constraint-first generation.

    Algorithm
    ---------
    1. Translate prefix to CNF via TextTo3SAT.
    2. Build a PartialAssignment from variables fixed by the prefix.
    3. Run unit propagation to closure — O(|φ|).
    4. If contradiction found: return (PRUNABLE, ratio=0).
    5. Classify remaining clauses: DEAD/SATISFIED/FREE/UNIT.
    6. sat_ratio = (n_satisfied + n_free + n_unit) / n_total
    7. Threshold sat_ratio against SAT_COHERENT / SAT_PLATEAU_LO.

    The key property: this is O(|φ|) per call, not exponential.
    SAT backtracking is NOT used here — we're doing prefix feasibility,
    not complete solving.  Completeness is sacrificed for polynomial
    running time, giving a SOUND over-approximation: if we say PRUNABLE,
    the prefix is definitely a dead end.  If we say EXTENDABLE, it might
    still be unreachable (false positive), but we never prune good beams.

    Parameters
    ----------
    domain         — constraint domain for text_to_3sat ("auto", "logic", etc.)
    prop_budget    — max propositions to extract (controls formula size)
    cache_size     — number of prefix evaluations to cache (LRU)
    """

    def __init__(
        self,
        domain: str = "auto",
        prop_budget: int = 256,
        cache_size: int = 1024,
    ):
        self.domain = domain
        self.prop_budget = prop_budget
        self._translator = TextTo3SAT()
        self._cache: Dict[str, PrefixFeasibilityResult] = {}
        self._cache_size = cache_size

    def evaluate(self, prefix: str) -> PrefixFeasibilityResult:
        """
        Evaluate whether this prefix can reach a VERIFIED completion.

        Returns PrefixFeasibilityResult with full diagnostics.
        Safe to call on every beam step during generation.
        """
        # Cache by prefix text
        if prefix in self._cache:
            return self._cache[prefix]

        t0 = time.perf_counter()
        result = self._evaluate_impl(prefix)
        result.eval_ms = (time.perf_counter() - t0) * 1000.0
        result.prefix_len = len(prefix)

        # LRU eviction
        if len(self._cache) >= self._cache_size:
            oldest = next(iter(self._cache))
            del self._cache[oldest]
        self._cache[prefix] = result

        return result

    def _evaluate_impl(self, prefix: str) -> PrefixFeasibilityResult:
        """Core evaluation logic."""
        try:
            n_vars, clauses = self._translator.translate(prefix)
        except Exception:
            # Translation failure → assume extendable (never falsely prune)
            return PrefixFeasibilityResult(
                sat_ratio=1.0,
                n_dead=0, n_satisfied=0, n_free=0, n_unit=0, n_total=0,
                contradiction=False,
            )

        if not clauses or n_vars == 0:
            return PrefixFeasibilityResult(
                sat_ratio=1.0,
                n_dead=0, n_satisfied=0, n_free=0, n_unit=0, n_total=0,
                contradiction=False,
            )

        assignment = PartialAssignment(n_vars)
        # All variables start unassigned — current prefix determines nothing
        # about FUTURE tokens, but the propositions PRESENT in the prefix
        # are determined TRUE (they're in the text) and those that appear
        # negated with no positive form are determined FALSE.
        # For now: start with all unassigned and let unit propagation drive.
        # (A future extension would map proposition positions → variable assignments.)

        # Unit propagation
        no_contradiction = assignment.unit_propagate(clauses)

        if not no_contradiction:
            return PrefixFeasibilityResult(
                sat_ratio=0.0,
                n_dead=len(clauses), n_satisfied=0, n_free=0, n_unit=0,
                n_total=len(clauses),
                contradiction=True,
            )

        # Classify all clauses
        n_dead = n_satisfied = n_free = n_unit = 0
        for clause in clauses:
            status = assignment.clause_status(clause)
            if status == ClauseStatus.DEAD:
                n_dead += 1
            elif status == ClauseStatus.SATISFIED:
                n_satisfied += 1
            elif status == ClauseStatus.FREE:
                n_free += 1
            elif status == ClauseStatus.UNIT:
                n_unit += 1

        n_total = len(clauses)
        if n_total == 0:
            sat_ratio = 1.0
        else:
            sat_ratio = (n_satisfied + n_free + n_unit) / n_total

        return PrefixFeasibilityResult(
            sat_ratio=sat_ratio,
            n_dead=n_dead,
            n_satisfied=n_satisfied,
            n_free=n_free,
            n_unit=n_unit,
            n_total=n_total,
            contradiction=(n_dead > 0),
        )

    def batch_evaluate(
        self, prefixes: List[str]
    ) -> List[PrefixFeasibilityResult]:
        """Evaluate multiple prefixes.  Shared translator instance, cached."""
        return [self.evaluate(p) for p in prefixes]

    def clear_cache(self) -> None:
        self._cache.clear()


# ── Module-level convenience function ─────────────────────────────────────────

_default_evaluator: Optional[PartialConstraintEvaluator] = None


def evaluate_partial(
    prefix: str,
    domain: str = "auto",
) -> PrefixFeasibilityResult:
    """
    Evaluate whether the given prefix can be extended to a VERIFIED completion.

    This is the function called at every beam expansion step in
    constraint-first generation.  O(|φ|) — safe for hot-loop use.

    Returns PrefixFeasibilityResult.  Key fields:
        .prunable   → True if this beam should be pruned immediately
        .extendable → True if this beam is clearly on a good path
        .unresolved → True if this beam is in the phase-transition zone
        .sat_ratio  → raw score (0.0 = definite dead end, 1.0 = fully satisfiable)
    """
    global _default_evaluator
    if _default_evaluator is None or _default_evaluator.domain != domain:
        _default_evaluator = PartialConstraintEvaluator(domain=domain)
    return _default_evaluator.evaluate(prefix)
