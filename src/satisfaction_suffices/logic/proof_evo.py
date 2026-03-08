"""
Proof Evolution — Paradoxes as Evolution Catalysts
===================================================
The four-valued verdict drives everything:

    VERIFIED      (SAT)       → proved, accepted into the proof corpus
    CONTRADICTION (UNSAT)     → refuted, discarded or used as counterexample
    PARADOX       (structural)→ individually SAT groups, jointly UNSAT — decompose
    TIMEOUT       (operational)→ solver budget exhausted — escalate or reschedule

Paradoxes don't break the system. They ARE the system's growth signal.
When verification returns PARADOX or TIMEOUT, that's not a failure — it's
a constraint that requires new axioms, lemmas, or decompositions to
resolve. Evolution is the process of generating those resolutions.

Inspired by:
  - OpenEvolve (evolutionary search over programs)
  - Lean4/Mathlib proof automation
  - IMO25 (competition-level theorem proving)
  - PPL (Pigeonhole Paradox Logic) — contradictions increase tolerance

The cycle:
    1. VERIFY candidate proof/statement
    2. If unresolved (PARADOX/TIMEOUT) → DECOMPOSE into sub-problems
    3. MUTATE: generate variant decompositions
    4. VERIFY each variant
    5. SELECT: keep variants that resolve more sub-problems
    6. COMPOSE: merge successful variants
    7. Repeat until VERIFIED or generation budget exhausted

This ties into 3-SAT perfectly:
    - Each proof obligation is a clause
    - A complete proof is a satisfying assignment
    - A paradox is an UNSAT core — the minimal set of clauses
      that can't all be satisfied simultaneously
    - Evolution = clause learning at the proof level
"""

from __future__ import annotations

import hashlib
import math
import random
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from ..verifier.sat import CDCLSolver, pos_lit, neg_lit, solve_cnf
from ..verifier.verify import (
    VerificationGate,
    VerificationResult,
    Verdict,
    ProofConstraintExtractor,
    get_gate,
)


# ── Proof State ───────────────────────────────────────────────────────────────

class ProofStatus(Enum):
    PROVED = auto()      # verified TRUE
    REFUTED = auto()     # verified FALSE
    UNRESOLVED = auto()  # unresolved — evolution target
    EVOLVING = auto()    # currently being evolved



@dataclass
class ProofNode:
    """A node in the proof evolution tree."""
    id: str
    statement: str
    status: ProofStatus
    verification: Optional[VerificationResult] = None
    parent_id: Optional[str] = None
    children: List[str] = field(default_factory=list)
    generation: int = 0
    fitness: float = 0.0  # SAT ratio — higher is better
    mutations: List[str] = field(default_factory=list)  # history of mutations applied

    @property
    def is_resolved(self) -> bool:
        return self.status in (ProofStatus.PROVED, ProofStatus.REFUTED)


@dataclass
class EvolutionResult:
    """Result of an evolution run."""
    resolved: bool
    best_node: ProofNode
    generations: int
    total_candidates: int
    proved_count: int
    refuted_count: int
    unresolved_count: int
    elapsed_ms: float
    evolution_tree: Dict[str, ProofNode]
    mutation_stats: Optional[Dict[str, Dict[str, float]]] = None
    diversity: float = 0.0


# ── Mutation Operators ────────────────────────────────────────────────────────

class MutationOp(Enum):
    """Ways to mutate a proof attempt."""
    DECOMPOSE = auto()       # Split into sub-problems
    STRENGTHEN = auto()      # Add stronger premises
    WEAKEN = auto()          # Relax conclusions
    CONTRAPOSITIVE = auto()  # Flip implication direction
    CASE_SPLIT = auto()      # Try by cases
    INDUCTION = auto()       # Add inductive structure
    LEMMA_INJECT = auto()    # Insert intermediate lemmas
    GENERALIZE = auto()      # Abstract over specifics
    SPECIALIZE = auto()      # Instantiate universals
    RESOLUTION = auto()      # Resolve two statements sharing a term
    NEGATE_NORMAL = auto()   # Push negations inward (NNF transform)
    BY_ANALOGY = auto()      # Structural analogy with a proved lemma


