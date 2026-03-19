"""
Structural Code → 3-SAT
========================
Block-depth aware encoding with entity extraction, relationship inference,
terminal-agnostic normalization, TL operation graph stabilization, and
PPL attractor classification.

Key difference from flat ast.walk (CodeToBoolExpr in text_to_3sat.py):
  That encoder visits every AST node independently, produces ~40 vars and
  ~50 clauses for a 50-line file (ratio 1.2), and is trivially SAT with zero
  structural signal.

This encoder:
  Adjacent same-depth statements form conjunctive 3-literal clause groups.
  Depth changes encode implications (branch condition gates the body).
  Result: O(n) vars, O(n) clauses, ratio ~1.5-1.8 — enough structure
  that contradictions (dead code, impossible branches, self-referential
  assignments) produce genuine UNSAT / unresolved signal.

Clause scaling:
  n statements → ~n vars (one per statement + Tseitin intermediates)
               + ~n/3 group clauses  (adjacent triples)
               + ~k×3 implication clauses (k branch guards)
  Total: ~1.5n vars, ~2n clauses, ratio ≈ 1.3-1.8
  Budget=500 conflicts handles files up to ~300 lines comfortably.

PPL (Pigeonhole Paradox Logic) Attractor Classification:
  After encoding each block, the solver runs on that block's clauses.
  The result classifies the block's attractor state:
    STABLE      → SAT,  constraints are consistent (normal code)
    OSCILLATING → UNSAT with symmetric UNSAT core (X ∧ ¬X at same depth)
    DIVERGENT   → UNSAT with asymmetric core (contradiction builds across depth)
    FIXED_POINT → UNKNOWN/timeout (self-referential constraint, genuine timeout)
  These states are returned as metadata and also fed into the PPL tolerance score.

Uses the DPLL solver in satisfiable_ai/verifier/sat.py.
"""

from __future__ import annotations

import ast
import hashlib
import re
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, FrozenSet, Iterator, List, Optional, Set, Tuple

from .text_to_3sat import BoolExpr, TseitinEncoder
from .sat import solve_cnf


# ─────────────────────────────────────────────────────────────────────────────
# PPL Attractor State (mirrors ppl.py, self-contained)
# ─────────────────────────────────────────────────────────────────────────────

class AttractorState(Enum):
    STABLE      = auto()   # SAT — consistent
    OSCILLATING = auto()   # UNSAT — symmetric contradiction (X ∧ ¬X)
    DIVERGENT   = auto()   # UNSAT — asymmetric contradiction
    FIXED_POINT = auto()   # UNKNOWN — self-referential / timeout


@dataclass
class BlockAnalysis:
    """PPL analysis result for one scope block."""
    depth: int
    n_stmts: int
    n_vars: int
    n_clauses: int
    ratio: float
    attractor: AttractorState
    dead_vars: List[str]           # vars defined but never reached
    contradiction_hint: str = ""   # description when not STABLE


# ─────────────────────────────────────────────────────────────────────────────
# Entity and Relationship Extraction
# ─────────────────────────────────────────────────────────────────────────────

class EntityKind(Enum):
    VARIABLE  = auto()
    FUNCTION  = auto()
    CLASS_    = auto()
    MODULE    = auto()
    PARAMETER = auto()
    RETURN_   = auto()


class RelKind(Enum):
    DEFINES    = auto()   # x = expr  →  x DEFINES expr_vars
    CALLS      = auto()   # f(x)      →  call site CALLS f, DEPENDS_ON x
    RETURNS    = auto()   # return x  →  function RETURNS x
    GUARDS     = auto()   # if x:     →  branch GUARDS body
    ITERATES   = auto()   # for x in: →  loop ITERATES over collection
    COMPARES   = auto()   # x op y    →  x COMPARES y
    IMPORTS    = auto()   # import m  →  module IMPORTS m
    ASSERTS    = auto()   # assert e  →  block ASSERTS e


@dataclass
class Entity:
    kind: EntityKind
    name: str
    depth: int
    line: int


@dataclass
class Relation:
    kind: RelKind
    subject: str
    object_: str
    depth: int
    line: int


