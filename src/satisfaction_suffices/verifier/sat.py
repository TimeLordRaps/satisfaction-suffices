"""
SAT Solver — DPLL + WalkSAT Fallback
===============================================
Simple SAT solver for constraint verification in translated CNF spaces.

Implements:
    - Recursive DPLL (complete when budget=0)
  - Unit propagation
  - Pure literal elimination
    - WalkSAT fallback (stochastic local search) when budget-limited DPLL times out

Used as the verification backbone: given a model's output (token sequence,
code, proof step), extract propositional constraints and check satisfiability.
A SAT ratio measures structural coherence.
"""

from __future__ import annotations

import random
from typing import Dict, List, Optional, Set, Tuple

try:  # pragma: no cover - optional torch backend
    import torch
    import torch.nn as nn
    _HAS_TORCH = True
except Exception:  # pragma: no cover - torch may be unavailable/broken at import time
    _HAS_TORCH = False


# ── Literal helpers ──────────────────────────────────────────────────────────

def var_of(lit: int) -> int:
    return lit >> 1

def sign_of(lit: int) -> int:
    return lit & 1

def neg(lit: int) -> int:
    return lit ^ 1

def pos_lit(v: int) -> int:
    return v << 1

def neg_lit(v: int) -> int:
    return (v << 1) | 1


# ── LBool Enum ───────────────────────────────────────────────────────────────

from enum import IntEnum

class LBool(IntEnum):
    """Three-valued logic for SAT solving."""
    FALSE = 0
    TRUE = 1
    UNDEF = 2


# ── DPLL Solver ──────────────────────────────────────────────────────────────

