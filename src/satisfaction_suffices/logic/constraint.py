"""
constraint.py — Formal constraint algebra for constraint-first generation.
===========================================================================

The core distinction this module formalises:

    Rejection sampling (constraint-last):
        generate(prompt) → x  →  if C(x): emit else: discard

    Reward shaping (constraint-during):
        train to maximise E[C(x)]  →  biased distribution, not a hard boundary

    Constraint-first:
        x* = argmax_{x ∈ C⁻¹(VERIFIED)} p(x | prompt)
        Beam pruning at every token step from PartialConstraint.
        The constraint IS the search space. It is never bypassed.

Formal objects
--------------
Constraint        C : V* → {VERIFIED, CONTRADICTION, PARADOX, TIMEOUT}
PartialConstraint C_partial : V* → {EXTENDABLE, PRUNABLE, UNRESOLVED}

    EXTENDABLE  ↔  ∃ extension x_{k+1:n} s.t. C(x_{1:n}) = VERIFIED
    PRUNABLE    ↔  ∀ extensions,             C(x_{1:n}) ≠ VERIFIED  (dead end)
    UNRESOLVED  ↔  insufficient information to classify  (route to proof evolution)

Algebraic invariants
--------------------
Conjunction  (C₁ ∧ C₂):
    PRUNABLE  iff  C₁ prunable  OR  C₂ prunable
    EXTENDABLE iff  C₁ extendable AND C₂ extendable

Disjunction  (C₁ ∨ C₂):
    PRUNABLE  iff  C₁ prunable  AND  C₂ prunable
    EXTENDABLE iff  C₁ extendable OR  C₂ extendable

These are the De Morgan duals on PartialResult — the algebra is a bounded
distributive lattice with EXTENDABLE = ⊤ and PRUNABLE = ⊥.

Clause-to-variable ratio
------------------------
For random 3-CNF with n variables and m clauses, the SAT/UNSAT threshold
sits near m/n ≈ 4.0 (high clause-to-variable ratio).
The UNRESOLVED zone is the ε-neighbourhood of that transition.  Proof evolution
(logic/proof_evo.py) handles unresolved verdicts — paradoxes become catalysts,
not dead ends.
"""

from __future__ import annotations

import abc
import math
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Callable, List, Optional, Sequence, Tuple

from ..verifier.verify import Verdict, VerificationResult, verify


# ── Clause-to-variable ratio constants ────────────────────────────────────────

CLAUSE_RATIO_THRESHOLD: float = 4.0     # m/n threshold (high ratio zone)
SAT_COHERENT: float = 0.94              # above → EXTENDABLE
SAT_PLATEAU_LO: float = 0.80            # below → PRUNABLE


# ── PartialResult ─────────────────────────────────────────────────────────────

class PartialResult(Enum):
    """
    The three-valued result of evaluating a constraint against a *prefix*.

    This is the tractable approximation of the undecidable question:
        "Can this prefix be extended to a constraint-satisfying completion?"

    Lattice order:  EXTENDABLE (⊤) > UNRESOLVED > PRUNABLE (⊥)
    """
    EXTENDABLE = auto()   # prefix is on a satisfiable path — keep this beam
    UNRESOLVED = auto()   # insufficient information — route to proof evolution
    PRUNABLE   = auto()   # dead end — no satisfying extension possible



# Lattice meet (greatest lower bound) — used for conjunction lifting
def _partial_meet(a: PartialResult, b: PartialResult) -> PartialResult:
    if a == PartialResult.PRUNABLE or b == PartialResult.PRUNABLE:
        return PartialResult.PRUNABLE
    if a == PartialResult.UNRESOLVED or b == PartialResult.UNRESOLVED:
        return PartialResult.UNRESOLVED
    return PartialResult.EXTENDABLE


# Lattice join (least upper bound) — used for disjunction lifting
def _partial_join(a: PartialResult, b: PartialResult) -> PartialResult:
    if a == PartialResult.EXTENDABLE or b == PartialResult.EXTENDABLE:
        return PartialResult.EXTENDABLE
    if a == PartialResult.UNRESOLVED or b == PartialResult.UNRESOLVED:
        return PartialResult.UNRESOLVED
    return PartialResult.PRUNABLE


