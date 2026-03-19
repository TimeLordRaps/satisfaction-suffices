"""
Text → 3-SAT — Automatic Constraint Translation
==================================================
The bridge between human-readable content and machine-verifiable
propositional logic. Every dataset sample must cross this bridge
before verification.

The pipeline:
    raw text → parse → propositions → boolean formula → Tseitin → 3-SAT CNF

This module handles the full translation for every domain:
    - Natural language reasoning → logical structure → 3-SAT
    - Math problems → arithmetic constraints → bounded encoding → 3-SAT
    - Code → AST → control/data flow → boolean constraints → 3-SAT
    - Proofs → proof obligations → implications → 3-SAT
    - Chain-of-thought → step consistency → 3-SAT

Key transformation: Tseitin encoding
    Any boolean formula → equisatisfiable 3-CNF with linear blowup.
    For each sub-expression, introduce a fresh variable that represents
    its truth value, then add 3-SAT clauses constraining that variable.

    Example: (A ∧ B) → C
    1. Fresh var x₁ = (A ∧ B):  (¬x₁∨A), (¬x₁∨B), (¬A∨¬B∨x₁)
    2. Fresh var x₂ = (x₁ → C): (x₁∨x₂), (¬C∨x₂), (¬x₁∨C∨¬x₂)
    3. Unit clause: (x₂)  [the formula must be true]

    Every clause has ≤ 3 literals. Always.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Set, Tuple, Union


# ── Boolean Formula AST ──────────────────────────────────────────────────────

class BoolOp(Enum):
    VAR = auto()
    NOT = auto()
    AND = auto()
    OR = auto()
    IMPLIES = auto()
    IFF = auto()
    XOR = auto()


@dataclass
class BoolExpr:
    """A node in a boolean formula tree."""
    op: BoolOp
    name: str = ""                    # only for VAR
    children: List["BoolExpr"] = field(default_factory=list)

    @staticmethod
    def var(name: str) -> "BoolExpr":
        return BoolExpr(op=BoolOp.VAR, name=name)

    @staticmethod
    def neg(child: "BoolExpr") -> "BoolExpr":
        return BoolExpr(op=BoolOp.NOT, children=[child])

    @staticmethod
    def and_(*children: "BoolExpr") -> "BoolExpr":
        return BoolExpr(op=BoolOp.AND, children=list(children))

    @staticmethod
    def or_(*children: "BoolExpr") -> "BoolExpr":
        return BoolExpr(op=BoolOp.OR, children=list(children))

    @staticmethod
    def implies(ante: "BoolExpr", cons: "BoolExpr") -> "BoolExpr":
        return BoolExpr(op=BoolOp.IMPLIES, children=[ante, cons])

    @staticmethod
    def iff(left: "BoolExpr", right: "BoolExpr") -> "BoolExpr":
        return BoolExpr(op=BoolOp.IFF, children=[left, right])

    @staticmethod
    def xor(left: "BoolExpr", right: "BoolExpr") -> "BoolExpr":
        return BoolExpr(op=BoolOp.XOR, children=[left, right])


# ── Tseitin Transformation ───────────────────────────────────────────────────

class TseitinEncoder:
    """
    Convert arbitrary boolean formulas to equisatisfiable 3-CNF.

    Tseitin's transformation introduces a fresh variable for each
    sub-expression and adds clauses constraining it. The result is
    always in 3-CNF (every clause has at most 3 literals) with only
    a linear increase in variables and clauses.

    This is the canonical way to convert arbitrary propositional
    formulas to SAT solver input.
    """

    def __init__(self):
        self._var_map: Dict[str, int] = {}  # name → var id (1-indexed)
        self._n_vars: int = 0
        self._clauses: List[List[int]] = []

    def _fresh(self, label: str = "") -> int:
        """Create a fresh Tseitin variable."""
        self._n_vars += 1
        if label:
            self._var_map[f"__tseitin_{label}_{self._n_vars}"] = self._n_vars
        return self._n_vars

    def _named_var(self, name: str) -> int:
        """Get or create a named propositional variable."""
        if name not in self._var_map:
            self._n_vars += 1
            self._var_map[name] = self._n_vars
        return self._var_map[name]

    def _lit(self, var: int, positive: bool = True) -> int:
        """Convert var id to signed literal."""
        return var if positive else -var

    def encode(self, expr: BoolExpr) -> Tuple[int, List[List[int]]]:
        """
        Encode a BoolExpr into 3-CNF.

        Returns (n_vars, clauses) where each clause is a list of
        signed ints (positive = true, negative = false).

        The root expression is asserted true (added as unit clause).
        """
        self._var_map = {}
        self._n_vars = 0
        self._clauses = []

        root_var = self._encode_recursive(expr)

        # Assert the root is true
        self._clauses.append([root_var])

        return self._n_vars, list(self._clauses)

    def _encode_recursive(self, expr: BoolExpr) -> int:
        """
        Recursively encode, returning the variable representing
        this sub-expression's truth value.
        """
        if expr.op == BoolOp.VAR:
            return self._named_var(expr.name)

        elif expr.op == BoolOp.NOT:
            child_var = self._encode_recursive(expr.children[0])
            out = self._fresh("not")
            # out ↔ ¬child:
            #   (out ∨ child), (¬out ∨ ¬child)
            self._clauses.append([out, child_var])
            self._clauses.append([-out, -child_var])
            return out

        elif expr.op == BoolOp.AND:
            child_vars = [self._encode_recursive(c) for c in expr.children]
            out = self._fresh("and")
            # out → (c1 ∧ c2 ∧ ...):  (¬out ∨ ci) for each ci
            for cv in child_vars:
                self._clauses.append([-out, cv])
            # (c1 ∧ c2 ∧ ...) → out:  (¬c1 ∨ ¬c2 ∨ ... ∨ out)
            # If more than 2 children, need to break into 3-literal clauses
            neg_children = [-cv for cv in child_vars]
            self._add_long_clause(neg_children + [out])
            return out

        elif expr.op == BoolOp.OR:
            child_vars = [self._encode_recursive(c) for c in expr.children]
            out = self._fresh("or")
            # out → (c1 ∨ c2 ∨ ...): (¬out ∨ c1 ∨ c2 ∨ ...)
            self._add_long_clause([-out] + child_vars)
            # (c1 ∨ c2 ∨ ...) → out: (¬ci ∨ out) for each ci
            for cv in child_vars:
                self._clauses.append([-cv, out])
            return out

        elif expr.op == BoolOp.IMPLIES:
            # A → B  ≡  ¬A ∨ B
            a = self._encode_recursive(expr.children[0])
            b = self._encode_recursive(expr.children[1])
            out = self._fresh("implies")
            # out ↔ (¬A ∨ B):
            #   (¬out ∨ ¬A ∨ B)
            #   (A ∨ out)
            #   (¬B ∨ out)
            self._clauses.append([-out, -a, b])
            self._clauses.append([a, out])
            self._clauses.append([-b, out])
            return out

        elif expr.op == BoolOp.IFF:
            # A ↔ B  ≡  (A → B) ∧ (B → A)
            a = self._encode_recursive(expr.children[0])
            b = self._encode_recursive(expr.children[1])
            out = self._fresh("iff")
            # out ↔ (A ↔ B):
            #   (¬out ∨ ¬A ∨ B), (¬out ∨ A ∨ ¬B)
            #   (¬A ∨ ¬B ∨ out), (A ∨ B ∨ out)
            self._clauses.append([-out, -a, b])
            self._clauses.append([-out, a, -b])
            self._clauses.append([-a, -b, out])
            self._clauses.append([a, b, out])
            return out

        elif expr.op == BoolOp.XOR:
            # A ⊕ B  ≡  (A ∨ B) ∧ ¬(A ∧ B)
            a = self._encode_recursive(expr.children[0])
            b = self._encode_recursive(expr.children[1])
            out = self._fresh("xor")
            # out ↔ (A ⊕ B):
            #   (¬out ∨ A ∨ B), (¬out ∨ ¬A ∨ ¬B)
            #   (out ∨ ¬A ∨ B), (out ∨ A ∨ ¬B) -- WRONG, use:
            #   (out ∨ A ∨ ¬B) is wrong. Correct:
            #   (A ∨ B ∨ ¬out), (¬A ∨ ¬B ∨ ¬out)
            #   (¬A ∨ B ∨ out), (A ∨ ¬B ∨ out)
            self._clauses.append([a, b, -out])
            self._clauses.append([-a, -b, -out])
            self._clauses.append([-a, b, out])
            self._clauses.append([a, -b, out])
            return out

        raise ValueError(f"Unknown BoolOp: {expr.op}")

    def _add_long_clause(self, lits: List[int]) -> None:
        """
        Add a clause that might have more than 3 literals.
        If > 3, introduce auxiliary variables to split into 3-SAT.

        (l1 ∨ l2 ∨ l3 ∨ l4 ∨ l5) becomes:
        (l1 ∨ l2 ∨ y1), (¬y1 ∨ l3 ∨ y2), (¬y2 ∨ l4 ∨ l5)
        """
        if len(lits) <= 3:
            self._clauses.append(lits)
            return

        # Chain splitting
        remaining = list(lits)
        while len(remaining) > 3:
            aux = self._fresh("chain")
            self._clauses.append([remaining[0], remaining[1], aux])
            remaining = [-aux] + remaining[2:]

        self._clauses.append(remaining)


# ── Text Proposition Mining ──────────────────────────────────────────────────

class PropositionMiner:
    """
    Extract atomic propositions and logical relations from text.

    This is the NLP layer that sits between raw text and boolean
    formula construction. It identifies:
    - Factual claims (propositions)
    - Logical connectives (and, or, not, if-then, iff)
    - Quantifiers (for all, exists)
    - Comparisons and equalities
    - Temporal relations (before, after, during)
    - Causal relations (because, causes, leads to)
    """

    # ── Pattern bank ──────────────────────────────────────────────

    # Logical connectives
    IF_THEN = re.compile(
        r"(?:if|when|whenever|assuming|given that|provided that)\s+(.+?)"
        r"\s*[,]?\s*(?:then|implies|means|so)\s+(.+?)(?:\.|;|$)",
        re.IGNORECASE | re.DOTALL
    )
    IFF = re.compile(
        r"(.+?)\s+(?:if and only if|iff|is equivalent to|exactly when)\s+(.+?)(?:\.|;|$)",
        re.IGNORECASE
    )
    AND = re.compile(r"\b(?:and|also|moreover|furthermore|additionally)\b", re.IGNORECASE)
    OR = re.compile(r"\b(?:or|alternatively|either)\b", re.IGNORECASE)
    NOT = re.compile(
        r"\b(?:not|never|no|none|neither|cannot|can't|won't|wouldn't|"
        r"shouldn't|doesn't|don't|isn't|aren't|wasn't|weren't|hasn't|"
        r"haven't|hadn't|impossible|false|incorrect|invalid|fails?|"
        r"violates?|contradicts?)\b",
        re.IGNORECASE
    )

    # Quantifiers
    FORALL = re.compile(
        r"(?:for (?:all|every|each|any)|all|every|each|any|∀)\s+(\w+)",
        re.IGNORECASE
    )
    EXISTS = re.compile(
        r"(?:there (?:exists?|is|are)|some|at least one|∃)\s+(\w+)",
        re.IGNORECASE
    )

    # Comparisons
    EQUALS = re.compile(r"(\w+(?:\s+\w+)?)\s*(?:=|equals?|is equal to)\s*(\w+(?:\s+\w+)?)")
    NOT_EQUALS = re.compile(r"(\w+)\s*(?:≠|!=|is not equal to|differs from)\s*(\w+)")
    LESS_THAN = re.compile(r"(\w+)\s*(?:<|is less than|is smaller than)\s*(\w+)")
    GREATER_THAN = re.compile(r"(\w+)\s*(?:>|is greater than|is larger than|exceeds)\s*(\w+)")

    # Market patterns
    PRICE_ABOVE = re.compile(
        r"(?:price|close|bid|ask|last)\s+(?:of\s+)?(\w+)\s*(?:>|above|exceeds?|over)\s*"
        r"(\$?[\d,.]+|\w+)",
        re.IGNORECASE,
    )
    PRICE_BELOW = re.compile(
        r"(?:price|close|bid|ask|last)\s+(?:of\s+)?(\w+)\s*(?:<|below|under)\s*"
        r"(\$?[\d,.]+|\w+)",
        re.IGNORECASE,
    )
    POSITION_LIMIT = re.compile(
        r"(?:position|exposure|allocation)\s+(?:in\s+)?(\w+)\s*(?:<=?|must not exceed|"
        r"capped at|limited to|max(?:imum)?)\s*(\$?[\d,.]+%?)",
        re.IGNORECASE,
    )
    STOP_LOSS = re.compile(
        r"(?:stop[\s-]?loss|risk|max(?:imum)?\s+(?:loss|drawdown))\s*(?:at|of|=|:)\s*"
        r"(\$?[\d,.]+%?)",
        re.IGNORECASE,
    )
    HEDGE_REQ = re.compile(
        r"(?:hedge|hedging|hedged)\s+(.+?)\s+(?:with|via|using|by)\s+(.+?)(?:\.|;|$)",
        re.IGNORECASE,
    )
    MARKET_BOUND = re.compile(
        r"(\w+)\s+(?:is\s+)?(?:between|in range|within)\s+"
        r"(\$?[\d,.]+)\s*(?:and|to|-)\s*(\$?[\d,.]+)",
        re.IGNORECASE,
    )
    CORRELATION = re.compile(
        r"(?:correlation|corr)\s*(?:between|of)\s*(\w+)\s*(?:and|,)\s*(\w+)\s*"
        r"(?:>|<|=|above|below|equals?)\s*([\d.+-]+)",
        re.IGNORECASE,
    )
    RATIO_CONSTRAINT = re.compile(
        r"(?:sharpe|sortino|calmar|information)\s*(?:ratio)?\s*(?:>|>=|above|exceeds?)\s*"
        r"([\d.]+)",
        re.IGNORECASE,
    )
    LONG_SHORT = re.compile(
        r"\b(long|short|buy|sell)\s+(\w+)",
        re.IGNORECASE,
    )
    LEQ = re.compile(r"(\w+)\s*(?:≤|<=|is at most|is no more than)\s*(\w+)")
    GEQ = re.compile(r"(\w+)\s*(?:≥|>=|is at least|is no less than)\s*(\w+)")

    # Causal
    BECAUSE = re.compile(
        r"(.+?)\s+(?:because|since|as|due to|owing to)\s+(.+?)(?:\.|;|$)",
        re.IGNORECASE
    )
    CAUSES = re.compile(
        r"(.+?)\s+(?:causes?|leads? to|results? in|produces?|implies?)\s+(.+?)(?:\.|;|$)",
        re.IGNORECASE
    )

    # Mathematical expressions
    MATH_EQ = re.compile(r"([a-zA-Z_]\w*)\s*([+\-*/^])\s*([a-zA-Z_]\w*)\s*=\s*([a-zA-Z_]\w*)")
    INEQUALITY = re.compile(r"(\d+)\s*([<>≤≥]=?)\s*(\w+)\s*([<>≤≥]=?)\s*(\d+)")

    def mine(self, text: str) -> List[BoolExpr]:
        """
        Extract boolean expressions from text.

        Returns a list of BoolExpr that should ALL be true
        (conjoined). Feed each to TseitinEncoder to get 3-SAT.
        """
        exprs: List[BoolExpr] = []

        # Split into sentences
        sentences = [s.strip() for s in re.split(r'(?<=[.;!?])\s+|\n+', text) if s.strip()]

        for sent in sentences:
            expr = self._parse_sentence(sent)
            if expr is not None:
                exprs.append(expr)

        return exprs

    def mine_market(self, text: str) -> List[BoolExpr]:
        """
        Extract market constraints from text.

        The Ed Thorp layer: extract verifiable edges from market text.

        Recognizes:
        - Price bounds (above/below)
        - Position limits
        - Stop-loss levels
        - Hedging requirements
        - Range constraints
        - Correlation constraints
        - Performance ratio thresholds (Sharpe, Sortino, etc.)
        - Long/short direction constraints
        """
        exprs: List[BoolExpr] = []

        # Price bounds: "price of X above $100" → price_X_above_100
        for m in self.PRICE_ABOVE.finditer(text):
            asset = m.group(1).strip()
            level = m.group(2).strip().replace("$", "").replace(",", "")
            exprs.append(BoolExpr.var(f"price_{asset}_above_{level}"))

        for m in self.PRICE_BELOW.finditer(text):
            asset = m.group(1).strip()
            level = m.group(2).strip().replace("$", "").replace(",", "")
            exprs.append(BoolExpr.var(f"price_{asset}_below_{level}"))

        # Range constraints: "X between 50 and 100" → X_above_50 AND X_below_100
        for m in self.MARKET_BOUND.finditer(text):
            asset = m.group(1).strip()
            lo = m.group(2).strip().replace("$", "").replace(",", "")
            hi = m.group(3).strip().replace("$", "").replace(",", "")
            above = BoolExpr.var(f"{asset}_above_{lo}")
            below = BoolExpr.var(f"{asset}_below_{hi}")
            exprs.append(BoolExpr.and_(above, below))

        # Position limits: "position in X max 10%" → position_X_within_limit
        for m in self.POSITION_LIMIT.finditer(text):
            asset = m.group(1).strip()
            limit_val = m.group(2).strip().replace("$", "").replace(",", "").replace("%", "pct")
            exprs.append(BoolExpr.var(f"position_{asset}_within_{limit_val}"))

        # Stop-loss: "stop-loss at 2%" → stop_loss_respected
        for m in self.STOP_LOSS.finditer(text):
            level = m.group(1).strip().replace("$", "").replace(",", "").replace("%", "pct")
            exprs.append(BoolExpr.var(f"stop_loss_{level}_respected"))

        # Hedging: "hedge X with Y" → hedge_X_implies_Y
        for m in self.HEDGE_REQ.finditer(text):
            target = m.group(1).strip()
            instrument = m.group(2).strip()
            # If you hold the target, you must hold the hedge
            t_var = BoolExpr.var(f"holds_{target}")
            h_var = BoolExpr.var(f"holds_{instrument}")
            exprs.append(BoolExpr.implies(t_var, h_var))

        # Correlation: "correlation of X and Y > 0.5" → corr_X_Y_above_0.5
        for m in self.CORRELATION.finditer(text):
            a = m.group(1).strip()
            b = m.group(2).strip()
            threshold = m.group(3).strip()
            exprs.append(BoolExpr.var(f"corr_{a}_{b}_satisfied_{threshold}"))

        # Ratio thresholds: "sharpe ratio > 1.5" → sharpe_above_1.5
        for m in self.RATIO_CONSTRAINT.finditer(text):
            # The regex captures the ratio name in context; extract it
            full = m.group(0).lower()
            for name in ("sharpe", "sortino", "calmar", "information"):
                if name in full:
                    threshold = m.group(1).strip()
                    exprs.append(BoolExpr.var(f"{name}_above_{threshold}"))
                    break

        # Long/short direction: creates directional propositions
        long_assets = set()
        short_assets = set()
        for m in self.LONG_SHORT.finditer(text):
            direction = m.group(1).lower()
            asset = m.group(2).strip()
            if direction in ("long", "buy"):
                long_assets.add(asset)
                exprs.append(BoolExpr.var(f"long_{asset}"))
            else:
                short_assets.add(asset)
                exprs.append(BoolExpr.var(f"short_{asset}"))

        # Mutual exclusion: can't be both long AND short same asset
        for asset in long_assets & short_assets:
            long_v = BoolExpr.var(f"long_{asset}")
            short_v = BoolExpr.var(f"short_{asset}")
            # ¬(long ∧ short) → ¬long ∨ ¬short
            exprs.append(BoolExpr.or_(BoolExpr.neg(long_v), BoolExpr.neg(short_v)))

        # Also mine general propositions from the text
        exprs.extend(self.mine(text))

        return exprs

    def _parse_sentence(self, sent: str) -> Optional[BoolExpr]:
        """Parse a single sentence into a BoolExpr."""

        # Try if-and-only-if first (more specific)
        m = self.IFF.search(sent)
        if m:
            left = self._atom(m.group(1))
            right = self._atom(m.group(2))
            return BoolExpr.iff(left, right)

        # Try if-then
        m = self.IF_THEN.search(sent)
        if m:
            ante = self._parse_compound(m.group(1))
            cons = self._parse_compound(m.group(2))
            return BoolExpr.implies(ante, cons)

        # Try causal (X because Y → Y implies X)
        m = self.BECAUSE.search(sent)
        if m:
            effect = self._atom(m.group(1))
            cause = self._atom(m.group(2))
            return BoolExpr.implies(cause, effect)

        # Try causal (X causes Y → X implies Y)
        m = self.CAUSES.search(sent)
        if m:
            cause = self._atom(m.group(1))
            effect = self._atom(m.group(2))
            return BoolExpr.implies(cause, effect)

        # Try compound (and/or)
        if self.AND.search(sent) or self.OR.search(sent):
            return self._parse_compound(sent)

        # Try equality
        m = self.EQUALS.search(sent)
        if m:
            return BoolExpr.iff(
                BoolExpr.var(m.group(1).strip()),
                BoolExpr.var(m.group(2).strip()),
            )

        # Try inequality
        m = self.NOT_EQUALS.search(sent)
        if m:
            return BoolExpr.xor(
                BoolExpr.var(m.group(1).strip()),
                BoolExpr.var(m.group(2).strip()),
            )

        # Try comparisons (encode as boolean: "X < Y" → X_lt_Y is true)
        for pat, label in [
            (self.LESS_THAN, "lt"), (self.GREATER_THAN, "gt"),
            (self.LEQ, "leq"), (self.GEQ, "geq"),
        ]:
            m = pat.search(sent)
            if m:
                return BoolExpr.var(f"{m.group(1)}_{label}_{m.group(2)}")

        # Try quantifiers
        m = self.FORALL.search(sent)
        if m:
            # Universal: the body must hold (just assert it)
            body = self.FORALL.sub("", sent).strip()
            return self._atom(body) if body else None

        m = self.EXISTS.search(sent)
        if m:
            return BoolExpr.var(f"exists_{m.group(1)}")

        # Fall through: treat as atomic proposition
        cleaned = sent.strip().rstrip(".;!?")
        if cleaned:
            return self._atom(cleaned)

        return None

    def _parse_compound(self, text: str) -> BoolExpr:
        """Parse compound expressions with and/or."""
        # Check for OR first (lower precedence)
        parts = self.OR.split(text)
        if len(parts) > 1:
            children = [self._parse_compound(p.strip()) for p in parts]
            return BoolExpr.or_(*children)

        # Then AND
        parts = self.AND.split(text)
        if len(parts) > 1:
            children = [self._atom(p.strip()) for p in parts]
            return BoolExpr.and_(*children)

        return self._atom(text)

    def _atom(self, text: str) -> BoolExpr:
        """Create an atomic proposition, detecting negation."""
        text = text.strip().rstrip(".;!?,")
        if self.NOT.match(text) or text.lower().startswith(("not ", "no ")):
            # Negated proposition
            inner = self.NOT.sub("", text, count=1).strip()
            if inner:
                return BoolExpr.neg(BoolExpr.var(self._normalize(inner)))
            return BoolExpr.var(self._normalize(text))
        return BoolExpr.var(self._normalize(text))

    @staticmethod
    def _normalize(text: str) -> str:
        """Normalize a proposition name to a canonical form."""
        text = text.strip().lower()
        # Remove articles
        text = re.sub(r"\b(?:the|a|an)\b", "", text).strip()
        # Collapse whitespace
        text = re.sub(r"\s+", "_", text)
        # Remove non-alphanumeric except underscore
        text = re.sub(r"[^a-z0-9_]", "", text)
        return text or "unnamed"


# ── Arithmetic → Boolean Encoding ────────────────────────────────────────────

class ArithmeticEncoder:
    """
    Encode bounded arithmetic constraints as boolean formulas.

    Given constraints like "x + y = z" where variables have bounded
    domains, encode using a unary or binary representation and
    generate boolean constraints.

    Unary encoding (simple, more variables):
        x ∈ {0,1,...,N} → N+1 boolean variables x_0, x_1, ..., x_N
        x = k ↔ x_k is true ∧ all others false

    Binary encoding (compact, fewer variables):
        x ∈ {0,...,2^b-1} → b boolean variables representing bits

    We use binary encoding by default for compactness.
    """

    def __init__(self, max_val: int = 255, bits: int = 0):
        if bits > 0:
            self.bits = bits
        else:
            self.bits = max(1, max_val.bit_length())
        self.max_val = (1 << self.bits) - 1

    def encode_equality(self, x_name: str, y_name: str) -> List[BoolExpr]:
        """x = y: each bit must match → AND of IFF for each bit."""
        exprs = []
        for i in range(self.bits):
            xi = BoolExpr.var(f"{x_name}_b{i}")
            yi = BoolExpr.var(f"{y_name}_b{i}")
            exprs.append(BoolExpr.iff(xi, yi))
        return exprs

    def encode_less_than(self, x_name: str, y_name: str) -> BoolExpr:
        """
        x < y in binary: there exists a bit position k where
        y_k=1, x_k=0, and for all higher bits i>k, x_i=y_i.

        Encoded as a disjunction over possible "first differing bit"
        positions.
        """
        cases = []
        for k in range(self.bits):
            # At position k: y_k=1, x_k=0
            diff = BoolExpr.and_(
                BoolExpr.var(f"{y_name}_b{k}"),
                BoolExpr.neg(BoolExpr.var(f"{x_name}_b{k}")),
            )
            # Higher bits equal
            higher_equal = []
            for i in range(k + 1, self.bits):
                higher_equal.append(BoolExpr.iff(
                    BoolExpr.var(f"{x_name}_b{i}"),
                    BoolExpr.var(f"{y_name}_b{i}"),
                ))
            if higher_equal:
                case = BoolExpr.and_(diff, *higher_equal)
            else:
                case = diff
            cases.append(case)

        if len(cases) == 1:
            return cases[0]
        return BoolExpr.or_(*cases)

    def encode_constant(self, x_name: str, value: int) -> List[BoolExpr]:
        """x = constant: set each bit."""
        exprs = []
        for i in range(self.bits):
            xi = BoolExpr.var(f"{x_name}_b{i}")
            if (value >> i) & 1:
                exprs.append(xi)  # bit i is 1
            else:
                exprs.append(BoolExpr.neg(xi))  # bit i is 0
        return exprs


# ── Code AST → Boolean ───────────────────────────────────────────────────────

class CodeToBoolExpr:
    """
    Parse Python code AST and extract boolean constraints.

    Handles:
    - Assertions → must be true
    - If/elif/else → branch mutual exclusion + coverage
    - Comparisons → equality/inequality constraints
    - Assignments → variable equivalence
    - Function pre/post conditions
    - Loop invariants (from comments/annotations)
    """

    def extract(self, code: str) -> List[BoolExpr]:
        """Extract boolean expressions from Python code."""
        exprs: List[BoolExpr] = []

        try:
            tree = ast.parse(code)
        except SyntaxError:
            # Can't parse — return what we get from regex
            return self._fallback_extract(code)

        for node in ast.walk(tree):
            extracted = self._visit(node)
            if extracted:
                exprs.extend(extracted)

        return exprs

    def _visit(self, node: ast.AST) -> List[BoolExpr]:
        results: List[BoolExpr] = []

        if isinstance(node, ast.Assert):
            expr = self._convert_expr(node.test)
            if expr:
                results.append(expr)

        elif isinstance(node, ast.If):
            # Condition must be decidable
            cond = self._convert_expr(node.test)
            if cond:
                results.append(cond)

            # If there's an else, model mutual exclusion
            if node.orelse:
                if cond:
                    # Branch taken XOR not taken
                    neg_cond = BoolExpr.neg(cond)
                    results.append(BoolExpr.or_(cond, neg_cond))

        elif isinstance(node, ast.Compare):
            expr = self._convert_compare(node)
            if expr:
                results.append(expr)

        elif isinstance(node, ast.Assign):
            # x = expr → x_valid ↔ expr_valid
            if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                name = node.targets[0].id
                results.append(BoolExpr.var(f"{name}_defined"))

        elif isinstance(node, ast.Return):
            results.append(BoolExpr.var("__return_reached__"))
            if node.value:
                ret_expr = self._convert_expr(node.value)
                if ret_expr:
                    results.append(BoolExpr.implies(
                        BoolExpr.var("__return_reached__"),
                        ret_expr,
                    ))

        elif isinstance(node, ast.FunctionDef):
            results.append(BoolExpr.var(f"fn_{node.name}_defined"))
            # Arguments → all must be provided
            for arg in node.args.args:
                results.append(BoolExpr.implies(
                    BoolExpr.var(f"fn_{node.name}_called"),
                    BoolExpr.var(f"arg_{arg.arg}_provided"),
                ))

        return results

    def _convert_expr(self, node: ast.expr) -> Optional[BoolExpr]:
        """Convert a Python AST expression to BoolExpr."""
        if isinstance(node, ast.Name):
            return BoolExpr.var(node.id)

        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            child = self._convert_expr(node.operand)
            return BoolExpr.neg(child) if child else None

        elif isinstance(node, ast.BoolOp):
            children = [self._convert_expr(v) for v in node.values]
            children = [c for c in children if c is not None]
            if not children:
                return None
            if isinstance(node.op, ast.And):
                return BoolExpr.and_(*children)
            elif isinstance(node.op, ast.Or):
                return BoolExpr.or_(*children)

        elif isinstance(node, ast.Compare):
            return self._convert_compare(node)

        elif isinstance(node, ast.NameConstant):
            if node.value is True:
                return BoolExpr.var("__true__")
            elif node.value is False:
                return BoolExpr.neg(BoolExpr.var("__true__"))

        elif isinstance(node, ast.Constant):
            if node.value is True:
                return BoolExpr.var("__true__")
            elif node.value is False:
                return BoolExpr.neg(BoolExpr.var("__true__"))

        return None

    def _convert_compare(self, node: ast.Compare) -> Optional[BoolExpr]:
        """Convert a comparison to BoolExpr."""
        if not node.comparators:
            return None

        left = self._expr_name(node.left)
        results = []

        for op, comp in zip(node.ops, node.comparators):
            right = self._expr_name(comp)
            if isinstance(op, ast.Eq):
                results.append(BoolExpr.iff(
                    BoolExpr.var(left), BoolExpr.var(right)
                ))
            elif isinstance(op, ast.NotEq):
                results.append(BoolExpr.xor(
                    BoolExpr.var(left), BoolExpr.var(right)
                ))
            elif isinstance(op, (ast.Lt, ast.LtE)):
                results.append(BoolExpr.var(f"{left}_leq_{right}"))
            elif isinstance(op, (ast.Gt, ast.GtE)):
                results.append(BoolExpr.var(f"{left}_geq_{right}"))
            elif isinstance(op, ast.Is):
                results.append(BoolExpr.iff(
                    BoolExpr.var(left), BoolExpr.var(right)
                ))
            elif isinstance(op, ast.IsNot):
                results.append(BoolExpr.xor(
                    BoolExpr.var(left), BoolExpr.var(right)
                ))
            elif isinstance(op, ast.In):
                results.append(BoolExpr.var(f"{left}_in_{right}"))
            elif isinstance(op, ast.NotIn):
                results.append(BoolExpr.neg(BoolExpr.var(f"{left}_in_{right}")))

        if len(results) == 1:
            return results[0]
        elif results:
            return BoolExpr.and_(*results)
        return None

    @staticmethod
    def _expr_name(node: ast.expr) -> str:
        """Get a string name for an expression."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Constant):
            return f"const_{node.value}"
        elif isinstance(node, ast.Attribute):
            return f"{CodeToBoolExpr._expr_name(node.value)}.{node.attr}"
        elif isinstance(node, ast.Call):
            fn = CodeToBoolExpr._expr_name(node.func)
            return f"call_{fn}"
        return f"expr_{id(node)}"

    def _fallback_extract(self, code: str) -> List[BoolExpr]:
        """Regex fallback when AST parsing fails."""
        exprs: List[BoolExpr] = []
        for m in re.finditer(r"assert\s+(.+?)(?:\s*,|\s*$|\s*#)", code, re.MULTILINE):
            text = m.group(1).strip()
            exprs.append(BoolExpr.var(PropositionMiner._normalize(text)))
        return exprs