def decompose(statement: str) -> List[str]:
    """
    Break a statement into sub-problems.
    Each sub-problem is independently verifiable.
    """
    # Split on logical connectives
    parts = []
    for sep in [" and ", " implies ", " if and only if ", " then "]:
        if sep in statement.lower():
            splits = statement.lower().split(sep)
            parts.extend(s.strip() for s in splits if s.strip())

    if not parts:
        # Try sentence splitting
        import re
        sentences = [s.strip() for s in re.split(r'[.;]', statement) if s.strip()]
        if len(sentences) > 1:
            parts = sentences
        else:
            # Atomic — can't decompose further
            parts = [statement]

    return parts


def contrapositive(statement: str) -> str:
    """
    If A then B → If not B then not A
    """
    import re
    m = re.match(r"if\s+(.+?)\s+then\s+(.+)", statement, re.IGNORECASE)
    if m:
        return f"if not {m.group(2).strip()} then not {m.group(1).strip()}"
    return f"not ({statement})"


def case_split(statement: str, cases: Optional[List[str]] = None) -> List[str]:
    """
    Split into cases. If no cases provided, split on positive/negative.
    """
    if cases:
        return [f"Case: {c}. {statement}" for c in cases]
    return [
        f"Assume positive. {statement}",
        f"Assume negative. not {statement}",
    ]


def inject_lemma(statement: str, lemma: str) -> str:
    """Insert a lemma before the conclusion."""
    return f"Assume {lemma}. Therefore {statement}"


def strengthen(statement: str, premise: str) -> str:
    """Add a stronger premise."""
    return f"Given {premise}. {statement}"


def induction(statement: str) -> List[str]:
    """
    Add inductive structure: base case + inductive step.
    Returns two sub-problems that together prove the original.
    """
    import re
    # Try to detect "for all n" / "for every" / universal quantifiers
    m = re.match(r"(?:for\s+(?:all|every|each)\s+(\w+)[\s,.:]+)?(.*)", statement, re.IGNORECASE)
    var = m.group(1) if m and m.group(1) else "n"
    body = m.group(2).strip() if m and m.group(2) else statement

    base = f"Base case: when {var} = 0, {body}"
    step = f"Inductive step: assume {body} holds for {var} = k, prove it holds for {var} = k + 1"
    return [base, step]


def generalize(statement: str) -> str:
    """
    Abstract over specifics — replace concrete terms with universals.
    """
    import re
    # Replace specific numbers with universal quantifier
    generalized = re.sub(r'\b\d+\b', 'N', statement, count=1)
    if generalized != statement:
        return f"For all N, {generalized}"
    # Replace specific names (capitalized single words) with variables
    generalized = re.sub(r'\b([A-Z][a-z]+)\b', 'X', statement, count=1)
    if generalized != statement:
        return f"For all X, {generalized}"
    return f"For all X, {statement}"


def specialize(statement: str, term: str = "0") -> str:
    """
    Instantiate universals with a concrete term.
    """
    import re
    m = re.match(r"for\s+all\s+(\w+)[\s,.:]+(.+)", statement, re.IGNORECASE)
    if m:
        var, body = m.group(1), m.group(2)
        return body.replace(var, term)
    return f"Let X = {term}. {statement}"


def negate_normalize(statement: str) -> str:
    """
    Push negations inward (NNF-like transform at the proof level).
    not (A and B) → (not A) or (not B)
    not (A or B) → (not A) and (not B)
    not not A → A
    """
    import re
    s = statement.strip()
    # Double negation elimination
    s = re.sub(r'not\s+not\s+', '', s, flags=re.IGNORECASE)
    # De Morgan: not (A and B)
    m = re.match(r"not\s*\(\s*(.+?)\s+and\s+(.+?)\s*\)", s, re.IGNORECASE)
    if m:
        return f"(not {m.group(1)}) or (not {m.group(2)})"
    # De Morgan: not (A or B)
    m = re.match(r"not\s*\(\s*(.+?)\s+or\s+(.+?)\s*\)", s, re.IGNORECASE)
    if m:
        return f"(not {m.group(1)}) and (not {m.group(2)})"
    return s