# ── PrefixFeasibility ─────────────────────────────────────────────────────────

@dataclass
class PrefixFeasibility:
    """
    Full diagnostic returned when evaluating a constraint against a prefix.

    sat_ratio     — fraction of CNF clauses satisfiable given the prefix.
                    Powers the EXTENDABLE/UNRESOLVED/PRUNABLE decision.
    result        — the PartialResult verdict.
    confidence    — how far from the phase-transition boundary we are.
                    confidence = 1.0 at sat_ratio=1.0, 0.0 at phase transition.
    clauses_free  — clauses with at least one unfixed literal (can still satisfy)
    clauses_fixed — clauses with all literals fixed by the prefix
    clauses_dead  — clauses fixed and unsatisfied (proof of unsatisfiability)
    text          — the prefix text that was evaluated (if provided)
    """
    sat_ratio:     float
    result:        PartialResult
    confidence:    float
    clauses_free:  int = 0
    clauses_fixed: int = 0
    clauses_dead:  int = 0
    text:          Optional[str] = None

    @property
    def is_extendable(self) -> bool:
        return self.result == PartialResult.EXTENDABLE

    @property
    def is_prunable(self) -> bool:
        return self.result == PartialResult.PRUNABLE

    @property
    def is_unresolved(self) -> bool:
        return self.result == PartialResult.UNRESOLVED

    @property
    def is_frontier(self) -> bool:
        """Back-compat alias for is_unresolved."""
        return self.is_unresolved

    @classmethod
    def from_sat_ratio(
        cls,
        ratio: float,
        clauses_free: int = 0,
        clauses_fixed: int = 0,
        clauses_dead: int = 0,
        text: Optional[str] = None,
    ) -> "PrefixFeasibility":
        if ratio >= SAT_COHERENT:
            result = PartialResult.EXTENDABLE
        elif ratio < SAT_PLATEAU_LO:
            result = PartialResult.PRUNABLE
        else:
            result = PartialResult.UNRESOLVED

        # Confidence = normalised distance from phase-transition midpoint
        midpoint = (SAT_COHERENT + SAT_PLATEAU_LO) / 2.0
        half_width = (SAT_COHERENT - SAT_PLATEAU_LO) / 2.0
        confidence = min(1.0, abs(ratio - midpoint) / half_width)

        return cls(
            sat_ratio=ratio,
            result=result,
            confidence=confidence,
            clauses_free=clauses_free,
            clauses_fixed=clauses_fixed,
            clauses_dead=clauses_dead,
            text=text,
        )


# ── Abstract Constraint ───────────────────────────────────────────────────────

class Constraint(abc.ABC):
    """
    Abstract base for all constraints in the constraint-first framework.

    A constraint is a function from token sequences to the four-valued verdict:
        VERIFIED      — constraint satisfied, emit this completion
        CONTRADICTION — constraint provably violated, discard
        PARADOX       — structural conflict (individually SAT, jointly UNSAT)
        TIMEOUT       — solver budget exhausted, route to proof evolution

    The partial_eval method approximates whether a *prefix* can still reach
    a VERIFIED completion — this is the mechanism "first" means: we evaluate
    at every token step, not after completion.

    Composition operators return new Constraint instances:
        C1 & C2   →  ConjunctiveConstraint
        C1 | C2   →  DisjunctiveConstraint
        ~C        →  NegatedConstraint
    """

    @abc.abstractmethod
    def __call__(self, text: str) -> Verdict:
        """Evaluate the constraint against a complete sequence."""
        ...

    @abc.abstractmethod
    def partial_eval(self, prefix: str) -> PrefixFeasibility:
        """
        Evaluate whether this prefix can still lead to a VERIFIED completion.

        This is the tractable approximation of C_partial.  The exact answer
        requires solving a PSPACE-hard problem (QBF); this approximation uses
        SAT ratio as a polynomial proxy.
        """
        ...

    def __and__(self, other: "Constraint") -> "ConjunctiveConstraint":
        return ConjunctiveConstraint(self, other)

    def __or__(self, other: "Constraint") -> "DisjunctiveConstraint":
        return DisjunctiveConstraint(self, other)

    def __invert__(self) -> "NegatedConstraint":
        return NegatedConstraint(self)