# ── Chain-of-Thought → Boolean ───────────────────────────────────────────────

class ChainOfThoughtEncoder:
    """
    Encode chain-of-thought reasoning as boolean constraints.

    A valid chain of thought has:
    1. Each step follows from previous steps (entailment)
    2. No step contradicts a previous step (consistency)
    3. The final step matches the stated answer (completeness)

    Encoding:
    - step_i_valid: step i is logically valid
    - step_i_follows_j: step i follows from step j
    - answer_matches: final answer matches conclusion

    Constraints:
    - For each step i > 0: step_i_valid → ∃j<i: step_i_follows_j
    - For each pair (i,j): ¬(step_i_contradicts_j)
    - answer_matches (must be true)
    """

    STEP_MARKERS = re.compile(
        r"(?:step\s*\d+|first|second|third|fourth|fifth|next|then|"
        r"finally|therefore|hence|thus|so|we get|this gives|"
        r"which means|it follows|consequently)\b[:\.]?\s*",
        re.IGNORECASE,
    )

    ANSWER_MARKERS = re.compile(
        r"(?:the answer is|answer:|result:|therefore|thus|hence|"
        r"= |equals |we conclude|final answer|solution:)\s*(.+?)(?:\.|$)",
        re.IGNORECASE,
    )

    def encode(self, text: str) -> List[BoolExpr]:
        """Extract chain-of-thought constraints."""
        steps = self._split_steps(text)
        if len(steps) <= 1:
            return []  # No chain to verify

        exprs: List[BoolExpr] = []

        # Each step must be valid
        step_vars = [BoolExpr.var(f"step_{i}_valid") for i in range(len(steps))]
        for sv in step_vars:
            exprs.append(sv)

        # Each step (after first) must follow from some previous step
        for i in range(1, len(steps)):
            follows_vars = [
                BoolExpr.var(f"step_{i}_follows_{j}")
                for j in range(i)
            ]
            # At least one "follows" must be true
            # step_i_valid → (follows_0 ∨ follows_1 ∨ ...)
            exprs.append(BoolExpr.implies(
                step_vars[i],
                BoolExpr.or_(*follows_vars) if len(follows_vars) > 1 else follows_vars[0],
            ))

        # No contradictions between steps
        for i in range(len(steps)):
            for j in range(i + 1, len(steps)):
                # ¬(step_i contradicts step_j) encoded as:
                # it can't be that both are valid AND they contradict
                contra = BoolExpr.var(f"step_{i}_contradicts_{j}")
                exprs.append(BoolExpr.neg(
                    BoolExpr.and_(step_vars[i], step_vars[j], contra)
                ))

        # Answer must match final step
        m = self.ANSWER_MARKERS.search(text)
        if m:
            exprs.append(BoolExpr.implies(
                step_vars[-1],
                BoolExpr.var("answer_consistent"),
            ))
            exprs.append(BoolExpr.var("answer_consistent"))

        return exprs

    def _split_steps(self, text: str) -> List[str]:
        """Split text into reasoning steps."""
        # Try explicit step markers
        parts = self.STEP_MARKERS.split(text)
        steps = [p.strip() for p in parts if p.strip() and len(p.strip()) > 5]

        if len(steps) > 1:
            return steps

        # Fall back to sentence splitting
        sentences = [s.strip() for s in re.split(r'[.;]\s+', text) if s.strip()]
        return sentences