def resolve_statements(s1: str, s2: str) -> Optional[str]:
    """
    Resolution: if s1 contains A and s2 contains 'not A', resolve.
    Returns the resolvent or None if no resolution possible.
    """
    import re
    # Extract atomic terms from each statement
    terms1 = set(re.findall(r'\b([a-zA-Z]\w*)\b', s1.lower()))
    terms2_neg = set()
    for m in re.finditer(r'not\s+(\w+)', s2.lower()):
        terms2_neg.add(m.group(1))

    common = terms1 & terms2_neg
    if common:
        pivot = common.pop()
        # Remove pivot from s1, remove "not pivot" from s2, combine
        r1 = re.sub(rf'\b{pivot}\b', '', s1, count=1, flags=re.IGNORECASE).strip()
        r2 = re.sub(rf'not\s+{pivot}', '', s2, count=1, flags=re.IGNORECASE).strip()
        # Clean up orphan connectives
        for pat in [r'^\s*and\s+', r'\s+and\s*$', r'^\s*or\s+', r'\s+or\s*$']:
            r1 = re.sub(pat, '', r1, flags=re.IGNORECASE).strip()
            r2 = re.sub(pat, '', r2, flags=re.IGNORECASE).strip()
        parts = [p for p in [r1, r2] if p]
        return " and ".join(parts) if parts else None
    return None


def by_analogy(statement: str, template: str) -> str:
    """
    Structural analogy: rewrite statement using the structure of a proved template.
    Extracts the logical skeleton of the template and applies it to the statement.
    """
    import re
    # Detect template pattern: "if X then Y", "given X, Y", "assume X. therefore Y"
    patterns = [
        (r"if\s+(.+?)\s+then\s+(.+)", "if {premise} then {conclusion}"),
        (r"given\s+(.+?)\.\s+(.+)", "Given {premise}. {conclusion}"),
        (r"assume\s+(.+?)\.\s+therefore\s+(.+)", "Assume {premise}. Therefore {conclusion}"),
    ]
    for pat, fmt in patterns:
        m = re.match(pat, template, re.IGNORECASE)
        if m:
            # Apply same skeleton to the new statement
            parts = decompose(statement)
            if len(parts) >= 2:
                return fmt.format(premise=parts[0], conclusion=parts[-1])
            return fmt.format(premise=statement, conclusion=statement)
    return f"By analogy with [{template[:50]}]: {statement}"


# ── Mutation Bandit (UCB-1 adaptive operator selection) ──────────────────────

@dataclass
class MutationArm:
    """Bandit arm for a single mutation operator."""
    op: MutationOp
    n_pulls: int = 0
    total_reward: float = 0.0
    best_delta: float = 0.0

    @property
    def mean_reward(self) -> float:
        return self.total_reward / max(self.n_pulls, 1)


class MutationBandit:
    """
    UCB-1 bandit over mutation operators.

    Tracks which mutations produce the best fitness gains (Δsat_ratio)
    and biases selection toward high-reward operators. This replaces
    uniform random selection with adaptive selection — the analog of
    TLSE's genome-based strategy selection, but at the proof level.
    """

    def __init__(self, ops: List[MutationOp], c: float = 1.41):
        self._arms = {op: MutationArm(op=op) for op in ops}
        self._c = c
        self._total_pulls = 0

    def select(self, rng: random.Random) -> MutationOp:
        """Select mutation operator via UCB-1."""
        # Ensure every arm pulled at least once
        for arm in self._arms.values():
            if arm.n_pulls == 0:
                return arm.op

        best_score = -1.0
        best_op = None
        for arm in self._arms.values():
            ucb = arm.mean_reward + self._c * math.sqrt(
                math.log(self._total_pulls + 1) / arm.n_pulls
            )
            if ucb > best_score or (ucb == best_score and rng.random() > 0.5):
                best_score = ucb
                best_op = arm.op
        return best_op or rng.choice(list(self._arms.keys()))

    def update(self, op: MutationOp, delta_fitness: float) -> None:
        """Update arm with observed reward (fitness delta)."""
        arm = self._arms[op]
        arm.n_pulls += 1
        self._total_pulls += 1
        reward = max(0.0, delta_fitness)  # clamp negative
        arm.total_reward += reward
        arm.best_delta = max(arm.best_delta, delta_fitness)

    def stats(self) -> Dict[str, Dict[str, float]]:
        """Return per-operator stats for diagnostics."""
        return {
            arm.op.name: {
                "pulls": arm.n_pulls,
                "mean_reward": arm.mean_reward,
                "best_delta": arm.best_delta,
            }
            for arm in self._arms.values()
        }