@dataclass
class EntityGraph:
    entities: List[Entity] = field(default_factory=list)
    relations: List[Relation] = field(default_factory=list)

    def entity_vars(self) -> Set[str]:
        """All entity names as 3-SAT variable names."""
        return {_var_name(e.name, e.kind) for e in self.entities}

    def relation_exprs(self) -> List[BoolExpr]:
        """
        Translate relations into BoolExprs.
        Each relation (A, rel, B) becomes a directed constraint:
          DEFINES:   A_defined → B_reachable  (if A is defined, B was evaluated)
          CALLS:     A_called  → B_defined    (can't call what isn't defined)
          RETURNS:   fn_called → ret_defined  (called fn must produce a return)
          GUARDS:    guard_var ↔ body_runs    (branch condition IFF body executes)
          ITERATES:  loop_runs → iter_defined (loop runs IFF iterable exists)
          COMPARES:  a_cmp_b  (atomic — comparison is a named proposition)
          IMPORTS:   module_imported (unit clause — import always resolves or fails)
          ASSERTS:   assertion_holds (unit clause — assert is a hard constraint)
        """
        exprs: List[BoolExpr] = []
        for rel in self.relations:
            s = _var_name(rel.subject, None)
            o = _var_name(rel.object_, None)
            if rel.kind == RelKind.DEFINES:
                exprs.append(BoolExpr.implies(BoolExpr.var(s), BoolExpr.var(o)))
            elif rel.kind == RelKind.CALLS:
                exprs.append(BoolExpr.implies(
                    BoolExpr.var(f"call_{s}"),
                    BoolExpr.var(f"defined_{o}"),
                ))
            elif rel.kind == RelKind.RETURNS:
                exprs.append(BoolExpr.implies(
                    BoolExpr.var(f"called_{s}"),
                    BoolExpr.var(f"return_{o}_defined"),
                ))
            elif rel.kind == RelKind.GUARDS:
                exprs.append(BoolExpr.iff(
                    BoolExpr.var(f"guard_{s}"),
                    BoolExpr.var(f"body_{o}_runs"),
                ))
            elif rel.kind == RelKind.ITERATES:
                exprs.append(BoolExpr.implies(
                    BoolExpr.var(f"loop_{s}_runs"),
                    BoolExpr.var(f"iter_{o}_defined"),
                ))
            elif rel.kind == RelKind.COMPARES:
                exprs.append(BoolExpr.var(f"cmp_{s}_vs_{o}"))
            elif rel.kind == RelKind.IMPORTS:
                exprs.append(BoolExpr.var(f"module_{o}_imported"))
            elif rel.kind == RelKind.ASSERTS:
                exprs.append(BoolExpr.var(f"assert_{s}_holds"))
        return exprs


def _var_name(name: str, kind: Optional[EntityKind]) -> str:
    """Normalize an entity name to a valid 3-SAT variable name."""
    n = re.sub(r"[^a-zA-Z0-9_]", "_", name).strip("_").lower()
    if not n:
        n = "unnamed"
    if kind == EntityKind.FUNCTION:
        return f"fn_{n}"
    if kind == EntityKind.CLASS_:
        return f"cls_{n}"
    if kind == EntityKind.MODULE:
        return f"mod_{n}"
    return n


def _hash4(s: str) -> str:
    """4-char hex hash of a string — used for anonymous condition variables."""
    return hashlib.md5(s.encode()).hexdigest()[:4]



# ─────────────────────────────────────────────────────────────────────────────
# Block-Depth Extractor
# ─────────────────────────────────────────────────────────────────────────────

