from __future__ import annotations

from satisfaction_suffices.benchmarks import (
    run_phase_transition_benchmark,
    run_phase_transition_budget_sweep,
    run_relevance_benchmarks,
)
from satisfaction_suffices.verifier import evaluate_partial, verify


def test_math_quantifier_case_no_longer_crashes() -> None:
    result = verify("x = y. for all z. exists w", domain="math")
    assert result.is_verified


def test_partial_evaluator_uses_live_translator_api() -> None:
    result = evaluate_partial("A. not A.")
    assert result.prunable
    assert result.contradiction is True


def test_relevance_benchmarks_smoke_profile_passes_curated_cases() -> None:
    report = run_relevance_benchmarks(profile="smoke")
    task = report["task_benchmarks"]
    assert task["passed"] == task["total"]
    assert report["phase_transition"]["peak_timeout_ratio"] is not None


def test_phase_transition_probe_tracks_instance_counts() -> None:
    phase = run_phase_transition_benchmark(
        n_vars=24,
        n_instances=8,
        budget=80,
        ratios=(3.2, 4.2),
        seed=7,
    )
    assert len(phase["ratios"]) == 2
    for row in phase["ratios"]:
        assert row["sat"] + row["unsat"] + row["timeout"] == 8


def test_phase_transition_budget_sweep_tracks_each_budget() -> None:
    sweep = run_phase_transition_budget_sweep(
        n_vars=18,
        n_instances=4,
        budgets=(40, 80),
        ratios=(4.0, 4.4),
        seed=5,
    )
    assert sweep["budgets"] == [40, 80]
    assert len(sweep["runs"]) == 2
    for run in sweep["runs"]:
        assert len(run["ratios"]) == 2
        for row in run["ratios"]:
            assert row["sat"] + row["unsat"] + row["timeout"] == 4