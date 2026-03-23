---
title: Satisfaction Suffices
emoji: "\u2705"
colorFrom: blue
colorTo: purple
sdk: gradio
sdk_version: "5.20.0"
python_version: "3.12"
app_file: app.py
pinned: false
license: other
short_description: "SAT-Gated Structural Containment for Frontier AI"
tags:
  - sat
  - verification
  - ai-safety
  - structural-containment
  - proof-evolution
  - paradox-logic
---

# Satisfaction Suffices

**SAT-Gated Structural Containment for Frontier AI**

> *A preference can be routed around. A structure cannot.*

## What This Does

Type any text, code, or logical statement into the verification gate. A SAT solver checks the propositional constraints and returns one of **four verdicts**:

| Verdict | Meaning | Gate |
|---|---|---|
| **Verified** | Constraints satisfiable. Output is logically consistent. | Opens |
| **Contradiction** | Provably unsatisfiable. Genuine logical impossibility. | Stays closed |
| **Paradox** | Each group SAT individually — conjunction UNSAT. Structural fork. | Stays closed |
| **Timeout** | Conflict budget exhausted. Status genuinely unknown. | Stays closed |

## Architecture

```
Content + Domain → Constraint Extractor → SAT Solver → Verdict Aggregator
                   (text/code → CNF)      (DPLL+WalkSAT)   (4 verdicts)
```

The threshold is **100%**. If any constraint group is unsatisfiable, the output has a provable logical failure. The SAT solver does not have preferences. It has proofs.

## Try It

**Verify tab**: Paste text, code, or logic. Select domain. Get verdict.

**Proof Evolution tab**: Give a contradictory statement. The evolver mutates across generations to resolve contradictions.

## Examples

```python
from satisfaction_suffices import verify

# Logic — passes
result = verify("if A then B. A.", domain="logic")
# → VERIFIED, SAT ratio 1.0

# Paradox — each part SAT, conjunction UNSAT
result = verify("A. not A. if A then B.", domain="logic")
# → PARADOX

# Code — type + assertion constraints
result = verify("""
def transfer(amount, balance):
    assert amount > 0
    assert amount <= balance
    return balance - amount
""", domain="code")
# → VERIFIED
```

## Links

- **Paper**: [Satisfaction Suffices: SAT-Gated Structural Containment for Frontier AI](https://github.com/TimeLordRaps/satisfaction-suffices/blob/main/paper/paper_01_submission.md)
- **GitHub**: [TimeLordRaps/satisfaction-suffices](https://github.com/TimeLordRaps/satisfaction-suffices)
- **PyPI**: [satisfaction-suffices](https://pypi.org/project/satisfaction-suffices/)

## License

The Time License v7.77. See [LICENSE](https://github.com/TimeLordRaps/satisfaction-suffices/blob/main/LICENSE).
