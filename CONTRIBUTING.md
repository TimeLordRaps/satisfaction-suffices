# Contributing to satisfaction-suffices

This is a community paper. The architecture is the floor — contributions build on top of it.

---

## What belongs here

- New constraint extractors (new modalities, new domains)
- Improvements to existing extractors (coverage, accuracy, performance)
- Bug fixes in the SAT solver, verification gate, or proof evolution module
- Additional tests
- Paper corrections (typos, citation errors, clarifications)

## What does not belong here

- Changes to the four-verdict taxonomy (Verified / Contradiction / Paradox / Timeout) — this is the core contribution and its semantics are fixed
- Changes to the gate's default-closed behavior
- Refactors that alter the public API surface without a deprecation path

---

## Extractor contributions — mandatory test requirement

Every new or modified extractor **must** include tests covering both of the following cases:

1. **Known-satisfiable input** — an input where the extractor produces constraints that the solver returns `SAT` for, and the gate verdict is `Verified`.
2. **Known-unsatisfiable input** — an input where the extractor produces constraints that the solver returns `UNSAT` for, and the gate verdict is `Contradiction`.

PRs that add an extractor without both cases will not be merged. This is not bureaucracy — it is how we know the extractor is wired to the gate correctly. A broken extractor that silently passes everything or silently blocks everything is worse than no extractor at all. It gives false confidence in the architecture.

### Minimal test pattern

```python
from satisfaction_suffices.verifier import get_gate, Verdict

gate = get_gate()

def test_my_extractor_satisfiable():
    result = gate.verify("<input that should be consistent>", domain="mydomain")
    assert result.verdict == Verdict.VERIFIED

def test_my_extractor_unsatisfiable():
    result = gate.verify("<input with a clear logical contradiction>", domain="mydomain")
    assert result.verdict == Verdict.CONTRADICTION
```

---

## Pull request checklist

- [ ] Extractor additions include both satisfiable and unsatisfiable test cases
- [ ] `pytest` passes locally: `.venv/Scripts/python.exe -m pytest tests/`
- [ ] No private tooling, internal system names, or proprietary pipeline references in any file
- [ ] If adding a new domain, add a corresponding entry to the extractor registry in `verifier/__init__.py`

**Future:** PRs will be required to attach a ZK receipt — a cryptographic proof of test execution generated inside a zkVM. A bot verifies the receipt in 50ms. You cannot fake a passing test suite; you can only prove one. This is the same architecture as the gate, applied to the repo that defines it.

---

## Paper contributions

The paper (`paper/paper_01_submission.md` and `.tex`) is living documentation. Corrections and clarifications are welcome as PRs. Substantive additions (new sections, new claims) should be opened as issues first for discussion.

---

## License

By contributing, you agree that your contributions will be licensed under the same AGPL-3.0 license as this repository.
