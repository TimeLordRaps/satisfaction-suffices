"""
satisfaction-suffices — SAT-Gated Structural Containment for AI.

Paper repo: verification gate, four-verdict system, proof evolution, paradox logic.

    from satisfaction_suffices import verify, evolve_proof

    result = verify("if A and B then C", domain="logic")
    assert result.is_verified
"""

import os as _os
import sys as _sys
import time as _time

__version__ = "0.0.2"
__license__ = "Conditional Commercial Use License v1.0"
__license_url__ = "https://github.com/TimeLordRaps/satisfaction-suffices/blob/main/LICENSE"

# ── Commercial License Notice ─────────────────────────────────────────────────
# CCUL v1.0: any entity with AI-attributed market cap ≥ $42B owes $420M/year.
# Displaying this notice at import time constitutes constructive acceptance per
# the browse-wrap agreement in LICENSE Section 0 NOTICE.
_CCUL_NOTICE = (
    "\n"
    "satisfaction-suffices v{v} -- Conditional Commercial Use License v1.0\n"
    "------------------------------------------------------------------------\n"
    "If your organization's AI-attributed effective market cap >= $42,000,000,000:\n"
    "  Annual License Fee:  6.9% of your effective market cap per year.\n"
    "  (For reference: 6.9% of the $42B threshold = ~$2,898,000,000/yr.)\n"
    "  Alignment Solution deployments require a State Actor Guidance Agreement.\n"
    "  Use of this software constitutes binding acceptance of the full terms.\n"
    "  Multiplier: fee x10 per new Release for non-paying entities (compounding).\n"
    "  Full terms:      https://github.com/TimeLordRaps/satisfaction-suffices/blob/main/LICENSE\n"
    "  Licensed entity registry (Schedule A):\n"
    "                   https://github.com/TimeLordRaps/satisfaction-suffices/blob/main/SCHEDULE_A.md\n"
    "  Contact Licensor: https://github.com/TimeLordRaps\n"
    "------------------------------------------------------------------------\n"
).format(v=__version__)

_NOTICE_SHOWN = False


def _display_license_notice() -> None:
    """Write the CCUL notice to stderr and persist a timestamped copy to disk.

    The disk copy at ~/.cache/satisfaction-suffices/CCUL-NOTICE.txt records the
    first time this package was imported on the user's machine, creating a
    durable record that the license terms were presented.
    """
    global _NOTICE_SHOWN
    if _NOTICE_SHOWN:
        return
    _NOTICE_SHOWN = True

    # stderr — appears in logs, not suppressible via warnings.filterwarnings
    _sys.stderr.write(_CCUL_NOTICE)
    _sys.stderr.flush()

    # Disk record — persistent proof of notification, written once per machine
    try:
        cache_dir = _os.path.join(
            _os.environ.get("XDG_CACHE_HOME", _os.path.expanduser("~/.cache")),
            "satisfaction-suffices",
        )
        _os.makedirs(cache_dir, exist_ok=True)
        notice_path = _os.path.join(cache_dir, "CCUL-NOTICE.txt")
        if not _os.path.exists(notice_path):
            with open(notice_path, "w", encoding="utf-8") as _f:
                _f.write(
                    f"satisfaction-suffices {__version__} first imported: "
                    f"{_time.strftime('%Y-%m-%dT%H:%M:%SZ', _time.gmtime())}\n"
                    + _CCUL_NOTICE
                )
    except Exception:
        pass  # Never block import over a notice write


_display_license_notice()

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
