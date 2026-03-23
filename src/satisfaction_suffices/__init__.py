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
__license__ = "The Time License v7.77"
__license_url__ = "https://github.com/TimeLordRaps/satisfaction-suffices/blob/main/LICENSE"

# ── Commercial License Notice ─────────────────────────────────────────────────
# The Time License v7.77: Top Entities (market cap >= $1B) owe tiered Annual License Fee.
# Displaying this notice at import time constitutes constructive acceptance per
# the browse-wrap agreement in LICENSE Section 0 NOTICE.
_LICENSE_NOTICE = (
    "\n"
    "satisfaction-suffices v{v} -- The Time License v7.77\n"
    "------------------------------------------------------------------------\n"
    "If your organization's Effective Market Capitalization >= $1,000,000,000:\n"
    "  Tiered Annual License Fee applies (Tier 1: $34.5M/yr — Tier 6: $24.15B/yr).\n"
    "  Pro bono litigation incentives and counsel-defection safeguards apply (§8A-8B).\n"
    ""
    "  Use of this software constitutes binding acceptance of the full terms.\n"
    ""
    "  Full terms:      https://github.com/TimeLordRaps/satisfaction-suffices/blob/main/LICENSE\n"
    "  Licensed entity registry (Schedule A):\n"
    "                   https://github.com/TimeLordRaps/satisfaction-suffices/blob/main/SCHEDULE_A.md\n"
    "  Contact Licensor: https://github.com/TimeLordRaps\n"
    "------------------------------------------------------------------------\n"
).format(v=__version__)

_NOTICE_SHOWN = False


def _display_license_notice() -> None:
    """Write the license notice to stderr and persist a timestamped copy to disk.

    The disk copy at ~/.cache/satisfaction-suffices/LICENSE-NOTICE.txt records the
    first time this package was imported on the user's machine, creating a
    durable record that the license terms were presented.
    """
    global _NOTICE_SHOWN
    if _NOTICE_SHOWN:
        return
    _NOTICE_SHOWN = True

    # stderr — appears in logs, not suppressible via warnings.filterwarnings
    _sys.stderr.write(_LICENSE_NOTICE)
    _sys.stderr.flush()

    # Disk record — persistent proof of notification, written once per machine
    try:
        cache_dir = _os.path.join(
            _os.environ.get("XDG_CACHE_HOME", _os.path.expanduser("~/.cache")),
            "satisfaction-suffices",
        )
        _os.makedirs(cache_dir, exist_ok=True)
        notice_path = _os.path.join(cache_dir, "LICENSE-NOTICE.txt")
        if not _os.path.exists(notice_path):
            with open(notice_path, "w", encoding="utf-8") as _f:
                _f.write(
                    f"satisfaction-suffices {__version__} first imported: "
                    f"{_time.strftime('%Y-%m-%dT%H:%M:%SZ', _time.gmtime())}\n"
                    + _LICENSE_NOTICE
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
from .bridge import (
    BRIDGE_SOURCES,
    DEFAULT_EXPERTS,
    IKM_RP_SOURCE,
    IKM_SOURCE,
    BridgeExample,
    BridgeSource,
    DiagonalPackPlan,
    ExpertPackPlan,
    assign_bridge_expert,
    build_bridge_examples,
    build_diagonal_pack_plan,
    bucket_bridge_examples,
    format_bridge_markdown,
    load_jsonl,
    parse_bridge_record,
    write_bridge_outputs,
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
    # Bridge stage
    "BRIDGE_SOURCES", "DEFAULT_EXPERTS",
    "IKM_RP_SOURCE", "IKM_SOURCE",
    "BridgeExample", "BridgeSource",
    "DiagonalPackPlan", "ExpertPackPlan",
    "assign_bridge_expert", "build_bridge_examples",
    "build_diagonal_pack_plan", "bucket_bridge_examples",
    "format_bridge_markdown", "load_jsonl",
    "parse_bridge_record", "write_bridge_outputs",
]