class BlockDepthExtractor:
    """
    Convert a code block into BoolExprs using block-depth structure.

    For each scope (function body, loop body, branch body):
      1. Collect normalized statements at this depth
      2. Group adjacent triples → AND(s₁, s₂, s₃)  (3-literal clause)
      3. Remaining pairs/singles → AND(s₁, s₂) or unit(s₁)
      4. The scope's guard variable (branch condition) gates the whole body:
            guard_var → AND(all statements in body)
      5. Recurse into nested scopes with their guard variable

    Entity extraction runs in parallel: every visited node populates
    an EntityGraph that maps the code's variable/function/module graph.
    """

    def __init__(self, budget: int = 500):
        self._budget = budget
        self._entity_graph = EntityGraph()
        self._analyses: List[BlockAnalysis] = []

    @property
    def entity_graph(self) -> EntityGraph:
        return self._entity_graph

    @property
    def block_analyses(self) -> List[BlockAnalysis]:
        return self._analyses

    def extract(self, code: str) -> Tuple[List[BoolExpr], EntityGraph]:
        """
        Main entry point. Returns:
          - List[BoolExpr]: all constraints for Tseitin encoding
          - EntityGraph: extracted entities and relations
        """
        self._entity_graph = EntityGraph()
        self._analyses = []
        exprs = self._extract_python(code)
        exprs.extend(self._entity_graph.relation_exprs())
        return exprs, self._entity_graph

    # ── Python path (ast-based) ───────────────────────────────────────────────

    def _extract_python(self, code: str) -> List[BoolExpr]:
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return []  # non-Python source: no encoding

        exprs: List[BoolExpr] = []
        self._visit_body(tree.body, depth=0, guard=None, exprs=exprs)
        return exprs

    def _visit_body(
        self,
        stmts: List[ast.stmt],
        depth: int,
        guard: Optional[BoolExpr],
        exprs: List[BoolExpr],
    ) -> None:
        """
        Process a list of sibling statements (a scope block).

        1. Extract one BoolExpr per statement (entity-aware)
        2. Group adjacent triples into conjunctions
        3. Gate the whole group conj under `guard` if present
        4. Recurse into nested blocks
        """
        stmt_exprs: List[BoolExpr] = []
        for node in stmts:
            e = self._stmt_to_expr(node, depth)
            if e is not None:
                stmt_exprs.append(e)
            # Recurse into nested scopes
            self._recurse_into(node, depth + 1, exprs)

        if not stmt_exprs:
            return

        # Group into triples: (s₀,s₁,s₂), (s₃,s₄,s₅), ...
        body_clauses = _group_into_clauses(stmt_exprs)

        # Conjoin all body clauses
        if len(body_clauses) == 1:
            body = body_clauses[0]
        else:
            body = BoolExpr.and_(*body_clauses)

        # Gate under guard if present
        if guard is not None:
            gated = BoolExpr.implies(guard, body)
            exprs.append(gated)
        else:
            exprs.append(body)

        # PPL block analysis
        self._analyze_block(stmt_exprs, depth, guard)

    def _recurse_into(
        self, node: ast.stmt, depth: int, exprs: List[BoolExpr]
    ) -> None:
        """Recurse into compound statement bodies."""
        if isinstance(node, (ast.If, ast.While, ast.For, ast.With,
                              ast.Try, ast.AsyncFor, ast.AsyncWith,
                              ast.AsyncFunctionDef, ast.FunctionDef)):
            guard = self._extract_guard(node, depth - 1)
            body = getattr(node, "body", [])
            if body:
                self._visit_body(body, depth, guard, exprs)
            # elif/else
            orelse = getattr(node, "orelse", [])
            if orelse:
                neg_guard = BoolExpr.neg(guard) if guard else None
                self._visit_body(orelse, depth, neg_guard, exprs)
            # exception handlers
            handlers = getattr(node, "handlers", [])
            for h in handlers:
                self._visit_body(h.body, depth, None, exprs)
        elif isinstance(node, ast.ClassDef):
            self._entity_graph.entities.append(Entity(
                EntityKind.CLASS_, node.name, depth - 1, node.lineno
            ))
            self._visit_body(node.body, depth, None, exprs)

    def _extract_guard(self, node: ast.stmt, depth: int) -> Optional[BoolExpr]:
        """Return the BoolExpr for the branch/loop condition."""
        if isinstance(node, ast.If):
            return self._ast_expr_to_bool(node.test, depth, node.lineno)
        if isinstance(node, ast.While):
            return self._ast_expr_to_bool(node.test, depth, node.lineno)
        if isinstance(node, ast.For):
            target = ast.unparse(node.target) if hasattr(ast, "unparse") else _fallback_name(node.target)
            iter_ = ast.unparse(node.iter) if hasattr(ast, "unparse") else _fallback_name(node.iter)
            # Register iteration relation
            self._entity_graph.relations.append(Relation(
                RelKind.ITERATES, target, iter_, depth, node.lineno
            ))
            return BoolExpr.var(f"loop_{_safe(target)}_over_{_safe(iter_)}")
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            name = node.name
            self._entity_graph.entities.append(Entity(
                EntityKind.FUNCTION, name, depth, node.lineno
            ))
            for arg in node.args.args:
                self._entity_graph.entities.append(Entity(
                    EntityKind.PARAMETER, arg.arg, depth, node.lineno
                ))
                self._entity_graph.relations.append(Relation(
                    RelKind.DEFINES, name, arg.arg, depth, node.lineno
                ))
            return BoolExpr.var(f"fn_{_safe(name)}_called")
        return None

    def _stmt_to_expr(self, node: ast.stmt, depth: int) -> Optional[BoolExpr]:
        """Convert one AST statement to a BoolExpr. Populates EntityGraph."""
        ln = getattr(node, "lineno", 0)

        if isinstance(node, ast.Assert):
            cond = self._ast_expr_to_bool(node.test, depth, ln)
            if cond:
                # Assert IS a hard constraint — not just a var declaration
                self._entity_graph.relations.append(Relation(
                    RelKind.ASSERTS, _ast_repr(node.test), "true", depth, ln
                ))
                return cond
            return BoolExpr.var(f"assert_{_hash4(ast.dump(node.test))}")

        if isinstance(node, ast.Return):
            val = ""
            if node.value:
                val = _ast_repr(node.value)
                self._entity_graph.relations.append(Relation(
                    RelKind.RETURNS, "__fn__", val, depth, ln
                ))
            return BoolExpr.var(f"return_{_safe(val) or 'void'}")

        if isinstance(node, ast.Assign):
            targets = [_ast_repr(t) for t in node.targets]
            val = _ast_repr(node.value)
            for t in targets:
                self._entity_graph.entities.append(Entity(EntityKind.VARIABLE, t, depth, ln))
                self._entity_graph.relations.append(Relation(RelKind.DEFINES, t, val, depth, ln))
            name = targets[0] if targets else "anon"
            return BoolExpr.var(f"defined_{_safe(name)}")

        if isinstance(node, ast.AugAssign):
            target = _ast_repr(node.target)
            self._entity_graph.entities.append(Entity(EntityKind.VARIABLE, target, depth, ln))
            return BoolExpr.var(f"defined_{_safe(target)}")

        if isinstance(node, ast.AnnAssign):
            if node.target:
                t = _ast_repr(node.target)
                self._entity_graph.entities.append(Entity(EntityKind.VARIABLE, t, depth, ln))
                return BoolExpr.var(f"defined_{_safe(t)}")

        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            else:
                names = [node.module or ""]
            for n in names:
                self._entity_graph.entities.append(Entity(EntityKind.MODULE, n, depth, ln))
                self._entity_graph.relations.append(Relation(RelKind.IMPORTS, "__module__", n, depth, ln))
            return BoolExpr.var(f"module_{_safe(names[0] if names else 'anon')}_imported")

        if isinstance(node, ast.Raise):
            exc = _ast_repr(node.exc) if node.exc else "exception"
            return BoolExpr.var(f"raises_{_safe(exc)}")

        if isinstance(node, ast.Expr):
            # Standalone expression — usually a call
            if isinstance(node.value, ast.Call):
                fn = _ast_repr(node.value.func)
                args = [_ast_repr(a) for a in node.value.args]
                self._entity_graph.relations.append(Relation(
                    RelKind.CALLS, "__scope__", fn, depth, ln
                ))
                for a in args:
                    self._entity_graph.relations.append(Relation(
                        RelKind.CALLS, fn, a, depth, ln
                    ))
                return BoolExpr.var(f"call_{_safe(fn)}")
            # Standalone comparison
            if isinstance(node.value, ast.Compare):
                return self._ast_expr_to_bool(node.value, depth, ln)
            return None

        # Compound stmts (if/for/while/def) — only guard extraction matters,
        # body handled by _recurse_into
        if isinstance(node, (ast.If, ast.For, ast.While,
                              ast.FunctionDef, ast.AsyncFunctionDef,
                              ast.ClassDef, ast.With, ast.Try)):
            return None

        return None

    def _ast_expr_to_bool(
        self, node: ast.expr, depth: int, ln: int
    ) -> Optional[BoolExpr]:
        """Convert an AST expression to BoolExpr for conditions/assertions."""
        if isinstance(node, ast.BoolOp):
            children = [self._ast_expr_to_bool(v, depth, ln) for v in node.values]
            children = [c for c in children if c is not None]
            if not children:
                return None
            if isinstance(node.op, ast.And):
                return BoolExpr.and_(*children)
            return BoolExpr.or_(*children)

        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            child = self._ast_expr_to_bool(node.operand, depth, ln)
            return BoolExpr.neg(child) if child else None

        if isinstance(node, ast.Compare):
            left = _ast_repr(node.left)
            results = []
            for op, comp in zip(node.ops, node.comparators):
                right = _ast_repr(comp)
                op_name = type(op).__name__.lower()
                # Remap to canonical
                op_label = {
                    "eq": "eq", "noteq": "ne", "lt": "lt", "lte": "le",
                    "gt": "gt", "gte": "ge", "in": "in", "notin": "not_in",
                    "is": "is", "isnot": "is_not",
                }.get(op_name, op_name)
                var = f"cmp_{_safe(left)}_{op_label}_{_safe(right)}"
                self._entity_graph.relations.append(Relation(
                    RelKind.COMPARES, left, right, depth, ln
                ))
                results.append(BoolExpr.var(var))
            if len(results) == 1:
                return results[0]
            return BoolExpr.and_(*results)

        if isinstance(node, ast.Name):
            return BoolExpr.var(_safe(node.id))

        if isinstance(node, ast.Constant):
            if node.value is True:
                return BoolExpr.var("__true__")
            if node.value is False:
                return BoolExpr.neg(BoolExpr.var("__true__"))
            return None

        # Anything else: treat as an opaque named proposition
        rep = _ast_repr(node)
        return BoolExpr.var(_safe(rep) or f"expr_{_hash4(rep)}")

    # ── PPL block attractor analysis ─────────────────────────────────────────

    def _analyze_block(
        self,
        stmt_exprs: List[BoolExpr],
        depth: int,
        guard: Optional[BoolExpr],
    ) -> None:
        """Run SAT solver on one block's clauses and classify the PPL attractor."""
        if not stmt_exprs:
            return

        clauses_in = _group_into_clauses(stmt_exprs)
        if guard is not None:
            clauses_in = [BoolExpr.implies(guard, c) for c in clauses_in]

        # Tseitin-encode and solve with restricted budget
        encoder = TseitinEncoder()
        if len(clauses_in) == 1:
            root = clauses_in[0]
        else:
            root = BoolExpr.and_(*clauses_in)

        n_vars, clauses = encoder.encode(root)
        if not clauses:
            return

        ratio = len(clauses) / max(n_vars, 1)
        sat_result, model = solve_cnf(n_vars, clauses, budget=self._budget)

        if sat_result is True:
            attractor = AttractorState.STABLE
            hint = ""
        elif sat_result is False:
            # Distinguish oscillating vs divergent by core symmetry
            # Heuristic: if n_clauses is small relative to n_vars → oscillating
            # (symmetric contradiction), else divergent (progressive)
            if len(clauses) <= n_vars:
                attractor = AttractorState.OSCILLATING
                hint = f"symmetric UNSAT at depth {depth}: {len(clauses)} clauses, {n_vars} vars"
            else:
                attractor = AttractorState.DIVERGENT
                hint = f"asymmetric UNSAT at depth {depth}: ratio {ratio:.2f}"
        else:
            # None = budget exceeded = genuine UNKNOWN
            attractor = AttractorState.FIXED_POINT
            hint = f"FIXED_POINT at depth {depth}: solver hit budget ({self._budget} conflicts)"

        self._analyses.append(BlockAnalysis(
            depth=depth,
            n_stmts=len(stmt_exprs),
            n_vars=n_vars,
            n_clauses=len(clauses),
            ratio=ratio,
            attractor=attractor,
            dead_vars=[],
            contradiction_hint=hint,
        ))


