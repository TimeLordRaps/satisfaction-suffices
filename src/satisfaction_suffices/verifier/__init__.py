"""
verifier — SAT solver + verification gate.
"""

from .sat import (
    CDCLSolver,
    SATReward,
    SATSolver,
    sat_score,
    solve_cnf,
    neg,
    neg_lit,
    pos_lit,
    sign_of,
    var_of,
)
from .verify import (
    ConstraintExtractor,
    CodeConstraintExtractor,
    LogicConstraintExtractor,
    MathConstraintExtractor,
    ProofConstraintExtractor,
    Verdict,
    VerificationError,
    VerificationGate,
    VerificationResult,
    get_gate,
    must_verify,
    verify,
)
from .text_to_3sat import (
    BoolExpr,
    BoolOp,
    TextTo3SAT,
    TseitinEncoder,
    text_to_3sat,
    text_to_3sat_grouped,
    tokens_to_3sat,
)
from .partial import (
    ClauseStatus,
    PartialConstraintEvaluator,
    PrefixFeasibilityResult,
    evaluate_partial,
)

__all__ = [
    "CDCLSolver", "SATSolver", "SATReward", "sat_score", "solve_cnf",
    "neg", "neg_lit", "pos_lit", "sign_of", "var_of",
    "ConstraintExtractor", "CodeConstraintExtractor",
    "LogicConstraintExtractor", "MathConstraintExtractor",
    "ProofConstraintExtractor",
    "Verdict", "VerificationError", "VerificationGate", "VerificationResult",
    "get_gate", "must_verify", "verify",
    "BoolExpr", "BoolOp", "TextTo3SAT", "TseitinEncoder",
    "text_to_3sat", "text_to_3sat_grouped", "tokens_to_3sat",
    "ClauseStatus", "PartialConstraintEvaluator",
    "PrefixFeasibilityResult", "evaluate_partial",
]
