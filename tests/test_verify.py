from __future__ import annotations

import pytest

from satisfaction_suffices.verifier import VerificationError, VerificationGate, verify


def test_verify_logic_content_is_verified() -> None:
    result = verify("if A then B. A.", domain="logic")
    assert result.is_verified
    assert result.zone == "coherent"


def test_verify_logic_opposites_form_paradox() -> None:
    result = verify("A. not A.", domain="logic")
    assert result.is_paradox
    assert result.n_paradox == result.n_constraints


def test_verify_unsat_extra_constraints_is_contradiction() -> None:
    result = verify("A.", domain="logic", extra_constraints=[[[1], [-1]]])
    assert result.is_contradiction


def test_must_verify_raises_on_non_verified() -> None:
    from satisfaction_suffices.verifier import must_verify

    with pytest.raises(VerificationError):
        must_verify("A. not A.", domain="logic")