class SATSolver:
    """
    Complete DPLL SAT solver with unit propagation and pure literal elimination.

    Usage:
        solver = SATSolver()
        solver.new_vars(n)
        solver.add_clause([pos_lit(0), neg_lit(1), pos_lit(2)])
        result = solver.solve()  # True = SAT, False = UNSAT
        if result:
            model = solver.model()  # {var: bool}
    """

    def __init__(self):
        self.n_vars: int = 0
        self.clauses: List[List[int]] = []
        self._assigns: Dict[int, bool] = {}  # var -> True/False
        self.conflicts: int = 0
        self.last_method: str = "dpll"

    def new_var(self) -> int:
        v = self.n_vars
        self.n_vars += 1
        return v

    def new_vars(self, n: int) -> List[int]:
        return [self.new_var() for _ in range(n)]

    def add_clause(self, lits: List[int]) -> bool:
        """Add a clause. Returns False if immediately UNSAT (empty clause)."""
        # Remove duplicates, check tautology
        seen: Set[int] = set()
        cleaned: List[int] = []
        for lit in lits:
            if neg(lit) in seen:
                return True  # tautology
            if lit not in seen:
                seen.add(lit)
                cleaned.append(lit)
        if not cleaned:
            return False
        self.clauses.append(cleaned)
        return True

    def _eval_lit(self, lit: int) -> Optional[bool]:
        """Evaluate a literal under current assignment. None if unassigned."""
        v = var_of(lit)
        if v not in self._assigns:
            return None
        val = self._assigns[v]
        return val if sign_of(lit) == 0 else not val

    def _eval_clause(self, clause: List[int]) -> Optional[bool]:
        """Evaluate a clause. True if satisfied, False if all false, None if undetermined."""
        has_undef = False
        for lit in clause:
            val = self._eval_lit(lit)
            if val is True:
                return True
            if val is None:
                has_undef = True
        return None if has_undef else False

    def _unit_propagate(self) -> bool:
        """
        Apply unit propagation. Returns False if conflict found.
        A unit clause has exactly one unassigned literal and all others false.
        """
        changed = True
        while changed:
            changed = False
            for clause in self.clauses:
                val = self._eval_clause(clause)
                if val is True:
                    continue
                if val is False:
                    self.conflicts += 1
                    return False  # conflict
                # Check if unit
                unassigned = []
                all_sat = False
                for lit in clause:
                    ev = self._eval_lit(lit)
                    if ev is True:
                        all_sat = True
                        break
                    if ev is None:
                        unassigned.append(lit)
                if all_sat:
                    continue
                if len(unassigned) == 1:
                    lit = unassigned[0]
                    v = var_of(lit)
                    self._assigns[v] = (sign_of(lit) == 0)
                    changed = True
        return True

    def _pure_literal_eliminate(self) -> None:
        """Assign pure literals (appearing with only one polarity)."""
        pos_seen: Set[int] = set()
        neg_seen: Set[int] = set()
        for clause in self.clauses:
            if self._eval_clause(clause) is True:
                continue
            for lit in clause:
                v = var_of(lit)
                if v in self._assigns:
                    continue
                if sign_of(lit) == 0:
                    pos_seen.add(v)
                else:
                    neg_seen.add(v)
        # Pure positives
        for v in pos_seen - neg_seen:
            if v not in self._assigns:
                self._assigns[v] = True
        # Pure negatives
        for v in neg_seen - pos_seen:
            if v not in self._assigns:
                self._assigns[v] = False

    def _pick_var(self) -> Optional[int]:
        """Pick an unassigned variable."""
        for v in range(self.n_vars):
            if v not in self._assigns:
                return v
        return None

    # ── WalkSAT fallback (incomplete but often fast on near-3-SAT) ──────────

    def _eval_clause_with_assign(self, clause: List[int], assigns: Dict[int, bool]) -> bool:
        for lit in clause:
            v = var_of(lit)
            val = assigns.get(v, False)
            if (sign_of(lit) == 0 and val) or (sign_of(lit) == 1 and not val):
                return True
        return False

    def _unsat_clause_indices(self, assigns: Dict[int, bool]) -> List[int]:
        return [
            i for i, clause in enumerate(self.clauses)
            if not self._eval_clause_with_assign(clause, assigns)
        ]

    def _count_unsat(self, assigns: Dict[int, bool]) -> int:
        return len(self._unsat_clause_indices(assigns))

    def _walksat_profile(self) -> Tuple[int, float, int]:
        """
        Choose WalkSAT parameters for translated CNFs used in this repo.

        Most translators emit 2/3-literal clauses and operate near SAT phase
        transition densities, so we bias toward modest noise and multiple restarts.
        """
        n_clauses = len(self.clauses)
        n_vars = max(1, self.n_vars)
        avg_clause_len = (
            sum(len(c) for c in self.clauses) / max(1, n_clauses)
        )
        ratio = n_clauses / n_vars

        if avg_clause_len <= 3.2:
            max_flips = min(12000, max(600, 90 * n_vars))
            noise = 0.35
            restarts = 8 if 3.2 <= ratio <= 5.2 else 5
        else:
            max_flips = min(8000, max(400, 60 * n_vars))
            noise = 0.45
            restarts = 4

        return max_flips, noise, restarts

    def _walksat(
        self,
        max_flips: int,
        noise: float,
        restarts: int,
        seed: Optional[int] = None,
    ) -> bool:
        if self.n_vars == 0:
            return True

        rng = random.Random(seed)
        best_assign: Dict[int, bool] = {}
        best_unsat = float("inf")

        for _ in range(restarts):
            assigns = {v: bool(rng.getrandbits(1)) for v in range(self.n_vars)}

            for _flip in range(max_flips):
                unsat_idx = self._unsat_clause_indices(assigns)
                if not unsat_idx:
                    self._assigns = assigns
                    return True

                if len(unsat_idx) < best_unsat:
                    best_unsat = len(unsat_idx)
                    best_assign = dict(assigns)

                clause = self.clauses[rng.choice(unsat_idx)]
                vars_in_clause = list({var_of(l) for l in clause})
                if not vars_in_clause:
                    continue

                if rng.random() < noise:
                    flip_v = rng.choice(vars_in_clause)
                else:
                    # Greedy: choose var that minimises unsatisfied clauses after flip
                    best_v = vars_in_clause[0]
                    best_after = float("inf")
                    for v in vars_in_clause:
                        trial = dict(assigns)
                        trial[v] = not trial[v]
                        unsat_after = self._count_unsat(trial)
                        if unsat_after < best_after:
                            best_after = unsat_after
                            best_v = v
                    flip_v = best_v

                assigns[flip_v] = not assigns[flip_v]

        # Keep best assignment for introspection even when unresolved
        if best_assign:
            self._assigns = best_assign
        return False

    def _dpll(self, budget: int) -> bool:
        """Recursive DPLL."""
        if budget > 0 and self.conflicts >= budget:
            return False

        if not self._unit_propagate():
            return False

        self._pure_literal_eliminate()

        # Check if all clauses satisfied
        all_sat = True
        for clause in self.clauses:
            val = self._eval_clause(clause)
            if val is False:
                return False
            if val is None:
                all_sat = False
        if all_sat:
            return True

        v = self._pick_var()
        if v is None:
            return True

        # Try True
        saved = dict(self._assigns)
        self._assigns[v] = True
        if self._dpll(budget):
            return True

        # Try False
        self._assigns = saved
        self._assigns[v] = False
        if self._dpll(budget):
            return True

        # Backtrack
        del self._assigns[v]
        return False

    def solve(self, budget: int = 0) -> bool:
        """
        Solve the SAT instance.
        budget: conflict limit (0 = unlimited).
        Returns True if SAT, False if UNSAT or timeout.

        Behavior:
        - budget == 0  → complete DPLL only.
        - budget > 0   → run DPLL with conflict cap; if cap is hit,
                         attempt WalkSAT fallback tuned for translated CNFs.
        """
        self._assigns = {}
        self.conflicts = 0
        self.last_method = "dpll"
        result = self._dpll(budget)
        if result:
            return True

        # Only fallback when the DPLL failure looks like a timeout path.
        timed_out = budget > 0 and self.conflicts >= budget
        if timed_out and self.clauses and self.n_vars > 0:
            max_flips, noise, restarts = self._walksat_profile()
            self.last_method = "walksat"
            return self._walksat(
                max_flips=max_flips,
                noise=noise,
                restarts=restarts,
                seed=0,
            )

        return False

    def model(self) -> Dict[int, bool]:
        """Return satisfying assignment (call after solve() returns True)."""
        result = {}
        for v in range(self.n_vars):
            result[v] = self._assigns.get(v, False)
        return result


