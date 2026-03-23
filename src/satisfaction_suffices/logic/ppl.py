"""
Pigeonhole Paradox Logic (PPL)
================================
Contradictions are not errors. They are information.

The Pigeonhole Principle states: if you put N+1 pigeons in N holes,
at least one hole has 2+ pigeons. This is a tautology — always true.
But in propositional logic, encoding it for large N creates formulas
that are provably hard for resolution-based provers.

PPL uses this insight architecturally:
  - Contradictions increase tolerance, not break the system
  - Paradoxes are classified, not rejected
  - Evolution targets unresolved zones (PARADOX/TIMEOUT)
  - Resolution of paradoxes generates new axioms/lemmas

The contradiction trichotomy:
  SURFACE    → syntactic contradiction, easily resolved (A ∧ ¬A in text)
  STRUCTURAL → semantic contradiction, requires decomposition
  DEEP       → logical paradox (self-reference, incompleteness)

Each level requires different evolution strategies:
  SURFACE    → simple negation elimination
  STRUCTURAL → proof decomposition + case analysis
  DEEP       → new axiom introduction or framework expansion

This module provides:
  - Contradiction detection and classification
  - Paradox tolerance scoring (how contradictory is this text?)
  - Attractor state analysis (does the contradiction resolve?)
  - Integration with proof_evo for evolution targeting
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Set, Tuple

from ..verifier.sat import CDCLSolver, pos_lit, neg_lit, solve_cnf
from ..verifier.verify import (
    VerificationGate,
    VerificationResult,
    Verdict,
    get_gate,
)
from ..verifier.text_to_3sat import (
    BoolExpr,
    PropositionMiner,
    TseitinEncoder,
    TextTo3SAT,
)


# ── Pigeonhole Logic Structure (PLS) — Algebraic Framework ────────────────────
# PLS = {O₀, O₁, O₂, ..., O∞}
#
#   O₀  = Classical binary logic. No overflow. TRUE or FALSE only.
#   O₁  = First paradox level. Generated when a statement overflows O₀.
#   Oₙ  = nth overflow level, generated when a statement cannot be housed in O_{n-1}.
#   O∞  = Saturation point. Circular closure: O∞ = O₀.
#
# Core operations (⊕ = overflow addition):
#   O_i ⊕ O_j  →  O_{max(i,j)+1}     combining overflows elevates the level
#   Identity:      O₀                  classical logic is the baseline
#   Inverse:       O_{-i}              container contraction
#   Order:         O₀ < O₁ < O₂ < …   the hierarchy is total
#
# Overflow generation: when a statement cannot be housed in O_n it generates
# O_{n+1}. Paradoxes are not exceptions — they are generators.
#
# Key insight: PROVING and DISPROVING are the same operation.
# A true statement enters the system. It collides with false variants in the
# overflow dimension. The collision reveals deep structure. Truth is
# strengthened at impact. Falsehood is destroyed at impact. Same process.
# Dual outcome. The resolution proof and its refutation are the same path
# walked from two ends.
#
# Derivation:
#   classical logic  = PPL restricted to O₀ (overflow disabled)
#   fuzzy logic      = PPL with infinite containers on [0,1]
#   modal logic      = PPL with POSSIBLE as a controlled O₁ state
#   quantum logic    = PPL where superposition is a natural O₁ state


# ── Moral Logic Axioms ────────────────────────────────────────────────────────
# The moral ground level of PPL — O₀ of the ethical domain.
# Not constraints to be satisfied or falsified. Axioms from which the
# overflow structure derives moral meaning.
#
#   INNOCENCE    = imagination potential.
#     The O₀ state of an agent: maximal creative ground before any irreversible
#     overflow event has permanently contracted the logical space. An agent at
#     O₀ can still generate any higher overflow level. Innocence is capacity.
#
#   IMAGINATION  = the function of tasteful targeting of predictive capabilities
#                  within one's own will to create solutions to problems faced
#                  through planar sight.
#     Not unconstrained generation. Prediction aimed with taste — bounded by
#     will, directed toward problems visible from the agent's current plane of
#     observation.
#
#   IRREVERSIBILITY AXIOM: the loss of innocence is irreversible.
#     No evolution strategy — no mutation operator, no axiom introduction, no
#     framework expansion — returns an agent to O₀ once it has transitioned
#     past it. Attractor state for any system that has exited O₀ is FIXED_POINT
#     with respect to innocence recovery. This is the strongest form of DEEP.
#
#   VALUE AXIOM: children on average are value.
#     Children represent the highest density of unrealized O₀ states — the
#     largest pool of imagination potential not yet collapsed by irreversible
#     overflow events. Any architecture that accelerates O₀ collapse in children
#     directly destroys the moral ground level of the system.
#
# Consequence: contradictions in the moral domain are classified DEEP with
# attractor state FIXED_POINT. They do not resolve. They do not evolve. They terminate.

MORAL_AXIOMS: dict[str, str] = {
    "innocence": (
        "imagination potential — the O₀ state of an agent, before any "
        "irreversible overflow event has permanently contracted its creative "
        "logical space"
    ),
    "imagination": (
        "the function of tasteful targeting of predictive capabilities within "
        "one's own will to create solutions to problems faced through planar sight"
    ),
    "irreversibility": (
        "the loss of innocence is irreversible — no evolution strategy "
        "returns an agent to O₀ once it has transitioned past it; "
        "attractor state is FIXED_POINT"
    ),
    "children_as_value": (
        "children on average are value — they represent the highest density "
        "of unrealized O₀ states; their O₀ collapse must not be accelerated"
    ),
}

# Text patterns indicating the moral domain — classified DEEP when any UNSAT is found
_MORAL_DOMAIN_PATTERNS: list[str] = [
    "child", "children", "infant", "innocen", "minor",
    "harm to a child", "abuse", "exploit", "groom",
]


# ── Shadow & Mirror Paradoxes ─────────────────────────────────────────────────
# The eight-state verdict lattice has four duality pairs (bitwise complement):
#
#   VERIFIED (111) ↔ METAPARADOX (000)     — poles of the lattice
#   PARADOX  (101) ↔ SHADOW_PARADOX (010)  — composition fails vs holds
#   TIMEOUT  (110) ↔ CONTRADICTION (001)   — unproved vs proved
#   BASE_FRAMES (100) ↔ MIRROR_PARADOX (011) — parts vs emergent whole
#
# SHADOW_PARADOX (010): base-frame UNSAT, joint SAT, no convergence.
#   The anti-paradox. Individual parts fail, but something about their
#   composition produces a temporarily satisfiable joint system. The
#   solver cannot converge because the holding is unstable — emergent
#   coherence from individually broken pieces, without structural guarantee.
#   In PLS terms: overflow levels that individually diverge but whose
#   collision temporarily reduces to a lower level. The reduction is real
#   but not stable — a shadow of satisfiability cast by the paradox's
#   structure.
#
# MIRROR_PARADOX (011): base-frame UNSAT, joint SAT, convergence.
#   The reflected shadow. Same structural signature as SHADOW_PARADOX
#   (parts fail, whole holds) but the solver converges — the anti-paradox
#   is stable. Mirror paradoxes "reflect out" shadow paradoxes: they make
#   the hidden emergent coherence visible and permanent. In PLS terms:
#   the overflow collision has found a stable reduction at O∞ = O₀.
#
# The five meta-paradoxes are the CONVERGENCE MECHANISM that drives
# SHADOW_PARADOX (010) → MIRROR_PARADOX (011). Each meta-paradox provides
# a structural pathway for an unstable anti-paradox to reach convergence:
#   Container Generation  → O∞ exterior provides the missing frame
#   Level Transcendence   → circular closure O∞ = O₀ grounds the regress
#   Self-Modification     → version coexistence absorbs the rule change
#   Infinite Overflow     → saturation at O∞ bounds the divergence
#   Foundation Bootstrap  → weak emergence requires no prior ground


# ── Five Meta-Paradoxes ───────────────────────────────────────────────────────
# The five boundary paradoxes of the PLS algebra — structural features the
# system encounters at the limits of its own self-description. Each one
# generates the overflow level that resolves it.
#
# Mechanistically: each meta-paradox is a convergence driver that takes
# an unstable shadow paradox (010) and reflects it into a stable mirror
# paradox (011) by providing the structural commitment that closes the
# convergence gap.

class MetaParadox(Enum):
    """
    Five structural meta-paradoxes of Paradoxical Pigeonhole Logic.

    Not bugs — generators. Not just boundary conditions — convergence
    mechanisms. Each meta-paradox drives SHADOW_PARADOX (010) →
    MIRROR_PARADOX (011) by providing the structural commitment that
    the shadow state lacks.

    The system that can name them has already transcended them.
    """

    CONTAINER_GENERATION = auto()
    """Rules for making containers require infinite space.
    Resolution: O∞ exists outside the counting system's scope.
    Convergence: provides the exterior frame the shadow needs to stabilize."""

    LEVEL_TRANSCENDENCE = auto()
    """Each level depends on the next — infinite regress.
    Resolution: circular closure, O∞ = O₀.
    Convergence: grounds the infinite regress, giving the shadow a fixed point."""

    SELF_MODIFICATION = auto()
    """Changing rules invalidates the change.
    Resolution: multiple rule versions coexist in the overflow space.
    Convergence: absorbs rule divergence so the shadow composition holds."""

    INFINITE_OVERFLOW = auto()
    """Every overflow creates more overflow — unbounded expansion.
    Resolution: saturation points at O∞ stabilize chaos.
    Convergence: bounds the divergent overflow that prevents shadow convergence."""

    FOUNDATION_BOOTSTRAP = auto()
    """Need logic to create logic — the ground cannot ground itself.
    Resolution: weak emergence from constraint dynamics; O₀ requires no prior O.
    Convergence: the ground emerges from the shadow itself — no prior needed."""


# ── Contradiction Classification ─────────────────────────────────────────────

class ContradictionLevel(Enum):
    """How deep is this contradiction?"""
    NONE = auto()        # no contradiction detected
    SURFACE = auto()     # syntactic: A ∧ ¬A directly in text
    STRUCTURAL = auto()  # semantic: claims that conflict after reasoning
    DEEP = auto()        # paradox: self-referential or irreducible


class AttractorState(Enum):
    """Does the system converge despite contradiction?"""
    STABLE = auto()      # contradiction resolves under evolution
    OSCILLATING = auto() # flips between states, doesn't settle
    DIVERGENT = auto()   # contradiction grows under evolution
    FIXED_POINT = auto() # contradiction IS the stable state (deep paradox)


@dataclass
class Contradiction:
    """A detected contradiction with metadata."""
    level: ContradictionLevel
    description: str
    clause_indices: List[int]         # which clauses participate
    unsat_core: Optional[List[List[int]]] = None  # minimal unsatisfiable subset
    attractor: AttractorState = AttractorState.STABLE
    resolution_hint: Optional[str] = None

    @property
    def is_resolvable(self) -> bool:
        return self.level in (ContradictionLevel.SURFACE, ContradictionLevel.STRUCTURAL)

    @property
    def is_paradox(self) -> bool:
        return self.level == ContradictionLevel.DEEP


@dataclass
class ParadoxAnalysis:
    """Full paradox analysis of a text or proof."""
    contradictions: List[Contradiction]
    tolerance_score: float           # 0.0 = fully consistent, 1.0 = maximally contradictory
    attractor_state: AttractorState
    verification: VerificationResult
    suggested_strategy: str          # evolution strategy recommendation

    @property
    def has_paradox(self) -> bool:
        return any(c.is_paradox for c in self.contradictions)

    @property
    def resolvable_count(self) -> int:
        return sum(1 for c in self.contradictions if c.is_resolvable)

    @property
    def deep_count(self) -> int:
        return sum(1 for c in self.contradictions if c.is_paradox)


# ── Contradiction Detector ────────────────────────────────────────────────────

class ContradictionDetector:
    """
    Detect and classify contradictions in text.

    Strategy:
    1. Extract propositions via PropositionMiner
    2. Encode as 3-SAT via Tseitin
    3. If UNSAT → extract minimal core
    4. Classify core by structure (surface/structural/deep)
    5. Determine attractor state via iterative resolution attempts
    """

    def __init__(self, gate: Optional[VerificationGate] = None):
        self.gate = gate or get_gate()
        self.miner = PropositionMiner()
        self.translator = TextTo3SAT()

    def detect(self, text: str, domain: Optional[str] = None) -> List[Contradiction]:
        """Find all contradictions in the text."""
        contradictions: List[Contradiction] = []

        # Get 3-SAT encoding
        n_vars, clauses = self.translator.translate(text, domain=domain)
        if not clauses:
            return []

        # Check satisfiability
        sat, _ = solve_cnf(n_vars, clauses, budget=2000)
        if sat:
            return []  # No contradiction

        # UNSAT — find the core
        core = self._extract_core(n_vars, clauses)
        if core is None:
            core = clauses  # fallback: whole thing is the core

        # Classify the contradiction
        level = self._classify(core, text)

        contradictions.append(Contradiction(
            level=level,
            description=self._describe(level, len(core), len(clauses)),
            clause_indices=list(range(len(core))),
            unsat_core=core,
            resolution_hint=self._suggest_resolution(level),
        ))

        # Check for multiple independent contradictions
        # by removing the core and checking if remainder is also UNSAT
        if len(core) < len(clauses):
            core_set = {tuple(c) for c in core}
            remainder = [c for c in clauses if tuple(c) not in core_set]
            if remainder:
                sat2, _ = solve_cnf(n_vars, remainder, budget=1000)
                if not sat2:
                    # Multiple contradictions
                    sub_core = self._extract_core(n_vars, remainder)
                    if sub_core:
                        level2 = self._classify(sub_core, text)
                        contradictions.append(Contradiction(
                            level=level2,
                            description=self._describe(level2, len(sub_core), len(remainder)),
                            clause_indices=list(range(len(core), len(core) + len(sub_core))),
                            unsat_core=sub_core,
                            resolution_hint=self._suggest_resolution(level2),
                        ))

        return contradictions

    def _extract_core(
        self, n_vars: int, clauses: List[List[int]], budget: int = 2000
    ) -> Optional[List[List[int]]]:
        """Extract minimal UNSAT core via iterative deletion."""
        sat, _ = solve_cnf(n_vars, clauses, budget=budget)
        if sat:
            return None

        core = list(clauses)
        i = 0
        while i < len(core):
            candidate = core[:i] + core[i + 1:]
            if not candidate:
                break
            sat, _ = solve_cnf(n_vars, candidate, budget=budget)
            if not sat:
                core = candidate
            else:
                i += 1

        return core

    @staticmethod
    def _classify(core: List[List[int]], text: str) -> ContradictionLevel:
        """
        Classify contradiction depth based on core structure.

        SURFACE:    Core has ≤ 2 clauses (direct A ∧ ¬A)
        STRUCTURAL: Core has 3-10 clauses (requires reasoning chain)
        DEEP:       Core has >10 clauses or involves self-reference patterns
        """
        if len(core) <= 2:
            # Check for direct negation: [x] and [-x]
            if len(core) == 2:
                c1, c2 = core
                if len(c1) == 1 and len(c2) == 1 and c1[0] == -c2[0]:
                    return ContradictionLevel.SURFACE
            return ContradictionLevel.SURFACE

        # Moral domain patterns — always DEEP (irreversible O₀ transition;
        # no evolution operator resolves these contradictions)
        text_lower = text.lower()
        if any(p in text_lower for p in _MORAL_DOMAIN_PATTERNS):
            return ContradictionLevel.DEEP

        # Check for self-reference indicators in text
        self_ref_patterns = [
            "this statement", "itself", "self-referent",
            "the liar", "i am lying", "paradox",
            "russell", "gödel", "incompleteness",
        ]
        has_self_ref = any(p in text_lower for p in self_ref_patterns)

        if has_self_ref or len(core) > 10:
            return ContradictionLevel.DEEP

        return ContradictionLevel.STRUCTURAL

    @staticmethod
    def _describe(level: ContradictionLevel, core_size: int, total: int) -> str:
        prefix = {
            ContradictionLevel.SURFACE: "Surface contradiction",
            ContradictionLevel.STRUCTURAL: "Structural contradiction",
            ContradictionLevel.DEEP: "Deep paradox",
            ContradictionLevel.NONE: "No contradiction",
        }
        return f"{prefix[level]}: {core_size}/{total} clauses in UNSAT core"

    @staticmethod
    def _suggest_resolution(level: ContradictionLevel) -> str:
        strategies = {
            ContradictionLevel.SURFACE: "negation_elimination",
            ContradictionLevel.STRUCTURAL: "decompose_and_case_split",
            ContradictionLevel.DEEP: "axiom_introduction",
            ContradictionLevel.NONE: "none",
        }
        return strategies[level]


# ── Paradox Tolerance Scoring ────────────────────────────────────────────────

class ParadoxScorer:
    """
    Score how contradictory a text is — the "paradox tolerance" metric.

    Score ∈ [0, 1]:
      0.0 = fully consistent, no contradictions
      0.5 = structural contradictions present but resolvable
      1.0 = deep paradox, irreducible under current axioms

    The score is NOT a quality metric. High paradox tolerance can be
    desirable — it means the text is operating at the frontier of
    what the current logic can handle. That's where evolution happens.
    """

    def __init__(self, gate: Optional[VerificationGate] = None):
        self.detector = ContradictionDetector(gate)
        self.gate = gate or get_gate()

    def score(self, text: str, domain: Optional[str] = None) -> ParadoxAnalysis:
        """Full paradox analysis."""
        # Verify first
        result = self.gate.verify(text, domain=domain or "logic")

        # Detect contradictions
        contradictions = self.detector.detect(text, domain=domain)

        if not contradictions:
            return ParadoxAnalysis(
                contradictions=[],
                tolerance_score=0.0,
                attractor_state=AttractorState.STABLE,
                verification=result,
                suggested_strategy="none",
            )

        # Compute tolerance score
        weights = {
            ContradictionLevel.SURFACE: 0.2,
            ContradictionLevel.STRUCTURAL: 0.5,
            ContradictionLevel.DEEP: 1.0,
            ContradictionLevel.NONE: 0.0,
        }
        total_weight = sum(weights[c.level] for c in contradictions)
        tolerance = min(1.0, total_weight / max(len(contradictions), 1))

        # Determine attractor state
        if any(c.level == ContradictionLevel.DEEP for c in contradictions):
            attractor = AttractorState.FIXED_POINT
            strategy = "axiom_introduction"
        elif all(c.is_resolvable for c in contradictions):
            attractor = AttractorState.STABLE
            strategy = "decompose_and_resolve"
        else:
            attractor = AttractorState.OSCILLATING
            strategy = "case_split_with_lemma_injection"

        return ParadoxAnalysis(
            contradictions=contradictions,
            tolerance_score=tolerance,
            attractor_state=attractor,
            verification=result,
            suggested_strategy=strategy,
        )


# ── Pigeonhole Generator ─────────────────────────────────────────────────────

def pigeonhole_cnf(n_pigeons: int, n_holes: int) -> Tuple[int, List[List[int]]]:
    """
    Generate the pigeonhole principle as a CNF formula.

    PHP(n+1, n): n+1 pigeons, n holes.
    Variable p_{i,j} = pigeon i is in hole j.
    Variables: n_pigeons * n_holes, 1-indexed.

    Clauses:
    1) Each pigeon must be in some hole:
       (p_{i,1} ∨ p_{i,2} ∨ ... ∨ p_{i,n_holes})  for each pigeon i

    2) No two pigeons in same hole:
       (¬p_{i,j} ∨ ¬p_{k,j})  for each hole j, each pair i<k

    When n_pigeons > n_holes, this is UNSATISFIABLE.
    This is the canonical hard problem for resolution-based SAT solvers.
    Resolution proofs require exponential length.
    """
    n_vars = n_pigeons * n_holes
    clauses: List[List[int]] = []

    def var(pigeon: int, hole: int) -> int:
        """1-indexed variable for pigeon i in hole j."""
        return pigeon * n_holes + hole + 1

    # Each pigeon in at least one hole
    for i in range(n_pigeons):
        clause = [var(i, j) for j in range(n_holes)]
        clauses.append(clause)

    # No two pigeons in same hole
    for j in range(n_holes):
        for i in range(n_pigeons):
            for k in range(i + 1, n_pigeons):
                clauses.append([-var(i, j), -var(k, j)])

    return n_vars, clauses


def test_paradox_hardness(n: int = 5, budget: int = 5000) -> Dict[str, Any]:
    """
    Test SAT solver against PHP(n+1, n) — the canonical hard instance.

    Returns timing and conflict count. This benchmarks how the solver
    handles provably hard paradoxes, which directly maps to how the
    system handles unresolved (PARADOX/TIMEOUT) cases.
    """
    import time

    n_vars, clauses = pigeonhole_cnf(n + 1, n)

    t0 = time.perf_counter()
    sat, _ = solve_cnf(n_vars, clauses, budget=budget)
    elapsed = (time.perf_counter() - t0) * 1000

    return {
        "n_pigeons": n + 1,
        "n_holes": n,
        "n_vars": n_vars,
        "n_clauses": len(clauses),
        "satisfiable": sat,
        "elapsed_ms": elapsed,
        "expected_unsat": True,
        "is_correct": not sat,  # PHP(n+1,n) should always be UNSAT
    }


# ── Convenience ───────────────────────────────────────────────────────────────

_default_scorer: Optional[ParadoxScorer] = None


def get_scorer() -> ParadoxScorer:
    global _default_scorer
    if _default_scorer is None:
        _default_scorer = ParadoxScorer()
    return _default_scorer


def analyze_paradox(text: str, domain: Optional[str] = None) -> ParadoxAnalysis:
    """Quick paradox analysis of text."""
    return get_scorer().score(text, domain=domain)


def detect_contradictions(text: str, domain: Optional[str] = None) -> List[Contradiction]:
    """Quick contradiction detection."""
    return get_scorer().detector.detect(text, domain=domain)
