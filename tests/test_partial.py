from __future__ import annotations

from satisfaction_suffices.verifier.partial import PartialConstraintEvaluator, PrefixFeasibilityResult, evaluate_partial


def test_partial_evaluator_constructs_and_runs() -> None:
    evaluator = PartialConstraintEvaluator(domain="logic")
    result = evaluator.evaluate("if A then B. A.")
    assert isinstance(result, PrefixFeasibilityResult)
    assert result.sat_ratio >= 0.0
    assert result.prefix_len == len("if A then B. A.")


def test_evaluate_partial_smoke() -> None:
    result = evaluate_partial("A.")
    assert result.extendable or result.unresolved or result.prunable


def test_partial_detects_contradiction_with_monkeypatched_translator() -> None:
    evaluator = PartialConstraintEvaluator()
    evaluator._translator.translate = lambda prefix, domain=None: (1, [[1], [-1]])  # type: ignore[method-assign]
    result = evaluator.evaluate("boom")
    assert result.contradiction
    assert result.prunable
