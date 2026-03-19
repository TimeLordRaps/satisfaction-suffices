"""
logic — Reasoning, proof evolution, and paradox analysis.
"""

from .proof_evo import (
    EvolutionResult,
    MutationOp,
    ProofEvolver,
    ProofNode,
    ProofStatus,
    evolve_proof,
    extract_unsat_core,
)
from .ppl import (
    AttractorState,
    Contradiction,
    ContradictionDetector,
    ContradictionLevel,
    ParadoxAnalysis,
    ParadoxScorer,
    analyze_paradox,
    detect_contradictions,
    pigeonhole_cnf,
    test_paradox_hardness,
)
from .constraint import (
    Constraint,
    ConstraintAlgebra,
    ConjunctiveConstraint,
    DisjunctiveConstraint,
    FunctionConstraint,
    NegatedConstraint,
    PartialResult,
    PrefixFeasibility,
    SATConstraint,
    SequentialConstraint,
    algebra,
    CLAUSE_RATIO_THRESHOLD,
)

__all__ = [
    "EvolutionResult", "MutationOp", "ProofEvolver", "ProofNode", "ProofStatus",
    "evolve_proof", "extract_unsat_core",
    "AttractorState", "Contradiction", "ContradictionDetector",
    "ContradictionLevel", "ParadoxAnalysis", "ParadoxScorer",
    "analyze_paradox", "detect_contradictions", "pigeonhole_cnf",
    "test_paradox_hardness",
    "Constraint", "ConstraintAlgebra", "ConjunctiveConstraint",
    "DisjunctiveConstraint", "FunctionConstraint", "NegatedConstraint",
    "PartialResult", "PrefixFeasibility", "SATConstraint",
    "SequentialConstraint", "algebra", "CLAUSE_RATIO_THRESHOLD",
]
