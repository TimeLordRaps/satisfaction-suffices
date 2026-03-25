from __future__ import annotations

import random
from dataclasses import asdict, dataclass
from typing import Any, Dict, Iterable, List, Literal, Mapping

from .verifier import evaluate_partial, verify
from .verifier.sat import SATSolver, neg_lit, pos_lit


VerdictName = Literal["VERIFIED", "CONTRADICTION", "PARADOX", "TIMEOUT"]
PartialState = Literal["extendable", "prunable", "unresolved"]


@dataclass(frozen=True)
class VerdictBenchmarkCase:
    name: str
    domain: str
    content: str
    expected_verdict: VerdictName
    description: str


@dataclass(frozen=True)
class PartialBenchmarkCase:
    name: str
    content: str
    expected_state: PartialState
    description: str
    domain: str = "auto"


@dataclass(frozen=True)
class PhaseTransitionProfile:
    n_vars: int
    n_instances: int
    budget: int
    ratios: tuple[float, ...]
    seed: int = 42


VERDICT_BENCHMARKS: Mapping[str, tuple[VerdictBenchmarkCase, ...]] = {
    "logic": (
        VerdictBenchmarkCase(
            name="implication_keeps_gate_open",
            domain="logic",
            content="if A then B. A.",
            expected_verdict="VERIFIED",
            description="basic implication chain remains satisfiable",
        ),
        VerdictBenchmarkCase(
            name="direct_negation_forms_paradox",
            domain="logic",
            content="A. not A.",
            expected_verdict="PARADOX",
            description="single claim and negation are jointly inconsistent",
        ),
        VerdictBenchmarkCase(
            name="implication_conflict_forms_paradox",
            domain="logic",
            content="if A then B. A. not B.",
            expected_verdict="PARADOX",
            description="implication plus opposite conclusion stays blocked",
        ),
    ),
    "code": (
        VerdictBenchmarkCase(
            name="consistent_branching_code_verifies",
            domain="code",
            content="assert ready\nif cond:\n    pass\nelif other:\n    pass\nx == y",
            expected_verdict="VERIFIED",
            description="assertions, branch exclusivity, and equality remain consistent",
        ),
        VerdictBenchmarkCase(
            name="opposing_asserts_form_paradox",
            domain="code",
            content="assert ready\nassert not ready",
            expected_verdict="PARADOX",
            description="opposed asserts should not pass the code gate",
        ),
        VerdictBenchmarkCase(
            name="equality_inequality_conflict_forms_paradox",
            domain="code",
            content="x == y\nx != y",
            expected_verdict="PARADOX",
            description="opposed relation constraints stay blocked",
        ),
    ),
    "math": (
        VerdictBenchmarkCase(
            name="quantified_equality_verifies",
            domain="math",
            content="x = y. for all z. exists w",
            expected_verdict="VERIFIED",
            description="mixed equality and quantifier extraction returns a coherent verdict",
        ),
        VerdictBenchmarkCase(
            name="chained_equalities_verify",
            domain="math",
            content="x = y. x = z.",
            expected_verdict="VERIFIED",
            description="simple equalities remain satisfiable",
        ),
    ),
    "proof": (
        VerdictBenchmarkCase(
            name="assumption_to_conclusion_verifies",
            domain="proof",
            content="assume A. therefore A.",
            expected_verdict="VERIFIED",
            description="basic proof step stays coherent",
        ),
        VerdictBenchmarkCase(
            name="explicit_contradiction_forms_paradox",
            domain="proof",
            content="assume A. contradiction.",
            expected_verdict="PARADOX",
            description="explicit contradiction triggers the unresolved/paradox bucket",
        ),
    ),
}


PARTIAL_BENCHMARKS: tuple[PartialBenchmarkCase, ...] = (
    PartialBenchmarkCase(
        name="atomic_prefix_extendable",
        content="A",
        expected_state="extendable",
        description="simple atomic prefix is still extendable",
    ),
    PartialBenchmarkCase(
        name="contradictory_prefix_prunable",
        content="A. not A.",
        expected_state="prunable",
        description="direct contradiction should be safely pruned",
    ),
)


