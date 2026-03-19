"""
Verification Gate — The First Step of Everything
==================================================
Nothing proceeds without verification. This module is the spine
of the entire system.

Architecture:
    INPUT → extract_constraints() → SAT solve → VerificationResult
                                                    ↓
                                            VERIFIED      → proceed
                                            CONTRADICTION → discard / retry
                                            PARADOX       → resolve (structural)
                                            TIMEOUT       → re-solve or escalate

Four-valued verdict:
    TRUE     (SAT)             → VERIFIED, constraints satisfiable
    FALSE    (UNSAT)           → CONTRADICTION, provably inconsistent
    SAT ∧ UNSAT (conjunction)  → PARADOX, structural conflict
    UNKNOWN  (budget exceeded) → TIMEOUT, solver resource limit

Every module in the system calls verify() before acting:
    - Generation → verify each step before emitting
    - Proof evolution → verify candidate lemmas before accepting
    - Signal processing → verify quantized constraints before accepting

Constraint extractors turn domain-specific content into 3-SAT:
    - Code → control flow + type constraints → CNF
    - Math → equation consistency → CNF
    - Proofs → proof obligations → CNF
    - Reasoning → logical structure → CNF

This is public-domain algorithmic work. The insight is architectural:
SAT-as-gatekeeper, not SAT-as-afterthought.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, Union

try:
    import numpy as np
    _HAS_NUMPY = True
except ImportError:
    _HAS_NUMPY = False

from .sat import (
    SATSolver,
    ZONE_REWARDS,
    SAT_COHERENT,
    SAT_PLATEAU_LO,
    pos_lit,
    neg_lit,
    solve_cnf,
    sat_score,
)
if _HAS_NUMPY:
    try:
        from .signal_to_3sat import (
            MultimodalTo3SAT,
            SignalConstraintExtractor,
            TimeSeriesTo3SAT,
            AudioTo3SAT,
            ImageTo3SAT,
            VideoTo3SAT,
        )
    except ImportError:
        _HAS_NUMPY = False

TEXT_DOMAIN_ALIASES = [
    "med",
    "law",
    "text",
    "bio",
    "cyber",
    "chem",
    "nano",
    "phys",
    "quantum",
    "socio",
    "econ",
    "anthro",
    "prehistory",
    "history",
    "government",
    "philosophy",
    "meta_sciences",
    "hypercomplexes",
    "sempiternalities",
]


# ── Four-Valued Verdict ──────────────────────────────────────────────────────

class Verdict(Enum):
    """The four possible outcomes of verification.

    VERIFIED      — SAT: constraints satisfiable, proceed.
    CONTRADICTION — UNSAT: provably inconsistent, discard.
    PARADOX       — Individually SAT groups whose conjunction is UNSAT.
                    Structural property of the constraints, not the solver.
    TIMEOUT       — Solver exhausted conflict budget without resolving.
                    Operational property of the solver, not the constraints.
    """
    VERIFIED      = auto()
    CONTRADICTION = auto()
    PARADOX       = auto()
    TIMEOUT       = auto()

    # Back-compat aliases ─────────────────────────────────────────────────
    @classmethod
    def _missing_(cls, value):
        """Support old names during migration."""
        aliases = {"REJECTED": cls.CONTRADICTION}
        if isinstance(value, str) and value in aliases:
            return aliases[value]
        return None

# Keep importable aliases for code that hasn't migrated yet
Verdict.REJECTED = Verdict.CONTRADICTION  # type: ignore[attr-defined]


@dataclass
class VerificationResult:
    """Complete result of a verification pass."""
    verdict: Verdict
    sat_ratio: float                         # fraction of constraint groups satisfied
    zone: str                                # "coherent" | "plateau" | "incoherent" | "paradox" | "timeout"
    elapsed_ms: float                        # wall-clock time for verification
    n_constraints: int                       # total constraint groups checked
    n_satisfied: int                         # how many were SAT
    n_refuted: int                           # how many were UNSAT
    n_timeout: int                           # how many exhausted conflict budget
    n_paradox: int = 0                       # how many involved in structural paradox
    details: Dict[str, Any] = field(default_factory=dict)

    @property
    def reward(self) -> float:
        return ZONE_REWARDS.get(self.zone, -1.0)

    @property
    def is_verified(self) -> bool:
        return self.verdict == Verdict.VERIFIED

    @property
    def is_contradiction(self) -> bool:
        return self.verdict == Verdict.CONTRADICTION

    @property
    def is_paradox(self) -> bool:
        return self.verdict == Verdict.PARADOX

    @property
    def is_timeout(self) -> bool:
        return self.verdict == Verdict.TIMEOUT

    # Back-compat aliases
    @property
    def n_frontier(self) -> int:
        return self.n_timeout + self.n_paradox

    @property
    def is_frontier(self) -> bool:
        return self.verdict in (Verdict.PARADOX, Verdict.TIMEOUT)

    @property
    def is_rejected(self) -> bool:
        return self.verdict == Verdict.CONTRADICTION


# ── Central Verification Gate ─────────────────────────────────────────────────

class VerificationGate:
    """
    The gatekeeper. Everything passes through here.

    Usage:
        gate = VerificationGate()
        gate.register_extractor("code", code_to_constraints)
        gate.register_extractor("math", math_to_constraints)

        result = gate.verify(content, domain="code")
        if result.is_verified:
            proceed(content)
        elif result.is_contradiction:
            discard(content)
        elif result.is_paradox:
            resolve_structural(content, result)
        else:  # TIMEOUT
            escalate(content, result)
    """

    def __init__(
        self,
        paradox_threshold: int = 500,
        coherence_threshold: float = SAT_COHERENT,
        frontier_threshold: float = SAT_PLATEAU_LO,
    ):
        self.paradox_threshold = paradox_threshold
        self.coherence_threshold = coherence_threshold
        self.frontier_threshold = frontier_threshold
        self._extractors: Dict[str, ConstraintExtractor] = {}

        # Register built-in extractors
        self._extractors["logic"] = LogicConstraintExtractor()
        self._extractors["code"] = CodeConstraintExtractor()
        self._extractors["math"] = MathConstraintExtractor()
        self._extractors["proof"] = ProofConstraintExtractor()
        self._extractors["market"] = MarketConstraintExtractor()

        # Domain aliases — text-only domains delegate to logic extraction.
        logic_ext = self._extractors["logic"]
        for alias in TEXT_DOMAIN_ALIASES:
            self._extractors[alias] = logic_ext

        # Signal extractors — continuous modalities (require numpy)
        self._signal_extractors: Dict[str, Any] = {}
        self._multimodal = None
        if _HAS_NUMPY:
            self._signal_extractors["ts"] = TimeSeriesTo3SAT()
            self._signal_extractors["audio"] = AudioTo3SAT()
            self._signal_extractors["image"] = ImageTo3SAT()
            self._signal_extractors["video"] = VideoTo3SAT()
            self._multimodal = MultimodalTo3SAT()

    def register_extractor(self, domain: str, extractor: "ConstraintExtractor") -> None:
        self._extractors[domain] = extractor

    def register_signal_extractor(self, modality: str, extractor: SignalConstraintExtractor) -> None:
        self._signal_extractors[modality] = extractor

    def verify(
        self,
        content: str,
        domain: str = "logic",
        extra_constraints: Optional[List[List[List[int]]]] = None,
    ) -> VerificationResult:
        """
        Verify content. This is THE function. Everything calls this.

        1. Extract constraints from content using domain-specific extractor
        2. Run SAT on each constraint group
        3. Classify result as VERIFIED / CONTRADICTION / PARADOX / TIMEOUT
        4. Return full VerificationResult
        """
        t0 = time.perf_counter()

        extractor = self._extractors.get(domain)
        if extractor is None:
            raise ValueError(f"No extractor registered for domain '{domain}'. "
                           f"Available: {list(self._extractors.keys())}")

        n_vars, groups = extractor.extract(content)
        if extra_constraints:
            groups.extend(extra_constraints)

        return self._solve_groups(n_vars, groups, t0)

    def verify_tokens(
        self,
        token_ids: List[int],
        constraint_fn: Callable[[List[int]], Tuple[int, List[List[List[int]]]]],
    ) -> VerificationResult:
        """
        Verify a token sequence using a custom constraint function.
        Used during generation and training.
        """
        t0 = time.perf_counter()
        n_vars, groups = constraint_fn(token_ids)

        if not groups:
            elapsed = (time.perf_counter() - t0) * 1000
            return VerificationResult(
                verdict=Verdict.VERIFIED,
                sat_ratio=1.0, zone="coherent",
                elapsed_ms=elapsed,
                n_constraints=0, n_satisfied=0,
                n_refuted=0, n_timeout=0,
            )

        ratio, zone, n_timeout = sat_score(n_vars, groups, paradox_threshold=self.paradox_threshold)
        elapsed = (time.perf_counter() - t0) * 1000

        # Four-valued verdict — strictly correct:
        #   TIMEOUT       = solver exhausted conflict budget (operational)
        #   VERIFIED      = ratio above coherence threshold AND no timeout groups
        #   CONTRADICTION = ratio below threshold, all groups resolved (provably UNSAT)
        #   Plateau with n_timeout=0 is a clean measurement → CONTRADICTION
        if n_timeout > 0:
            verdict = Verdict.TIMEOUT
        elif ratio >= self.coherence_threshold:
            verdict = Verdict.VERIFIED
        else:
            verdict = Verdict.CONTRADICTION

        n_groups = len(groups)
        n_sat = int(ratio * n_groups)

        return VerificationResult(
            verdict=verdict,
            sat_ratio=ratio, zone=zone,
            elapsed_ms=elapsed,
            n_constraints=n_groups,
            n_satisfied=n_sat,
            n_refuted=n_groups - n_sat,
            n_timeout=n_timeout,
        )

    def verify_batch(
        self,
        contents: List[str],
        domain: str = "logic",
    ) -> List[VerificationResult]:
        """Verify a batch — each element independently gated."""
        return [self.verify(c, domain=domain) for c in contents]

    def gate(
        self,
        content: str,
        domain: str = "logic",
        on_unresolved: str = "pass",  # "pass" | "block" | "flag"
        on_frontier: str | None = None,  # back-compat alias
    ) -> Tuple[bool, VerificationResult]:
        """
        Boolean gate: should this content proceed?

        on_unresolved controls what happens for PARADOX / TIMEOUT:
          "pass"  → unresolved content proceeds (optimistic)
          "block" → unresolved content blocked (conservative)
          "flag"  → unresolved content proceeds but flagged
        """
        if on_frontier is not None:
            on_unresolved = on_frontier  # back-compat
        result = self.verify(content, domain=domain)

        if result.is_verified:
            return True, result
        elif result.is_contradiction:
            return False, result
        else:  # PARADOX or TIMEOUT
            if on_unresolved == "pass":
                return True, result
            elif on_unresolved == "block":
                return False, result
            else:  # "flag"
                return True, result

    # ── Signal Verification (continuous modalities) ──────────────────────────

    def _solve_groups(
        self, n_vars: int, groups: List[List[List[int]]], t0: float,
    ) -> VerificationResult:
        """Shared SAT-solve-and-classify for any constraint source."""
        if not groups:
            elapsed = (time.perf_counter() - t0) * 1000
            return VerificationResult(
                verdict=Verdict.VERIFIED, sat_ratio=1.0, zone="coherent",
                elapsed_ms=elapsed, n_constraints=0, n_satisfied=0,
                n_refuted=0, n_timeout=0,
            )

        n_sat = n_unsat = n_timeout = 0
        group_results = []

        for group in groups:
            solver = SATSolver()
            solver.new_vars(n_vars)
            ok = True
            for clause_lits in group:
                internal = []
                for lit in clause_lits:
                    if lit > 0:
                        internal.append(pos_lit(lit - 1))
                    else:
                        internal.append(neg_lit(-lit - 1))
                if not solver.add_clause(internal):
                    ok = False
                    break
            if not ok:
                n_unsat += 1
                group_results.append("UNSAT")
                continue
            result = solver.solve(budget=self.paradox_threshold)
            if result:
                n_sat += 1
                group_results.append("SAT")
            elif solver.conflicts >= self.paradox_threshold > 0:
                n_timeout += 1
                group_results.append("TIMEOUT")
            else:
                n_unsat += 1
                group_results.append("UNSAT")

        total = len(groups)
        ratio = n_sat / total if total > 0 else 1.0

        # Four-valued classification:
        #   TIMEOUT       — at least one group exhausted conflict budget
        #   PARADOX       — each group individually SAT, but conjunction UNSAT
        #   VERIFIED      — ratio above coherence threshold
        #   CONTRADICTION — provably UNSAT (some groups refuted, none timed out)
        n_paradox = 0
        if n_timeout > 0:
            verdict = Verdict.TIMEOUT
            zone = "timeout"
        elif ratio >= self.coherence_threshold:
            # All/most groups individually SAT — check if their conjunction holds
            if n_sat == total and total > 1:
                # Merge all clauses from all groups into a single formula
                combined_solver = SATSolver()
                combined_solver.new_vars(n_vars)
                combined_ok = True
                for group in groups:
                    for clause_lits in group:
                        internal = []
                        for lit in clause_lits:
                            if lit > 0:
                                internal.append(pos_lit(lit - 1))
                            else:
                                internal.append(neg_lit(-lit - 1))
                        if not combined_solver.add_clause(internal):
                            combined_ok = False
                            break
                    if not combined_ok:
                        break
                if combined_ok:
                    combined_result = combined_solver.solve(budget=self.paradox_threshold)
                    if not combined_result and combined_solver.conflicts < self.paradox_threshold:
                        # Individually SAT, jointly UNSAT → PARADOX
                        verdict = Verdict.PARADOX
                        zone = "paradox"
                        n_paradox = total
                    else:
                        verdict = Verdict.VERIFIED
                        zone = "coherent"
                else:
                    # Conjunction trivially UNSAT via empty clause
                    verdict = Verdict.PARADOX
                    zone = "paradox"
                    n_paradox = total
            else:
                verdict = Verdict.VERIFIED
                zone = "coherent"
        else:
            verdict = Verdict.CONTRADICTION
            zone = "incoherent" if ratio < self.frontier_threshold else "plateau"

        elapsed = (time.perf_counter() - t0) * 1000
        return VerificationResult(
            verdict=verdict, sat_ratio=ratio, zone=zone,
            elapsed_ms=elapsed, n_constraints=total,
            n_satisfied=n_sat, n_refuted=n_unsat, n_timeout=n_timeout,
            n_paradox=n_paradox,
            details={"group_results": group_results, "n_vars": n_vars},
        )

    def _require_numpy(self, method: str) -> None:
        if not _HAS_NUMPY:
            raise ImportError(
                f"{method} requires numpy. pip install numpy"
            )

    def verify_signal(
        self,
        signal: "np.ndarray",
        modality: str = "ts",
        metadata: Optional[Dict[str, Any]] = None,
        extra_constraints: Optional[List[List[List[int]]]] = None,
    ) -> VerificationResult:
        """
        Verify a continuous signal through the SAT gate.

        The Ed Thorp gate: signal → quantize → 3-SAT → SAT → verdict.

        modality: "ts" | "audio" | "image" | "video"
        """
        self._require_numpy("verify_signal")
        t0 = time.perf_counter()

        extractor = self._signal_extractors.get(modality)
        if extractor is None:
            raise ValueError(
                f"No signal extractor for modality '{modality}'. "
                f"Available: {list(self._signal_extractors.keys())}"
            )

        n_vars, groups = extractor.extract_from_signal(signal, metadata)
        if extra_constraints:
            groups.extend(extra_constraints)

        return self._solve_groups(n_vars, groups, t0)

    def verify_multimodal(
        self,
        signals: Dict[str, "np.ndarray"],
        metadata: Optional[Dict[str, Any]] = None,
        extra_constraints: Optional[List[List[List[int]]]] = None,
    ) -> VerificationResult:
        """
        Verify multiple modalities simultaneously through a unified SAT gate.

        signals: {"ts": array, "audio": array, "image": array, "video": array}
        Constraints from all modalities are merged, cross-modal constraints
        are generated, then a single SAT pass decides the verdict.
        """
        self._require_numpy("verify_multimodal")
        t0 = time.perf_counter()
        n_vars, groups = self._multimodal.extract(signals, metadata)
        if extra_constraints:
            groups.extend(extra_constraints)
        return self._solve_groups(n_vars, groups, t0)

    def verify_signal_batch(
        self,
        signals: List["np.ndarray"],
        modality: str = "ts",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[VerificationResult]:
        """Verify a batch of signals — each independently gated."""
        return [self.verify_signal(s, modality=modality, metadata=metadata) for s in signals]

    def gate_signal(
        self,
        signal: "np.ndarray",
        modality: str = "ts",
        metadata: Optional[Dict[str, Any]] = None,
        on_unresolved: str = "pass",
        on_frontier: str | None = None,  # back-compat alias
    ) -> Tuple[bool, VerificationResult]:
        """Boolean gate for continuous signals."""
        if on_frontier is not None:
            on_unresolved = on_frontier
        result = self.verify_signal(signal, modality=modality, metadata=metadata)
        if result.is_verified:
            return True, result
        elif result.is_contradiction:
            return False, result
        else:
            return on_unresolved != "block", result

    def gate_multimodal(
        self,
        signals: Dict[str, np.ndarray],
        metadata: Optional[Dict[str, Any]] = None,
        on_unresolved: str = "pass",
        on_frontier: str | None = None,  # back-compat alias
    ) -> Tuple[bool, VerificationResult]:
        """Boolean gate for multimodal inputs."""
        if on_frontier is not None:
            on_unresolved = on_frontier
        result = self.verify_multimodal(signals, metadata=metadata)
        if result.is_verified:
            return True, result
        elif result.is_contradiction:
            return False, result
        else:
            return on_unresolved != "block", result


# ── Constraint Extractors ─────────────────────────────────────────────────────

class ConstraintExtractor:
    """Base class for domain-specific constraint extraction."""

    def extract(self, content: str) -> Tuple[int, List[List[List[int]]]]:
        """
        Extract propositional constraints from content.

        Returns:
            n_vars: number of propositional variables
            groups: list of constraint groups, each group is a CNF formula
                    (list of clauses, each clause is list of signed ints)
        """
        raise NotImplementedError


class LogicConstraintExtractor(ConstraintExtractor):
    """
    Extract logical constraints from natural language / structured text.

    Looks for:
    - if/then implications → (¬A ∨ B)
    - and/or connectives
    - negations (not, never, no)
    - contradictions (X and not-X)
    """

    # Patterns for logical connectives
    IF_THEN = re.compile(r"if\s+(.+?)\s+then\s+(.+?)(?:\.|$)", re.IGNORECASE)
    AND_PAT = re.compile(r"\band\b", re.IGNORECASE)
    OR_PAT = re.compile(r"\bor\b", re.IGNORECASE)
    NOT_PAT = re.compile(r"\b(?:not|never|no|cannot|won't|doesn't|isn't)\b", re.IGNORECASE)

    def extract(self, content: str) -> Tuple[int, List[List[List[int]]]]:
        statements = [s.strip() for s in re.split(r'[.;!\n]', content) if s.strip()]
        if not statements:
            return 0, []

        # Assign a variable to each unique atomic proposition
        atoms: Dict[str, int] = {}
        var_counter = 0

        # Strip stop-words so "the patient has fever" and "fever" share a var.
        _SW = re.compile(
            r"\b(?:the|a|an|is|are|was|were|has|have|had|patient|subject|"
            r"person|it|this|that|they|he|she|we)\b",
            re.IGNORECASE,
        )

        def get_var(prop: str) -> int:
            nonlocal var_counter
            prop = prop.strip().lower()
            # Strip negation to get base proposition
            clean = self.NOT_PAT.sub("", prop).strip()
            # Normalise: remove stop-words so "patient has fever" == "fever"
            clean_norm = re.sub(r"\s+", "_", _SW.sub("", clean).strip())
            clean_norm = re.sub(r"[^a-z0-9_]", "", clean_norm).strip("_") or clean
            if clean_norm not in atoms:
                var_counter += 1
                atoms[clean_norm] = var_counter
            is_negated = bool(self.NOT_PAT.search(prop))
            v = atoms[clean_norm]
            return -v if is_negated else v

        groups: List[List[List[int]]] = []

        for stmt in statements:
            clauses: List[List[int]] = []

            # Check for if/then
            m = self.IF_THEN.search(stmt)
            if m:
                ante = get_var(m.group(1))
                cons = get_var(m.group(2))
                # if A then B → (¬A ∨ B)
                clauses.append([-ante, cons])
            elif self.AND_PAT.search(stmt):
                # "A and B" → each is a unit clause
                parts = self.AND_PAT.split(stmt)
                for part in parts:
                    v = get_var(part)
                    clauses.append([v])
            elif self.OR_PAT.search(stmt):
                # "A or B" → single clause (A ∨ B)
                parts = self.OR_PAT.split(stmt)
                clause = [get_var(p) for p in parts]
                clauses.append(clause)
            else:
                # Single proposition
                v = get_var(stmt)
                clauses.append([v])

            if clauses:
                groups.append(clauses)

        return var_counter, groups


class CodeConstraintExtractor(ConstraintExtractor):
    """
    Extract constraints from code snippets.

    Looks for:
    - assert statements → unit clauses
    - if/elif/else → implications
    - return type consistency
    - Variable assignments → equality constraints
    - Function calls → precondition constraints
    """

    ASSERT_PAT = re.compile(r"assert\s+(.+?)(?:\s*,|\s*$|\s*#)", re.MULTILINE)
    # Negative lookbehind prevents matching the 'if' inside 'elif'.
    IF_PAT = re.compile(r"(?<![a-zA-Z])if\s+(.+?):", re.MULTILINE)
    ELIF_PAT = re.compile(r"elif\s+(.+?):", re.MULTILINE)
    ASSIGN_PAT = re.compile(r"(\w+)\s*=\s*(.+?)$", re.MULTILINE)
    RETURN_PAT = re.compile(r"return\s+(.+?)$", re.MULTILINE)
    COMPARE_PAT = re.compile(r"(\w+)\s*(==|!=|<=|>=|<|>)\s*(\w+)")

    def extract(self, content: str) -> Tuple[int, List[List[List[int]]]]:
        atoms: Dict[str, int] = {}
        var_counter = 0

        def get_var(prop: str) -> int:
            nonlocal var_counter
            prop = prop.strip()
            if prop not in atoms:
                var_counter += 1
                atoms[prop] = var_counter
            return atoms[prop]

        groups: List[List[List[int]]] = []

        # Assertions → must be true (unit clauses)
        for m in self.ASSERT_PAT.finditer(content):
            expr = m.group(1).strip()
            # Handle "not" in assertions
            if expr.startswith("not "):
                v = get_var(expr[4:].strip())
                groups.append([[-v]])
            else:
                v = get_var(expr)
                groups.append([[v]])

        # Comparisons → equality/inequality constraints
        for m in self.COMPARE_PAT.finditer(content):
            left, op, right = m.group(1), m.group(2), m.group(3)
            lv = get_var(f"{left}_valid")
            rv = get_var(f"{right}_valid")
            if op == "==":
                # Both must agree: (¬L ∨ R) ∧ (L ∨ ¬R)
                groups.append([[-lv, rv], [lv, -rv]])
            elif op == "!=":
                # Must differ: (L ∨ R) ∧ (¬L ∨ ¬R)
                groups.append([[lv, rv], [-lv, -rv]])

        # If/elif chains → mutual exclusion
        if_vars = []
        for m in self.IF_PAT.finditer(content):
            v = get_var(f"if_{m.group(1).strip()}")
            if_vars.append(v)
        for m in self.ELIF_PAT.finditer(content):
            v = get_var(f"elif_{m.group(1).strip()}")
            if_vars.append(v)

        if len(if_vars) > 1:
            # At most one branch taken: for each pair, ¬A ∨ ¬B
            # Note: NOT adding "at least one" — if/elif branches need not fire.
            for i in range(len(if_vars)):
                for j in range(i + 1, len(if_vars)):
                    groups.append([[-if_vars[i], -if_vars[j]]])

        return var_counter, groups


class MathConstraintExtractor(ConstraintExtractor):
    """
    Extract constraints from mathematical expressions.

    Looks for:
    - Equations (a = b) → equivalence
    - Inequalities → ordering constraints
    - Quantifiers (for all, exists)
    - Consistency across multiple equations
    """

    EQ_PAT = re.compile(r"(\w+)\s*=\s*(\w+)")
    INEQ_PAT = re.compile(r"(\w+)\s*([<>≤≥])\s*(\w+)")
    FORALL_PAT = re.compile(r"(?:for all|∀)\s+(\w+)", re.IGNORECASE)
    EXISTS_PAT = re.compile(r"(?:exists|∃)\s+(\w+)", re.IGNORECASE)

    def extract(self, content: str) -> Tuple[int, List[List[List[int]]]]:
        atoms: Dict[str, int] = {}
        var_counter = 0

        def get_var(prop: str) -> int:
            nonlocal var_counter
            prop = prop.strip()
            if prop not in atoms:
                var_counter += 1
                atoms[prop] = var_counter
            return atoms[prop]

        groups: List[List[List[int]]] = []

        # Equations → biconditional
        for m in self.EQ_PAT.finditer(content):
            left, right = m.group(1), m.group(2)
            lv = get_var(left)
            rv = get_var(right)
            # A ↔ B: (¬A ∨ B) ∧ (A ∨ ¬B)
            groups.append([[-lv, rv], [lv, -rv]])

        # Inequalities → implication chains
        for m in self.INEQ_PAT.finditer(content):
            left, op, right = m.group(1), m.group(2), m.group(3)
            lv = get_var(f"{left}_bounded")
            rv = get_var(f"{right}_bounded")
            # a < b implies a is bounded above, b is bounded below
            groups.append([[lv], [rv]])

        # For all → universal constraint (must hold)
        for m in self.FORALL_PAT.finditer(content):
            v = get_var(f"forall_{m.group(1)}")
            groups.append([[v]])

        # Exists → existential (at least one witness)
        exists_vars = []
        for m in self.EXISTS_PAT.finditer(content):
            v = get_var(f"exists_{m.group(1)}")
            exists_vars.append(v)
        if exists_vars:
            groups.append([exists_vars])  # disjunction: at least one exists (one clause)

        return var_counter, groups


class ProofConstraintExtractor(ConstraintExtractor):
    """
    Extract constraints from formal/semi-formal proofs.

    This is the critical extractor for proof evolution.
    Proof obligations → 3-SAT. The mapping:

    - Axioms → unit clauses (must be true)
    - Lemmas → implications (if premises then conclusion)
    - Theorems → conjunction of lemma implications
    - Contradictions → A ∧ ¬A detected → CONTRADICTION
    - Proof steps → each step is a constraint group

    Supports:
    - Natural language proofs ("assume... therefore...")
    - Semi-formal ("let X. then Y. by Z, W.")
    - Lean4-style tactics (sorry/exact/apply/intro)
    """

    ASSUME_PAT = re.compile(r"(?:assume|let|given|suppose)\s+(.+?)(?:\.|,|$)", re.IGNORECASE | re.MULTILINE)
    THEREFORE_PAT = re.compile(r"(?:therefore|hence|thus|so|then|conclude)\s+(.+?)(?:\.|$)", re.IGNORECASE | re.MULTILINE)
    BY_PAT = re.compile(r"(?:by|from|using|via)\s+(.+?)(?:\.|,|$)", re.IGNORECASE | re.MULTILINE)
    # Only match Lean4-style bare tactics, not English uses of these words.
    # "contradiction" and "absurd" as standalone proof tactics (one per line).
    CONTRA_PAT = re.compile(r"^\s*(?:contradiction|absurd)\s*$", re.IGNORECASE | re.MULTILINE)
    QED_PAT = re.compile(r"(?:qed|□|∎|proved|done)", re.IGNORECASE)

    # Lean4-style
    # Match "sorry" only in tactic position:
    #   - alone on a line (standalone tactic)
    #   - after "by" or "exact" (tactic combinators)
    #   - after a period with optional whitespace (statement-final tactic)
    # This prevents English "I am sorry" from injecting a false contradiction.
    SORRY_PAT = re.compile(
        r"(?:^\s*sorry\s*$"               # alone on its own line
        r"|(?:by|exact)\s+sorry\b"        # tactic: "by sorry" / "exact sorry"
        r"|\.\s*sorry\b)",                # statement-final: ". sorry"
        re.IGNORECASE | re.MULTILINE,
    )
    EXACT_PAT = re.compile(r"exact\s+(.+?)$", re.MULTILINE)
    APPLY_PAT = re.compile(r"apply\s+(.+?)$", re.MULTILINE)
    HAVE_PAT = re.compile(r"have\s+(\w+)\s*:\s*(.+?)\s*:=", re.MULTILINE)

    def extract(self, content: str) -> Tuple[int, List[List[List[int]]]]:
        atoms: Dict[str, int] = {}
        var_counter = 0

        def get_var(prop: str) -> int:
            nonlocal var_counter
            prop = prop.strip().lower()
            if prop not in atoms:
                var_counter += 1
                atoms[prop] = var_counter
            return atoms[prop]

        groups: List[List[List[int]]] = []

        # Assumptions → axioms (unit clauses, must be true)
        assumptions = []
        for m in self.ASSUME_PAT.finditer(content):
            v = get_var(m.group(1))
            groups.append([[v]])
            assumptions.append(v)

        # Conclusions → must follow from assumptions
        for m in self.THEREFORE_PAT.finditer(content):
            conclusion = get_var(m.group(1))
            if assumptions:
                # Each assumption implies the conclusion:
                # (¬A₁ ∨ C) for each assumption A₁
                for a in assumptions:
                    groups.append([[-a, conclusion]])
            else:
                # Bare conclusion — must be provable
                groups.append([[conclusion]])

        # "By X" → X must be established (true)
        for m in self.BY_PAT.finditer(content):
            justification = m.group(1).strip()
            # Split on commas for multiple justifications
            for j in justification.split(","):
                v = get_var(j.strip())
                groups.append([[v]])

        # Contradiction → special handling
        if self.CONTRA_PAT.search(content):
            # Add a deliberate contradiction: A ∧ ¬A
            # This forces UNSAT → CONTRADICTION verdict → evolution trigger
            contra_var = get_var("__contradiction__")
            groups.append([[contra_var]])
            groups.append([[-contra_var]])

        # Lean4: sorry → incomplete proof → contradiction (forces evolution)
        if self.SORRY_PAT.search(content):
            sorry_var = get_var("__sorry_incomplete__")
            groups.append([[sorry_var]])
            groups.append([[-sorry_var]])

        # Lean4: have X : T := ... → establishes X
        for m in self.HAVE_PAT.finditer(content):
            name = m.group(1)
            v = get_var(name)
            groups.append([[v]])

        # Lean4: exact/apply → uses established facts
        for m in self.EXACT_PAT.finditer(content):
            v = get_var(m.group(1).strip())
            groups.append([[v]])
        for m in self.APPLY_PAT.finditer(content):
            v = get_var(m.group(1).strip())
            groups.append([[v]])

        return var_counter, groups


class MarketConstraintExtractor(ConstraintExtractor):
    """
    Extract constraints from market text.

    The Ed Thorp extractor. Delegates to TextTo3SAT with domain="market",
    which uses PropositionMiner.mine_market() to recognize:
    - Price bounds, position limits, stop-loss levels
    - Hedging requirements, correlation constraints
    - Performance ratio thresholds (Sharpe, Sortino, Calmar)
    - Long/short direction + mutual exclusion
    """

    def __init__(self):
        from .text_to_3sat import TextTo3SAT
        self._translator = TextTo3SAT()

    def extract(self, content: str) -> Tuple[int, List[List[List[int]]]]:
        return self._translator.translate_grouped(content, domain="market")


# ── Convenience Functions ─────────────────────────────────────────────────────

# Module-level default gate
_default_gate: Optional[VerificationGate] = None


def get_gate() -> VerificationGate:
    """Get or create the default verification gate."""
    global _default_gate
    if _default_gate is None:
        _default_gate = VerificationGate()
    return _default_gate


def verify(content: str, domain: str = "logic", **kwargs) -> VerificationResult:
    """Verify content using the default gate. The simplest entry point."""
    return get_gate().verify(content, domain=domain, **kwargs)


def must_verify(content: str, domain: str = "logic") -> str:
    """Verify or raise. For strict pipelines."""
    result = verify(content, domain=domain)
    if not result.is_verified:
        raise VerificationError(
            f"Verification {result.verdict.name}: {result.sat_ratio:.2%} SAT ratio, "
            f"{result.n_refuted}/{result.n_constraints} groups refuted",
            result=result,
        )
    return content


def verify_signal(
    signal: "np.ndarray",
    modality: str = "ts",
    metadata: Optional[Dict[str, Any]] = None,
    **kwargs,
) -> VerificationResult:
    """Verify a signal using the default gate."""
    return get_gate().verify_signal(signal, modality=modality, metadata=metadata, **kwargs)


def verify_multimodal(
    signals: Dict[str, "np.ndarray"],
    metadata: Optional[Dict[str, Any]] = None,
    **kwargs,
) -> VerificationResult:
    """Verify multimodal signals using the default gate."""
    return get_gate().verify_multimodal(signals, metadata=metadata, **kwargs)


def must_verify_signal(
    signal: "np.ndarray",
    modality: str = "ts",
    metadata: Optional[Dict[str, Any]] = None,
) -> "np.ndarray":
    """Verify signal or raise. For strict signal pipelines."""
    result = verify_signal(signal, modality=modality, metadata=metadata)
    if result.is_contradiction:
        raise VerificationError(
            f"Signal verification CONTRADICTION ({modality}): "
            f"{result.sat_ratio:.2%} SAT ratio, "
            f"{result.n_refuted}/{result.n_constraints} groups refuted",
            result=result,
        )
    return signal


class VerificationError(Exception):
    """Raised when verification fails in strict mode."""
    def __init__(self, message: str, result: VerificationResult):
        super().__init__(message)
        self.result = result