# ── Master Translation Pipeline ──────────────────────────────────────────────

class TextTo3SAT:
    """
    The master translator. Converts any text into 3-SAT clauses.

    Usage:
        translator = TextTo3SAT()

        # Automatic domain detection
        n_vars, clauses = translator.translate(
            "if x > 0 and y > 0 then x + y > 0"
        )

        # Explicit domain
        n_vars, clauses = translator.translate(code_text, domain="code")

        # Get grouped constraints (for sat_score)
        n_vars, groups = translator.translate_grouped(text)

    The output format matches what sat.py and verify.py expect:
        n_vars: int — number of propositional variables
        clauses: List[List[int]] — 3-SAT clauses (signed ints, 1-indexed)
    """

    def __init__(self):
        self.miner = PropositionMiner()
        self.tseitin = TseitinEncoder()
        # Lazy import to avoid circular dependency (code_to_3sat imports from here).
        # StructuralCodeTo3SAT is a drop-in replacement for CodeToBoolExpr:
        # block-depth aware, entity-extracting, terminal-agnostic, TL+PPL backed.
        try:
            from .code_to_3sat import StructuralCodeTo3SAT
            self.code_parser = StructuralCodeTo3SAT()
        except ImportError:
            self.code_parser = CodeToBoolExpr()
        self.cot_encoder = ChainOfThoughtEncoder()
        self.arith_encoder = ArithmeticEncoder()

    def translate(
        self,
        text: str,
        domain: Optional[str] = None,
    ) -> Tuple[int, List[List[int]]]:
        """
        Translate text to 3-SAT.

        Returns (n_vars, clauses) where clauses are in 3-CNF.
        Every clause has at most 3 literals.
        """
        if domain is None:
            domain = self._detect_domain(text)

        exprs = self._extract_expressions(text, domain)

        if not exprs:
            return 0, []

        # Conjoin all expressions and Tseitin-encode
        if len(exprs) == 1:
            root = exprs[0]
        else:
            root = BoolExpr.and_(*exprs)

        self.tseitin = TseitinEncoder()  # Reset state
        n_vars, clauses = self.tseitin.encode(root)

        # Verify all clauses are ≤ 3 literals (should be guaranteed by Tseitin)
        assert all(len(c) <= 3 for c in clauses), \
            f"Tseitin produced clause with > 3 literals"

        return n_vars, clauses

    def translate_grouped(
        self,
        text: str,
        domain: Optional[str] = None,
    ) -> Tuple[int, List[List[List[int]]]]:
        """
        Translate text to grouped 3-SAT constraints.

        Each expression becomes its own group. This format is used
        by sat_score() to compute per-group satisfiability.

        Returns (n_vars, groups) where each group is a list of 3-SAT clauses.
        """
        if domain is None:
            domain = self._detect_domain(text)

        exprs = self._extract_expressions(text, domain)

        if not exprs:
            return 0, []

        max_vars = 0
        groups: List[List[List[int]]] = []

        for expr in exprs:
            encoder = TseitinEncoder()
            n_v, clauses = encoder.encode(expr)
            if clauses:
                groups.append(clauses)
                max_vars = max(max_vars, n_v)

        return max_vars, groups

    def _extract_expressions(self, text: str, domain: str) -> List[BoolExpr]:
        """Extract boolean expressions based on domain."""
        exprs: List[BoolExpr] = []

        if domain == "code":
            # Use extract_exprs() — works for both CodeToBoolExpr (legacy)
            # and StructuralCodeTo3SAT (block-depth, entity-aware, TL+PPL).
            if hasattr(self.code_parser, "extract_exprs"):
                exprs.extend(self.code_parser.extract_exprs(text))
            else:
                exprs.extend(self.code_parser.extract(text))
            # Also mine comments for constraints
            comments = re.findall(r"#\s*(.+)$", text, re.MULTILINE)
            for comment in comments:
                mined = self.miner.mine(comment)
                exprs.extend(mined)

        elif domain == "math":
            # Mine propositions
            exprs.extend(self.miner.mine(text))

            # Look for arithmetic constraints
            for m in re.finditer(r"(\w+)\s*=\s*(\w+)", text):
                exprs.extend(
                    self.arith_encoder.encode_equality(m.group(1), m.group(2))
                )

            # Chain-of-thought in math solutions
            cot = self.cot_encoder.encode(text)
            exprs.extend(cot)

        elif domain == "proof":
            exprs.extend(self.miner.mine(text))
            cot = self.cot_encoder.encode(text)
            exprs.extend(cot)

        elif domain == "reasoning":
            exprs.extend(self.miner.mine(text))
            cot = self.cot_encoder.encode(text)
            exprs.extend(cot)

        elif domain == "market":
            # Ed Thorp domain: market constraints
            exprs.extend(self.miner.mine_market(text))
            # Arithmetic constraints on numerical values
            for m in re.finditer(r"(\w+)\s*=\s*(\w+)", text):
                exprs.extend(
                    self.arith_encoder.encode_equality(m.group(1), m.group(2))
                )
            # Chain-of-thought in market reasoning
            cot = self.cot_encoder.encode(text)
            exprs.extend(cot)

        else:
            # Default: mine propositions from text
            exprs.extend(self.miner.mine(text))

        return exprs

    @staticmethod
    def _detect_domain(text: str) -> str:
        """Auto-detect the domain of the text."""
        # Code detection
        code_indicators = [
            r"\bdef\s+\w+\s*\(",
            r"\bclass\s+\w+",
            r"\bimport\s+\w+",
            r"\breturn\b",
            r"\bfor\s+\w+\s+in\b",
            r"^\s*assert\b",
            r"__\w+__",
        ]
        code_score = sum(1 for p in code_indicators if re.search(p, text, re.MULTILINE))
        if code_score >= 2:
            return "code"

        # Proof detection
        proof_indicators = [
            r"\b(?:theorem|lemma|proof|qed|∎|□|corollary)\b",
            r"\b(?:assume|suppose|given|let)\b.*\b(?:then|therefore)\b",
            r"\b(?:by|from|using)\s+(?:induction|contradiction|cases)\b",
            r"\bsorry\b",
            r"\b(?:exact|apply|intro|have)\b.*:=",
        ]
        proof_score = sum(1 for p in proof_indicators if re.search(p, text, re.IGNORECASE))
        if proof_score >= 1:
            return "proof"

        # Math detection
        math_indicators = [
            r"[=<>≤≥]\s*\d+",
            r"\b(?:solve|find|compute|calculate|evaluate)\b",
            r"[+\-*/^]\s*[a-z]",
            r"\b(?:equation|formula|expression)\b",
            r"∀|∃|∈|∉|⊂|⊃|∪|∩",
        ]
        math_score = sum(1 for p in math_indicators if re.search(p, text, re.IGNORECASE))
        if math_score >= 2:
            return "math"

        # Market detection
        market_indicators = [
            r"\b(?:price|close|open|high|low|bid|ask|last|volume)\b",
            r"\b(?:long|short|buy|sell|position|portfolio|allocation)\b",
            r"\b(?:stop[\s-]?loss|drawdown|sharpe|sortino|calmar)\b",
            r"\b(?:hedge|hedging|correlation|beta|alpha|volatility|var)\b",
            r"\b(?:P&L|pnl|profit|loss|return|yield|dividend)\b",
            r"\$[\d,.]+",
            r"\b(?:stock|bond|option|future|derivative|equity|forex|crypto)\b",
        ]
        market_score = sum(1 for p in market_indicators if re.search(p, text, re.IGNORECASE))
        if market_score >= 2:
            return "market"

        # Check for reasoning chain
        cot_indicators = [
            r"\bstep\s*\d+\b",
            r"\b(?:first|second|third|finally)\b.*\b(?:then|next|therefore)\b",
            r"\btherefore\b",
            r"\bthe answer is\b",
        ]
        cot_score = sum(1 for p in cot_indicators if re.search(p, text, re.IGNORECASE))
        if cot_score >= 1:
            return "reasoning"

        return "logic"  # default