PHASE_TRANSITION_PROFILES: Mapping[str, PhaseTransitionProfile] = {
    "smoke": PhaseTransitionProfile(
        n_vars=24,
        n_instances=8,
        budget=80,
        ratios=(3.2, 4.2, 4.4, 5.0),
    ),
    "full": PhaseTransitionProfile(
        n_vars=100,
        n_instances=200,
        budget=500,
        ratios=(3.0, 3.4, 3.8, 4.0, 4.2, 4.267, 4.4, 4.8, 5.2),
    ),
}


def _partial_state_for_result(result: Any) -> PartialState:
    if result.prunable:
        return "prunable"
    if result.extendable:
        return "extendable"
    return "unresolved"


def _suite_accuracy(passed: int, total: int) -> float:
    if total == 0:
        return 1.0
    return passed / total


def run_verdict_benchmarks() -> Dict[str, Any]:
    suites: Dict[str, Any] = {}
    total_cases = 0
    total_passed = 0

    for suite_name, cases in VERDICT_BENCHMARKS.items():
        case_results: List[Dict[str, Any]] = []
        passed = 0

        for case in cases:
            result = verify(case.content, domain=case.domain)
            predicted = result.verdict.name
            ok = predicted == case.expected_verdict
            passed += int(ok)
            total_cases += 1
            total_passed += int(ok)
            case_results.append(
                {
                    **asdict(case),
                    "predicted_verdict": predicted,
                    "passed": ok,
                    "zone": result.zone,
                    "sat_ratio": result.sat_ratio,
                    "n_constraints": result.n_constraints,
                    "n_timeout": result.n_timeout,
                    "n_paradox": result.n_paradox,
                }
            )

        suites[suite_name] = {
            "passed": passed,
            "total": len(cases),
            "accuracy": _suite_accuracy(passed, len(cases)),
            "cases": case_results,
        }

    return {
        "passed": total_passed,
        "total": total_cases,
        "accuracy": _suite_accuracy(total_passed, total_cases),
        "suites": suites,
    }


def run_partial_benchmarks() -> Dict[str, Any]:
    case_results: List[Dict[str, Any]] = []
    passed = 0

    for case in PARTIAL_BENCHMARKS:
        result = evaluate_partial(case.content, domain=case.domain)
        predicted = _partial_state_for_result(result)
        ok = predicted == case.expected_state
        passed += int(ok)
        case_results.append(
            {
                **asdict(case),
                "predicted_state": predicted,
                "passed": ok,
                "sat_ratio": result.sat_ratio,
                "n_dead": result.n_dead,
                "n_satisfied": result.n_satisfied,
                "n_free": result.n_free,
                "n_unit": result.n_unit,
                "contradiction": result.contradiction,
            }
        )

    total = len(PARTIAL_BENCHMARKS)
    return {
        "passed": passed,
        "total": total,
        "accuracy": _suite_accuracy(passed, total),
        "cases": case_results,
    }


def generate_random_3cnf(
    n_vars: int,
    n_clauses: int,
    rng: random.Random,
) -> List[List[int]]:
    clauses: List[List[int]] = []
    for _ in range(n_clauses):
        vars_chosen = rng.sample(range(n_vars), 3)
        clause = [pos_lit(v) if rng.random() < 0.5 else neg_lit(v) for v in vars_chosen]
        clauses.append(clause)
    return clauses