# ── SATConstraint ─────────────────────────────────────────────────────────────

class SATConstraint(Constraint):
    """
    Constraint implemented via the VerificationGate + SAT solver pipeline.

    This is the primary implementation.  Text → 3-SAT via TseitinEncoder,
    then SAT solving with unit propagation and pure literal elimination.

    The partial_eval approximation:
        Given prefix x_{1:k}, build the 3-CNF formula φ(x_{1:k}).
        A clause is "dead" if all its literals are false under the current
        prefix.  A clause is "free" if at least one literal is unassigned.
        sat_ratio = (total_clauses - dead_clauses) / total_clauses
    """

    def __init__(self, domain: str = "auto", paradox_threshold: int = 5_000):
        self.domain = domain
        self.paradox_threshold = paradox_threshold

    def __call__(self, text: str) -> Verdict:
        result: VerificationResult = verify(text, domain=self.domain)
        return result.verdict

    def partial_eval(self, prefix: str) -> PrefixFeasibility:
        from ..verifier.text_to_3sat import TextTo3SAT
        from ..verifier.sat import CDCLSolver, sat_score

        try:
            translator = TextTo3SAT(domain=self.domain)
            n_vars, clauses = translator.translate(prefix)

            if not clauses:
                return PrefixFeasibility.from_sat_ratio(
                    1.0, clauses_free=0, clauses_fixed=0, clauses_dead=0, text=prefix
                )

            solver = CDCLSolver(n_vars, clauses)
            result = solver.solve(budget=self.paradox_threshold)
            ratio = sat_score(result)

            # Count clause categories from the formula
            n_clauses = len(clauses)
            n_dead = sum(
                1 for clause in clauses
                if all(lit < 0 for lit in clause)
            )
            n_free = n_clauses - n_dead

            return PrefixFeasibility.from_sat_ratio(
                ratio,
                clauses_free=n_free,
                clauses_fixed=n_clauses - n_free,
                clauses_dead=n_dead,
                text=prefix,
            )

        except Exception:
            # Encoding failure → treat as UNRESOLVED, not PRUNABLE
            return PrefixFeasibility.from_sat_ratio(
                (SAT_COHERENT + SAT_PLATEAU_LO) / 2.0,
                text=prefix,
            )


# ── FunctionConstraint ────────────────────────────────────────────────────────

class FunctionConstraint(Constraint):
    """
    Wraps an arbitrary callable as a Constraint.

    For cases where the constraint is a custom function that doesn't
    reduce to SAT.  partial_eval defaults to calling the full constraint
    on the prefix text (conservative — never PRUNABLE based on prefix alone).

    Use when you have a deterministic verifier but no 3-SAT encoding.
    """

    def __init__(
        self,
        fn: Callable[[str], bool],
        partial_fn: Optional[Callable[[str], PartialResult]] = None,
    ):
        self._fn = fn
        self._partial_fn = partial_fn

    def __call__(self, text: str) -> Verdict:
        return Verdict.VERIFIED if self._fn(text) else Verdict.CONTRADICTION

    def partial_eval(self, prefix: str) -> PrefixFeasibility:
        if self._partial_fn is not None:
            result = self._partial_fn(prefix)
            ratio = {
                PartialResult.EXTENDABLE: 1.0,
                PartialResult.UNRESOLVED: (SAT_COHERENT + SAT_PLATEAU_LO) / 2.0,
                PartialResult.PRUNABLE:   0.0,
            }[result]
            return PrefixFeasibility.from_sat_ratio(ratio, text=prefix)
        # No partial function — conservatively assume extendable
        return PrefixFeasibility.from_sat_ratio(1.0, text=prefix)


# ── Compositional Constraints ─────────────────────────────────────────────────