# ── Solver Portfolio ─────────────────────────────────────────────────────────

@dataclass
class SolverConfig:
    """
    A SAT solver configuration — different parameter choices.

    Inspired by TLSE's genome axes: each config is a point in the
    solver strategy space. Running the same CNF through multiple
    configs implements portfolio solving at the proof level.
    """
    name: str
    budget: int = 500
    var_decay: float = 0.95        # variable activity decay rate
    restart_mult: float = 2.0      # restart multiplier
    restart_base: int = 100        # base restart interval
    phase_init: bool = False       # initial phase polarity

    def apply(self, solver: "CDCLSolver") -> None:
        """Apply this configuration to a solver instance."""
        solver._var_decay = self.var_decay
        for v in range(solver.n_vars):
            solver._polarity[v] = self.phase_init


# Default portfolio — covers the major strategy axes
DEFAULT_PORTFOLIO = [
    SolverConfig("aggressive", budget=500, var_decay=0.80, restart_base=50),
    SolverConfig("patient", budget=2000, var_decay=0.99, restart_base=500),
    SolverConfig("default", budget=500, var_decay=0.95, restart_base=100),
    SolverConfig("rapid_restart", budget=500, var_decay=0.95, restart_base=25),
    SolverConfig("high_decay", budget=1000, var_decay=0.75, restart_base=100),
    SolverConfig("phase_true", budget=500, var_decay=0.95, restart_base=100, phase_init=True),
]


def portfolio_solve(
    n_vars: int,
    clauses: List[List[int]],
    configs: Optional[List[SolverConfig]] = None,
) -> Tuple[bool, Optional[Dict[int, bool]], str]:
    """
    Virtual Best Solver — run the same CNF through multiple configs.

    Returns (sat, model, winning_config_name).
    If ANY config finds SAT, we're done (SAT is a certificate).
    If ALL configs return UNSAT, the instance is UNSAT.
    """
    if configs is None:
        configs = DEFAULT_PORTFOLIO

    for cfg in configs:
        solver = CDCLSolver()
        solver.new_vars(n_vars)
        cfg.apply(solver)

        ok = True
        for clause_lits in clauses:
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
            continue

        result = solver.solve(budget=cfg.budget)
        if result:
            raw = solver.model()
            m = {v + 1: val for v, val in raw.items()}
            return True, m, cfg.name

    return False, None, "all_unsat"


# ── Evolution Engine ──────────────────────────────────────────────────────────

