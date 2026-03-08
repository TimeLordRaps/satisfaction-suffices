"""
satisfaction-suffices — SAT-Gated Structural Containment for AI.

Paper repo: verification gate, four-verdict system, proof evolution, paradox logic.

    from satisfaction_suffices import verify, evolve_proof

    result = verify("if A and B then C", domain="logic")
    assert result.is_verified
"""

from .verifier import (
    BoolExpr,
    BoolOp,
    CDCLSolver,
    ClauseStatus,
    CodeConstraintExtractor,
    ConstraintExtractor,
    LogicConstraintExtractor,
    MathConstraintExtractor,
    PartialConstraintEvaluator,
    PrefixFeasibilityResult,
    ProofConstraintExtractor,
    SATReward,
    TextTo3SAT,
    TseitinEncoder,
    VerificationError,
    VerificationGate,
    VerificationResult,
    Verdict,
    evaluate_partial,
    get_gate,
    must_verify,
    sat_score,
    solve_cnf,
    text_to_3sat,
    text_to_3sat_grouped,
    tokens_to_3sat,
    verify,
)
from .logic import (
    evolve_proof,
    extract_unsat_core,
    analyze_paradox,
    detect_contradictions,
    pigeonhole_cnf,
    EvolutionResult,
    MutationOp,
    ProofEvolver,
    ProofNode,
    ProofStatus,
    ContradictionLevel,
    ParadoxAnalysis,
    ParadoxScorer,
    Constraint,
    ConstraintAlgebra,
    SATConstraint,
    algebra,
)

__version__ = "0.1.0"

__all__ = [
    # Verifier
    "BoolExpr", "BoolOp", "CDCLSolver", "ClauseStatus",
    "CodeConstraintExtractor", "ConstraintExtractor",
    "LogicConstraintExtractor", "MathConstraintExtractor",
    "PartialConstraintEvaluator", "PrefixFeasibilityResult",
    "ProofConstraintExtractor", "SATReward", "TextTo3SAT", "TseitinEncoder",
    "VerificationError", "VerificationGate", "VerificationResult", "Verdict",
    "evaluate_partial", "get_gate", "must_verify",
    "sat_score", "solve_cnf",
    "text_to_3sat", "text_to_3sat_grouped", "tokens_to_3sat", "verify",
    # Logic
    "evolve_proof", "extract_unsat_core",
    "analyze_paradox", "detect_contradictions", "pigeonhole_cnf",
    "EvolutionResult", "MutationOp", "ProofEvolver", "ProofNode", "ProofStatus",
    "ContradictionLevel", "ParadoxAnalysis", "ParadoxScorer",
    "Constraint", "ConstraintAlgebra", "SATConstraint", "algebra",
]