# ── Convenience Functions ─────────────────────────────────────────────────────

_default_translator: Optional[TextTo3SAT] = None


def get_translator() -> TextTo3SAT:
    """Get or create the default translator."""
    global _default_translator
    if _default_translator is None:
        _default_translator = TextTo3SAT()
    return _default_translator


def text_to_3sat(
    text: str,
    domain: Optional[str] = None,
) -> Tuple[int, List[List[int]]]:
    """
    Translate text to 3-SAT clauses.

    >>> n_vars, clauses = text_to_3sat("if A then B. A is true.")
    >>> # clauses are all ≤ 3 literals
    >>> all(len(c) <= 3 for c in clauses)
    True
    """
    return get_translator().translate(text, domain=domain)


def text_to_3sat_grouped(
    text: str,
    domain: Optional[str] = None,
) -> Tuple[int, List[List[List[int]]]]:
    """
    Translate text to grouped 3-SAT constraints.

    Each logical statement becomes its own constraint group.
    Use with sat_score() for per-group verification.

    >>> n_vars, groups = text_to_3sat_grouped("A and B. if A then C.")
    """
    return get_translator().translate_grouped(text, domain=domain)


def tokens_to_3sat(
    token_ids: List[int],
    decode_fn: Any,
    domain: Optional[str] = None,
) -> Tuple[int, List[List[List[int]]]]:
    """
    Decode tokens to text, then translate to grouped 3-SAT.

    This is the constraint_fn you pass to SATReward and verified_generate.

    Usage:
        from functools import partial
        constraint_fn = partial(tokens_to_3sat, decode_fn=tokenizer.decode)
        result = model.verified_generate(prompt, constraint_fn=constraint_fn)
    """
    text = decode_fn(token_ids)
    return get_translator().translate_grouped(text, domain=domain)