class ProofEvolver:
    """
    Evolution engine for resolving unresolved (PARADOX/TIMEOUT) proofs.

    The cycle:
      1. Verify the proof → get verdict
      2. If unresolved → generate mutations
      3. Verify each mutation
      4. Select best (highest SAT ratio)
      5. Repeat for N generations or until resolved

    This is evolutionary search where:
      - Individuals = proof attempts
      - Fitness = SAT ratio from verification
      - Mutation = proof transformations (decompose, contrapositive, etc.)
      - Selection = keep highest SAT ratio
      - Termination = VERIFIED or budget exhausted
    """

    def __init__(
        self,
        gate: Optional[VerificationGate] = None,
        population_size: int = 8,
        max_generations: int = 20,
        mutation_rate: float = 0.7,
        elite_fraction: float = 0.25,
        seed: Optional[int] = None,
    ):
        self.gate = gate or get_gate()
        self.pop_size = population_size
        self.max_gen = max_generations
        self.mutation_rate = mutation_rate
        self.elite_k = max(1, int(population_size * elite_fraction))
        self.rng = random.Random(seed)

        self._tree: Dict[str, ProofNode] = {}
        self._gen_counter = 0
        self._id_counter = 0

        # Available mutations — all 12 operators
        self._mutations = [
            MutationOp.DECOMPOSE,
            MutationOp.CONTRAPOSITIVE,
            MutationOp.CASE_SPLIT,
            MutationOp.STRENGTHEN,
            MutationOp.WEAKEN,
            MutationOp.LEMMA_INJECT,
            MutationOp.INDUCTION,
            MutationOp.GENERALIZE,
            MutationOp.SPECIALIZE,
            MutationOp.RESOLUTION,
            MutationOp.NEGATE_NORMAL,
            MutationOp.BY_ANALOGY,
        ]

        # UCB bandit for adaptive mutation selection
        self._bandit = MutationBandit(self._mutations)

        # Lemma bank — grows during evolution
        self._lemma_bank: List[str] = []

        # Crossover rate — fraction of offspring produced by recombination
        self._crossover_rate = 0.3

        # Stagnation detector
        self._stagnation_window = 5
        self._best_fitness_history: List[float] = []

    def _make_id(self) -> str:
        self._id_counter += 1
        return f"pf_{self._id_counter:04d}"

    def _make_node(
        self,
        statement: str,
        parent_id: Optional[str] = None,
        generation: int = 0,
    ) -> ProofNode:
        node = ProofNode(
            id=self._make_id(),
            statement=statement,
            status=ProofStatus.UNRESOLVED,
            parent_id=parent_id,
            generation=generation,
        )
        self._tree[node.id] = node
        if parent_id and parent_id in self._tree:
            self._tree[parent_id].children.append(node.id)
        return node

    def _verify_node(self, node: ProofNode) -> None:
        """Verify a proof node and update its status + fitness."""
        result = self.gate.verify(node.statement, domain="proof")
        node.verification = result
        node.fitness = result.sat_ratio

        if result.verdict == Verdict.VERIFIED:
            node.status = ProofStatus.PROVED
            # Proved statements become lemmas
            self._lemma_bank.append(node.statement)
        elif result.verdict == Verdict.CONTRADICTION:
            node.status = ProofStatus.REFUTED
        else:
            # PARADOX or TIMEOUT — both are evolution targets
            node.status = ProofStatus.UNRESOLVED

    def _mutate(self, node: ProofNode) -> Tuple[List[ProofNode], MutationOp]:
        """Generate mutated variants of a proof node. Returns (variants, op_used)."""
        variants: List[ProofNode] = []
        statement = node.statement

        op = self._bandit.select(self.rng)

        if op == MutationOp.DECOMPOSE:
            parts = decompose(statement)
            for part in parts:
                child = self._make_node(part, node.id, node.generation + 1)
                child.mutations = node.mutations + ["decompose"]
                variants.append(child)

        elif op == MutationOp.CONTRAPOSITIVE:
            cp = contrapositive(statement)
            child = self._make_node(cp, node.id, node.generation + 1)
            child.mutations = node.mutations + ["contrapositive"]
            variants.append(child)

        elif op == MutationOp.CASE_SPLIT:
            cases = case_split(statement)
            for c in cases:
                child = self._make_node(c, node.id, node.generation + 1)
                child.mutations = node.mutations + ["case_split"]
                variants.append(child)

        elif op == MutationOp.STRENGTHEN:
            if self._lemma_bank:
                lemma = self.rng.choice(self._lemma_bank)
                s = strengthen(statement, lemma)
                child = self._make_node(s, node.id, node.generation + 1)
                child.mutations = node.mutations + [f"strengthen({lemma[:30]})"]
                variants.append(child)
            else:
                parts = decompose(statement)
                for part in parts:
                    child = self._make_node(part, node.id, node.generation + 1)
                    child.mutations = node.mutations + ["decompose"]
                    variants.append(child)

        elif op == MutationOp.WEAKEN:
            weakened = f"{statement} or the negation holds"
            child = self._make_node(weakened, node.id, node.generation + 1)
            child.mutations = node.mutations + ["weaken"]
            variants.append(child)

        elif op == MutationOp.LEMMA_INJECT:
            if self._lemma_bank:
                lemma = self.rng.choice(self._lemma_bank)
                injected = inject_lemma(statement, lemma)
                child = self._make_node(injected, node.id, node.generation + 1)
                child.mutations = node.mutations + [f"lemma_inject({lemma[:30]})"]
                variants.append(child)

        elif op == MutationOp.INDUCTION:
            parts = induction(statement)
            for part in parts:
                child = self._make_node(part, node.id, node.generation + 1)
                child.mutations = node.mutations + ["induction"]
                variants.append(child)

        elif op == MutationOp.GENERALIZE:
            gen = generalize(statement)
            child = self._make_node(gen, node.id, node.generation + 1)
            child.mutations = node.mutations + ["generalize"]
            variants.append(child)

        elif op == MutationOp.SPECIALIZE:
            terms = ["0", "1", "x", "empty"]
            term = self.rng.choice(terms)
            spec = specialize(statement, term)
            child = self._make_node(spec, node.id, node.generation + 1)
            child.mutations = node.mutations + [f"specialize({term})"]
            variants.append(child)

        elif op == MutationOp.RESOLUTION:
            if self._lemma_bank:
                other = self.rng.choice(self._lemma_bank)
                resolved = resolve_statements(statement, other)
                if resolved:
                    child = self._make_node(resolved, node.id, node.generation + 1)
                    child.mutations = node.mutations + ["resolution"]
                    variants.append(child)
            if not variants:
                # Fallback: negate-normalize instead
                nn = negate_normalize(statement)
                child = self._make_node(nn, node.id, node.generation + 1)
                child.mutations = node.mutations + ["negate_normal"]
                variants.append(child)

        elif op == MutationOp.NEGATE_NORMAL:
            nn = negate_normalize(statement)
            child = self._make_node(nn, node.id, node.generation + 1)
            child.mutations = node.mutations + ["negate_normal"]
            variants.append(child)

        elif op == MutationOp.BY_ANALOGY:
            if self._lemma_bank:
                template = self.rng.choice(self._lemma_bank)
                analog = by_analogy(statement, template)
                child = self._make_node(analog, node.id, node.generation + 1)
                child.mutations = node.mutations + [f"analogy({template[:30]})"]
                variants.append(child)

        return variants, op

    def _crossover(self, p1: ProofNode, p2: ProofNode) -> ProofNode:
        """
        Crossover: combine two proof nodes into an offspring.

        Strategy: take premise structure from p1, conclusion structure from p2.
        This is analogous to uniform crossover at the clause level.
        """
        parts1 = decompose(p1.statement)
        parts2 = decompose(p2.statement)

        # Interleave parts from both parents
        combined = []
        for i in range(max(len(parts1), len(parts2))):
            if i < len(parts1) and i < len(parts2):
                combined.append(parts1[i] if self.rng.random() < 0.5 else parts2[i])
            elif i < len(parts1):
                combined.append(parts1[i])
            else:
                combined.append(parts2[i])

        child_statement = " and ".join(combined) if len(combined) > 1 else combined[0]
        child = self._make_node(child_statement, p1.id, max(p1.generation, p2.generation) + 1)
        child.mutations = ["crossover"]
        return child

    def _tournament_select(self, population: List[ProofNode], k: int = 3) -> ProofNode:
        """Tournament selection: pick k random, return the fittest."""
        candidates = self.rng.sample(population, min(k, len(population)))
        return max(candidates, key=lambda n: n.fitness)

    def _diversity_score(self, population: List[ProofNode]) -> float:
        """
        Measure population diversity as ratio of unique statement hashes.
        1.0 = all unique, low = convergence/stagnation.
        """
        if not population:
            return 0.0
        hashes = {hashlib.md5(n.statement.encode()).hexdigest()[:8] for n in population}
        return len(hashes) / len(population)

    def _detect_stagnation(self, best_fitness: float) -> bool:
        """Detect if evolution has stalled."""
        self._best_fitness_history.append(best_fitness)
        if len(self._best_fitness_history) < self._stagnation_window:
            return False
        window = self._best_fitness_history[-self._stagnation_window:]
        return max(window) - min(window) < 0.01  # <1% improvement over window

    def evolve(
        self,
        statement: str,
        seed_lemmas: Optional[List[str]] = None,
    ) -> EvolutionResult:
        """
        Evolve a proof for the given statement.

        Returns EvolutionResult with the best proof node found,
        whether it was resolved, and the full evolution tree.

        Evolution strategy:
          - Tournament selection (pressure without total convergence)
          - UCB-1 bandit picks the mutation operator adaptively
          - Crossover recombines elite proof nodes
          - Diversity pressure restarts stagnant populations
          - Fitness = SAT ratio from verification gate
        """
        t0 = time.perf_counter()

        if seed_lemmas:
            self._lemma_bank.extend(seed_lemmas)

        # Initialize population with the original statement
        root = self._make_node(statement, generation=0)
        self._verify_node(root)

        if root.status == ProofStatus.PROVED:
            return self._make_result(root, 0, t0)

        # Initial population: root + mutations
        population = [root]
        for _ in range(self.pop_size - 1):
            variants, op = self._mutate(root)
            population.extend(variants)

        # Verify initial population
        for node in population[1:]:
            self._verify_node(node)
            if node.status == ProofStatus.PROVED:
                return self._make_result(node, 0, t0)

        # Evolution loop
        for gen in range(1, self.max_gen + 1):
            population.sort(key=lambda n: n.fitness, reverse=True)

            if population[0].status == ProofStatus.PROVED:
                return self._make_result(population[0], gen, t0)

            # Stagnation detection — if stuck, inject random diversity
            if self._detect_stagnation(population[0].fitness):
                diversity = self._diversity_score(population)
                if diversity < 0.3:
                    # Population converged — inject fresh random mutations from root
                    n_inject = max(1, self.pop_size // 4)
                    for _ in range(n_inject):
                        fresh, _ = self._mutate(root)
                        for f in fresh:
                            self._verify_node(f)
                            population.append(f)
                            if f.status == ProofStatus.PROVED:
                                return self._make_result(f, gen, t0)

            # Select elite
            elite = population[:self.elite_k]

            # Generate next generation
            next_gen = list(elite)

            while len(next_gen) < self.pop_size:
                r = self.rng.random()

                if r < self._crossover_rate and len(elite) >= 2:
                    # Crossover
                    p1 = self._tournament_select(population)
                    p2 = self._tournament_select(population)
                    if p1.id != p2.id:
                        child = self._crossover(p1, p2)
                        self._verify_node(child)
                        next_gen.append(child)
                        if child.status == ProofStatus.PROVED:
                            return self._make_result(child, gen, t0)
                    continue

                if r < self._crossover_rate + self.mutation_rate:
                    # Mutation with bandit-selected operator
                    parent = self._tournament_select(population)
                    parent_fit = parent.fitness
                    children, op = self._mutate(parent)
                    for child in children:
                        self._verify_node(child)
                        # Feed bandit: reward = fitness improvement over parent
                        delta = child.fitness - parent_fit
                        self._bandit.update(op, delta)
                        next_gen.append(child)
                        if child.status == ProofStatus.PROVED:
                            return self._make_result(child, gen, t0)
                else:
                    # Clone
                    parent = self._tournament_select(population)
                    clone = self._make_node(parent.statement, parent.id, gen)
                    self._verify_node(clone)
                    next_gen.append(clone)

            population = next_gen[:self.pop_size]

        # Budget exhausted — return best found
        population.sort(key=lambda n: n.fitness, reverse=True)
        return self._make_result(population[0], self.max_gen, t0)

    def _make_result(
        self, best: ProofNode, gen: int, t0: float
    ) -> EvolutionResult:
        elapsed = (time.perf_counter() - t0) * 1000
        proved = sum(1 for n in self._tree.values() if n.status == ProofStatus.PROVED)
        refuted = sum(1 for n in self._tree.values() if n.status == ProofStatus.REFUTED)
        unresolved = sum(1 for n in self._tree.values() if n.status == ProofStatus.UNRESOLVED)

        all_nodes = list(self._tree.values())
        diversity = self._diversity_score(all_nodes)

        return EvolutionResult(
            resolved=best.status == ProofStatus.PROVED,
            best_node=best,
            generations=gen,
            total_candidates=len(self._tree),
            proved_count=proved,
            refuted_count=refuted,
            unresolved_count=unresolved,
            elapsed_ms=elapsed,
            evolution_tree=dict(self._tree),
            mutation_stats=self._bandit.stats(),
            diversity=diversity,
        )

    @property
    def lemma_bank(self) -> List[str]:
        """Lemmas discovered during evolution. Reusable across runs."""
        return list(self._lemma_bank)


# ── UNSAT Core Extraction ─────────────────────────────────────────────────────

def extract_unsat_core(
    n_vars: int,
    clauses: List[List[int]],
    budget: int = 2000,
) -> Optional[List[List[int]]]:
    """
    Extract the minimal UNSAT core — the smallest subset of clauses
    that is still unsatisfiable.

    This identifies the EXACT source of a contradiction, which tells
    the evolution engine WHERE to focus mutations.

    Uses iterative deletion: remove one clause at a time, check if
    still UNSAT. If removing a clause makes it SAT, that clause is
    part of the core.
    """
    # First verify it's actually UNSAT
    sat, _ = solve_cnf(n_vars, clauses, budget=budget)
    if sat:
        return None  # Not UNSAT, no core

    core = list(clauses)
    i = 0
    while i < len(core):
        # Try removing clause i
        candidate = core[:i] + core[i + 1:]
        if not candidate:
            break
        sat, _ = solve_cnf(n_vars, candidate, budget=budget)
        if not sat:
            # Still UNSAT without this clause — it's redundant
            core = candidate
            # Don't increment i — next clause shifted into position
        else:
            # Became SAT — this clause is essential to the core
            i += 1

    return core


# ── Convenience ───────────────────────────────────────────────────────────────

def evolve_proof(
    statement: str,
    max_generations: int = 20,
    population_size: int = 8,
    seed_lemmas: Optional[List[str]] = None,
) -> EvolutionResult:
    """
    Convenience function: evolve a proof for a statement.

    >>> result = evolve_proof("if A and B then C")
    >>> result.resolved
    True
    """
    evolver = ProofEvolver(
        max_generations=max_generations,
        population_size=population_size,
    )
    return evolver.evolve(statement, seed_lemmas=seed_lemmas)


def portfolio_evolve_proof(
    statement: str,
    max_generations: int = 20,
    population_size: int = 12,
    seed_lemmas: Optional[List[str]] = None,
    n_runs: int = 3,
) -> EvolutionResult:
    """
    Multi-start evolution with different random seeds.

    Runs the evolver n_runs times with different seeds and returns the
    best result. This is the portfolio approach at the evolution level —
    different random seeds explore different regions of the proof space.
    """
    best_result: Optional[EvolutionResult] = None

    for i in range(n_runs):
        evolver = ProofEvolver(
            max_generations=max_generations,
            population_size=population_size,
            seed=i * 42 + 7,
        )
        result = evolver.evolve(statement, seed_lemmas=seed_lemmas)

        if best_result is None or result.best_node.fitness > best_result.best_node.fitness:
            best_result = result

        if result.resolved:
            return result

    return best_result  # type: ignore[return-value]