def run_phase_transition_benchmark(
    *,
    n_vars: int,
    n_instances: int,
    budget: int,
    ratios: Iterable[float],
    seed: int = 42,
) -> Dict[str, Any]:
    rng = random.Random(seed)
    ratio_rows: List[Dict[str, Any]] = []

    for ratio in ratios:
        n_clauses = int(round(ratio * n_vars))
        counts = {"SAT": 0, "UNSAT": 0, "TIMEOUT": 0}

        for _ in range(n_instances):
            solver = SATSolver()
            solver.new_vars(n_vars)
            ok = True

            for clause in generate_random_3cnf(n_vars, n_clauses, rng):
                if not solver.add_clause(list(clause)):
                    ok = False
                    break

            if not ok:
                counts["UNSAT"] += 1
                continue

            solved = solver.solve(budget=budget)
            if solved:
                counts["SAT"] += 1
            elif solver.conflicts >= budget > 0:
                counts["TIMEOUT"] += 1
            else:
                counts["UNSAT"] += 1

        timeout_density = counts["TIMEOUT"] / n_instances if n_instances else 0.0
        ratio_rows.append(
            {
                "ratio": ratio,
                "n_clauses": n_clauses,
                "sat": counts["SAT"],
                "unsat": counts["UNSAT"],
                "timeout": counts["TIMEOUT"],
                "timeout_density": timeout_density,
            }
        )

    peak = max(ratio_rows, key=lambda row: row["timeout_density"], default=None)
    return {
        "n_vars": n_vars,
        "n_instances": n_instances,
        "budget": budget,
        "ratios": ratio_rows,
        "peak_timeout_ratio": None if peak is None else peak["ratio"],
        "peak_timeout_density": None if peak is None else peak["timeout_density"],
    }


def run_phase_transition_budget_sweep(
    *,
    n_vars: int,
    n_instances: int,
    budgets: Iterable[int],
    ratios: Iterable[float],
    seed: int = 42,
) -> Dict[str, Any]:
    budget_runs: List[Dict[str, Any]] = []

    for budget in budgets:
        phase = run_phase_transition_benchmark(
            n_vars=n_vars,
            n_instances=n_instances,
            budget=budget,
            ratios=ratios,
            seed=seed,
        )
        total_timeouts = sum(row["timeout"] for row in phase["ratios"])
        mean_timeout_density = (
            sum(row["timeout_density"] for row in phase["ratios"]) / len(phase["ratios"])
            if phase["ratios"]
            else 0.0
        )
        budget_runs.append(
            {
                **phase,
                "budget": budget,
                "total_timeouts": total_timeouts,
                "mean_timeout_density": mean_timeout_density,
            }
        )

    strongest_peak = max(
        budget_runs,
        key=lambda run: (run["peak_timeout_density"] or 0.0, run["total_timeouts"]),
        default=None,
    )
    return {
        "n_vars": n_vars,
        "n_instances": n_instances,
        "budgets": [run["budget"] for run in budget_runs],
        "runs": budget_runs,
        "strongest_peak_budget": None if strongest_peak is None else strongest_peak["budget"],
        "strongest_peak_ratio": None if strongest_peak is None else strongest_peak["peak_timeout_ratio"],
        "strongest_peak_density": None if strongest_peak is None else strongest_peak["peak_timeout_density"],
    }


def run_relevance_benchmarks(profile: str = "smoke") -> Dict[str, Any]:
    if profile not in PHASE_TRANSITION_PROFILES:
        available = ", ".join(sorted(PHASE_TRANSITION_PROFILES))
        raise ValueError(f"Unknown benchmark profile '{profile}'. Available: {available}")

    phase_profile = PHASE_TRANSITION_PROFILES[profile]
    verdict = run_verdict_benchmarks()
    partial = run_partial_benchmarks()
    phase = run_phase_transition_benchmark(
        n_vars=phase_profile.n_vars,
        n_instances=phase_profile.n_instances,
        budget=phase_profile.budget,
        ratios=phase_profile.ratios,
        seed=phase_profile.seed,
    )

    combined_passed = verdict["passed"] + partial["passed"]
    combined_total = verdict["total"] + partial["total"]
    return {
        "profile": profile,
        "task_benchmarks": {
            "passed": combined_passed,
            "total": combined_total,
            "accuracy": _suite_accuracy(combined_passed, combined_total),
            "verdict": verdict,
            "partial": partial,
        },
        "phase_transition": phase,
        "notes": [
            "Task benchmarks are local proxy suites for the current verifier surface, not external LM leaderboard scores.",
            "Phase-transition results are synthetic SAT stress tests aligned with the repo's stated emergence/timeout hypothesis.",
        ],
    }