# Back-compat alias
CDCLSolver = SATSolver


# ── High-level interface ──────────────────────────────────────────────────────

SAT_COHERENT   = 0.90
SAT_PLATEAU_LO = 0.75

ZONE_REWARDS = {
    "coherent":   2.0,
    "plateau":    1.0,
    "incoherent": -1.0,
}


def solve_cnf(
    n_vars: int,
    clauses: List[List[int]],
    budget: int = 0,
) -> Tuple[bool, Optional[Dict[int, bool]]]:
    """
    Solve a CNF formula.

    n_vars: number of variables (0-indexed)
    clauses: list of clauses, each a list of signed ints
             positive int = positive literal, negative int = negative literal
             e.g. [1, -2, 3] means (x1 v ~x2 v x3)
    budget: conflict limit (0 = unlimited)

    Returns (satisfiable, model_or_None)
    """
    solver = SATSolver()
    solver.new_vars(n_vars)

    for clause_lits in clauses:
        internal = []
        for lit in clause_lits:
            if lit > 0:
                internal.append(pos_lit(lit - 1))
            else:
                internal.append(neg_lit(-lit - 1))
        if not solver.add_clause(internal):
            return False, None

    result = solver.solve(budget)
    if result:
        raw = solver.model()
        m = {v + 1: val for v, val in raw.items()}
        return True, m
    return False, None


def sat_score(
    n_vars: int,
    clause_groups: List[List[List[int]]],
    conflict_budget: int = 500,
    **kwargs,
) -> Tuple[float, str, int]:
    """
    Compute SAT coherence score across multiple constraint groups.

    Each group is a CNF formula. The score is the fraction of groups
    that are satisfiable.

    Returns (ratio, zone, n_timeout)
    """
    if not clause_groups:
        return 1.0, "coherent", 0

    sat_count = 0
    timeout_count = 0
    for group in clause_groups:
        solver = SATSolver()
        solver.new_vars(n_vars)
        ok_add = True
        for clause_lits in group:
            internal = []
            for lit in clause_lits:
                if lit > 0:
                    internal.append(pos_lit(lit - 1))
                else:
                    internal.append(neg_lit(-lit - 1))
            if not solver.add_clause(internal):
                ok_add = False
                break
        if not ok_add:
            continue
        result = solver.solve(budget=conflict_budget)
        if result:
            sat_count += 1
        elif conflict_budget > 0 and solver.conflicts >= conflict_budget:
            timeout_count += 1

    ratio = sat_count / len(clause_groups)

    if ratio >= SAT_COHERENT:
        zone = "coherent"
    elif ratio >= SAT_PLATEAU_LO:
        zone = "plateau"
    else:
        zone = "incoherent"

    return ratio, zone, timeout_count


if not _HAS_TORCH:  # pragma: no cover - exercised only when torch backend missing
    class SATReward:  # type: ignore[no-redef]
        """SATReward requires torch. Install torch to use this class."""
        def __init__(self, *a, **kw):
            raise ImportError("SATReward requires PyTorch. pip install torch")


if _HAS_TORCH:  # pragma: no cover - torch-only reward path is backend-dependent
    class SATReward(nn.Module):  # type: ignore[no-redef]
        """
        Differentiable SAT reward for RL training.

        The SAT solve itself is non-differentiable (discrete).
        We use REINFORCE: L = -reward * log_prob(sequence).
        Reward is detached; gradients flow only through the log-prob.
        """

        def __init__(self, weight: float = 0.3):
            super().__init__()
            self.weight = weight

        def forward(
            self,
            token_ids: torch.Tensor,         # (B, T)
            logits: torch.Tensor,             # (B, T, V)
            constraint_fn=None,
        ) -> Tuple[torch.Tensor, Dict]:
            B, T, V = logits.shape
            device = logits.device

            if constraint_fn is None:
                return torch.tensor(0.0, device=device), {"mean_sat": 0.0, "plateau_pct": 0.0}

            rewards = torch.zeros(B, device=device)
            sat_ratios: List[float] = []
            zones: List[str] = []

            for b in range(B):
                ids = token_ids[b].tolist()
                n_v, groups = constraint_fn(ids)
                ratio, zone, _ = sat_score(n_v, groups)
                rewards[b] = ZONE_REWARDS[zone]
                sat_ratios.append(ratio)
                zones.append(zone)

            log_probs = torch.nn.functional.log_softmax(logits, dim=-1)
            tok_lp = log_probs.gather(
                -1, token_ids.clamp(0, V - 1).unsqueeze(-1)
            ).squeeze(-1).mean(-1)

            loss = -(rewards.detach() * tok_lp).mean() * self.weight

            return loss, {
                "sat_ratios": sat_ratios,
                "zones": zones,
                "mean_sat": sum(sat_ratios) / max(len(sat_ratios), 1),
                "plateau_pct": zones.count("plateau") / max(B, 1),
                "coherent_pct": zones.count("coherent") / max(B, 1),
            }