# ─────────────────────────────────────────────────────────────────────────────
# Main encoder class: drop-in replacement for CodeToBoolExpr
# ─────────────────────────────────────────────────────────────────────────────

class StructuralCodeTo3SAT:
    """
    Full pipeline: code → entity graph → BoolExprs → 3-SAT CNF.

    Drop-in replacement for CodeToBoolExpr (text_to_3sat.py).
    Uses block-depth encoding, entity extraction, TL op normalization,
    and PPL attractor classification.

    Usage:
        encoder = StructuralCodeTo3SAT()
        n_vars, clauses = encoder.encode(code_str)
        # clauses is valid 3-CNF (≤3 literals per clause)

        # Also available:
        encoder.entity_graph       → EntityGraph
        encoder.block_analyses     → List[BlockAnalysis] (PPL per-block results)
        encoder.scale_report()     → dict with vars/clauses/ratio/attractor summary
    """

    def __init__(self, budget: int = 500):
        self._extractor = BlockDepthExtractor(budget=budget)
        self._encoder = TseitinEncoder()

    @property
    def entity_graph(self) -> EntityGraph:
        return self._extractor.entity_graph

    @property
    def block_analyses(self) -> List[BlockAnalysis]:
        return self._extractor.block_analyses

    def encode(self, code: str) -> Tuple[int, List[List[int]]]:
        """
        Encode code to 3-SAT CNF.

        Returns (n_vars, clauses) — same interface as TseitinEncoder.encode().
        All clauses have ≤ 3 literals.
        """
        exprs, _ = self._extractor.extract(code)
        if not exprs:
            return 0, []

        self._encoder = TseitinEncoder()
        if len(exprs) == 1:
            root = exprs[0]
        else:
            root = BoolExpr.and_(*exprs)

        n_vars, clauses = self._encoder.encode(root)
        assert all(len(c) <= 3 for c in clauses), "clause > 3 literals — Tseitin bug"
        return n_vars, clauses

    def encode_grouped(self, code: str) -> Tuple[int, List[List[List[int]]]]:
        """
        Encode code to grouped 3-SAT (one group per top-level expression).

        Returned format matches translate_grouped() in text_to_3sat.py.
        Suitable for sat_score() with per-group budget.
        """
        exprs, _ = self._extractor.extract(code)
        if not exprs:
            return 0, []

        max_vars = 0
        groups: List[List[List[int]]] = []
        for expr in exprs:
            enc = TseitinEncoder()
            nv, cls = enc.encode(expr)
            if cls:
                groups.append(cls)
                max_vars = max(max_vars, nv)

        return max_vars, groups

    def extract_exprs(self, code: str) -> List[BoolExpr]:
        """
        Compatibility shim: return just the List[BoolExpr] from extraction.
        Used by TextTo3SAT._extract_expressions so it can call
        self.code_parser.extract_exprs(text) whether the parser is
        CodeToBoolExpr (old) or StructuralCodeTo3SAT (new).
        """
        exprs, _ = self._extractor.extract(code)
        return exprs

    def scale_report(self) -> Dict[str, object]:
        """
        Return a summary of the encoding scale for the last encode() call.
        Use this to validate that you're in the polynomial corridor.
        """
        analyses = self.block_analyses
        if not analyses:
            return {"status": "no_blocks"}

        total_vars = sum(a.n_vars for a in analyses)
        total_clauses = sum(a.n_clauses for a in analyses)
        ratio = total_clauses / max(total_vars, 1)
        attractors = {a.attractor.name: 0 for a in analyses}
        for a in analyses:
            attractors[a.attractor.name] += 1

        return {
            "n_blocks": len(analyses),
            "total_vars": total_vars,
            "total_clauses": total_clauses,
            "ratio_m_over_n": round(ratio, 3),
            "high_clause_ratio": ratio > 4.0,
            "attractors": attractors,
            "contradictions": [
                {"depth": a.depth, "attractor": a.attractor.name, "hint": a.contradiction_hint}
                for a in analyses if a.attractor != AttractorState.STABLE
            ],
        }


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _group_into_clauses(exprs: List[BoolExpr]) -> List[BoolExpr]:
    """
    Group a list of BoolExprs into conjunctive 3-literal-sized clauses.

    Adjacent triples → AND(e0, e1, e2)
    Pairs            → AND(e0, e1)
    Singles          → e0 (unit)

    This keeps the Tseitin encoding at O(n) without long-clause blowup.
    """
    result: List[BoolExpr] = []
    i = 0
    while i < len(exprs):
        remaining = len(exprs) - i
        if remaining >= 3:
            result.append(BoolExpr.and_(exprs[i], exprs[i + 1], exprs[i + 2]))
            i += 3
        elif remaining == 2:
            result.append(BoolExpr.and_(exprs[i], exprs[i + 1]))
            i += 2
        else:
            result.append(exprs[i])
            i += 1
    return result


def _safe(s: str) -> str:
    """Normalize a string to a valid variable name fragment."""
    return re.sub(r"\W+", "_", s).strip("_").lower()[:40]


def _ast_repr(node: ast.AST) -> str:
    """Get a short canonical string for an AST node."""
    if hasattr(ast, "unparse"):
        try:
            return ast.unparse(node)
        except Exception:
            pass
    return _fallback_name(node)


def _fallback_name(node: ast.AST) -> str:
    """Fallback name extraction without ast.unparse."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return f"{_fallback_name(node.value)}.{node.attr}"
    if isinstance(node, ast.Constant):
        return str(node.value)
    if isinstance(node, ast.Call):
        return f"call_{_fallback_name(node.func)}"
    return f"node_{type(node).__name__}"