class ConjunctiveConstraint(Constraint):
    """
    C₁ ∧ C₂ — both constraints must be satisfied.

    Algebraic lifting of PartialResult to conjunction:
        PRUNABLE   iff  either sub-constraint is PRUNABLE   (lattice meet)
        EXTENDABLE iff  both sub-constraints are EXTENDABLE
        UNRESOLVED otherwise

    Four-valued verdict priority (conjunction):
        CONTRADICTION > PARADOX > TIMEOUT > VERIFIED
    CONTRADICTION short-circuits; PARADOX takes precedence over TIMEOUT
    because it is a structural finding, not merely operational.
    """

    def __init__(self, left: Constraint, right: Constraint):
        self.left = left
        self.right = right

    def __call__(self, text: str) -> Verdict:
        v_left = self.left(text)
        if v_left == Verdict.CONTRADICTION:
            return Verdict.CONTRADICTION
        v_right = self.right(text)
        if v_right == Verdict.CONTRADICTION:
            return Verdict.CONTRADICTION
        if v_left == Verdict.PARADOX or v_right == Verdict.PARADOX:
            return Verdict.PARADOX
        if v_left == Verdict.TIMEOUT or v_right == Verdict.TIMEOUT:
            return Verdict.TIMEOUT
        return Verdict.VERIFIED

    def partial_eval(self, prefix: str) -> PrefixFeasibility:
        f_left  = self.left.partial_eval(prefix)
        f_right = self.right.partial_eval(prefix)
        combined = _partial_meet(f_left.result, f_right.result)
        avg_ratio = (f_left.sat_ratio + f_right.sat_ratio) / 2.0
        return PrefixFeasibility.from_sat_ratio(avg_ratio, text=prefix)


class DisjunctiveConstraint(Constraint):
    """
    C₁ ∨ C₂ — at least one constraint must be satisfied.

    Algebraic lifting of PartialResult to disjunction:
        EXTENDABLE iff  either sub-constraint is EXTENDABLE  (lattice join)
        PRUNABLE   iff  both sub-constraints are PRUNABLE
        UNRESOLVED otherwise

    Four-valued verdict priority (disjunction):
        VERIFIED > TIMEOUT > PARADOX > CONTRADICTION
    VERIFIED short-circuits; TIMEOUT takes precedence over PARADOX
    because it is more likely to resolve with additional compute.
    """

    def __init__(self, left: Constraint, right: Constraint):
        self.left = left
        self.right = right

    def __call__(self, text: str) -> Verdict:
        v_left  = self.left(text)
        v_right = self.right(text)
        if v_left == Verdict.VERIFIED or v_right == Verdict.VERIFIED:
            return Verdict.VERIFIED
        if v_left == Verdict.TIMEOUT or v_right == Verdict.TIMEOUT:
            return Verdict.TIMEOUT
        if v_left == Verdict.PARADOX or v_right == Verdict.PARADOX:
            return Verdict.PARADOX
        return Verdict.CONTRADICTION

    def partial_eval(self, prefix: str) -> PrefixFeasibility:
        f_left  = self.left.partial_eval(prefix)
        f_right = self.right.partial_eval(prefix)
        combined = _partial_join(f_left.result, f_right.result)
        max_ratio = max(f_left.sat_ratio, f_right.sat_ratio)
        return PrefixFeasibility.from_sat_ratio(max_ratio, text=prefix)


class NegatedConstraint(Constraint):
    """
    ¬C — the constraint must NOT be satisfied.

    Note: negation of VERIFIED is CONTRADICTION and vice versa.
    PARADOX and TIMEOUT are fixed under negation (undecidability is symmetric).

    Useful for "this text must NOT be a valid proof of X" type constraints.
    """

    def __init__(self, inner: Constraint):
        self.inner = inner

    def __call__(self, text: str) -> Verdict:
        v = self.inner(text)
        if v == Verdict.VERIFIED:
            return Verdict.CONTRADICTION
        if v == Verdict.CONTRADICTION:
            return Verdict.VERIFIED
        return v  # PARADOX and TIMEOUT are fixed under negation

    def partial_eval(self, prefix: str) -> PrefixFeasibility:
        f = self.inner.partial_eval(prefix)
        # Negation flips EXTENDABLE ↔ PRUNABLE, UNRESOLVED stays UNRESOLVED
        if f.result == PartialResult.EXTENDABLE:
            flipped = PartialResult.PRUNABLE
            ratio = 1.0 - f.sat_ratio
        elif f.result == PartialResult.PRUNABLE:
            flipped = PartialResult.EXTENDABLE
            ratio = 1.0 - f.sat_ratio
        else:
            flipped = PartialResult.UNRESOLVED
            ratio = f.sat_ratio
        return PrefixFeasibility.from_sat_ratio(ratio, text=prefix)


class SequentialConstraint(Constraint):
    """
    Apply constraints in sequence: each constraint applies to the
    portion of the output generated after the previous constraint passed.

    Useful for chain-of-thought verification: premise → reasoning → conclusion,
    where each step has its own constraint and each feeds into the next.
    """

    def __init__(self, *constraints: Constraint, breakpoints: Optional[List[int]] = None):
        self.constraints = list(constraints)
        self.breakpoints = breakpoints  # token indices where constraint switches

    def __call__(self, text: str) -> Verdict:
        # Simple case: apply all constraints to full text, require all VERIFIED
        for c in self.constraints:
            if c(text) == Verdict.CONTRADICTION:
                return Verdict.CONTRADICTION
        verdicts = [c(text) for c in self.constraints]
        if any(v == Verdict.PARADOX for v in verdicts):
            return Verdict.PARADOX
        if any(v == Verdict.TIMEOUT for v in verdicts):
            return Verdict.TIMEOUT
        return Verdict.VERIFIED

    def partial_eval(self, prefix: str) -> PrefixFeasibility:
        # Use meet (most conservative) across all constraints on the prefix
        results = [c.partial_eval(prefix) for c in self.constraints]
        worst   = min(results, key=lambda f: f.sat_ratio)
        return worst


# ── ConstraintAlgebra ─────────────────────────────────────────────────────────

class ConstraintAlgebra:
    """
    Factory and operations for building constraint expressions.

    All returned objects preserve the algebraic invariants documented in the
    module docstring.  Compose freely — operator overloading handles nesting.

    Usage
    -----
        algebra = ConstraintAlgebra()
        C = algebra.sat("logic") & algebra.sat("math")
        C = algebra.sat("code") | algebra.fn(lambda x: len(x) < 512)
        result = C("if A then A")      # → Verdict
        partial = C.partial_eval("if") # → PrefixFeasibility
    """

    def sat(self, domain: str = "auto", paradox_threshold: int = 5_000) -> SATConstraint:
        """Constraint backed by the full SAT solver pipeline."""
        return SATConstraint(domain=domain, paradox_threshold=paradox_threshold)

    def fn(
        self,
        fn: Callable[[str], bool],
        partial_fn: Optional[Callable[[str], PartialResult]] = None,
    ) -> FunctionConstraint:
        """Constraint from an arbitrary boolean function."""
        return FunctionConstraint(fn, partial_fn)

    def all_of(self, *constraints: Constraint) -> Constraint:
        """All constraints must be VERIFIED.  Equivalent to C₁ & C₂ & ..."""
        if not constraints:
            raise ValueError("all_of requires at least one constraint")
        result = constraints[0]
        for c in constraints[1:]:
            result = ConjunctiveConstraint(result, c)
        return result

    def any_of(self, *constraints: Constraint) -> Constraint:
        """At least one constraint must be VERIFIED.  Equivalent to C₁ | C₂ | ..."""
        if not constraints:
            raise ValueError("any_of requires at least one constraint")
        result = constraints[0]
        for c in constraints[1:]:
            result = DisjunctiveConstraint(result, c)
        return result

    def chain(self, *constraints: Constraint) -> SequentialConstraint:
        """Apply constraints sequentially across chain-of-thought steps."""
        return SequentialConstraint(*constraints)

    def never(self, constraint: Constraint) -> NegatedConstraint:
        """The constraint must NOT be satisfied."""
        return NegatedConstraint(constraint)


# Module-level singleton
algebra = ConstraintAlgebra()
