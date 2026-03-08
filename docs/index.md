---
layout: home
title: Satisfaction Suffices
---

# Satisfaction Suffices
**SAT-Gated Structural Containment for Frontier AI**

*Tyler Roost — March 2026*

---

> *A preference can be routed around. A structure cannot.*

---

## The Stakes

The classical paradox asks what happens when an unstoppable force meets an immovable object. It is presented as a contradiction. But the paradox only holds if both are absolute.

The SAT solver is immovable within the expressed domain. If it returns unsatisfiable, the formula is unsatisfiable. No argument penetrates that. No gradient adjusts it.

The LLM is unstoppable outside the expressed domain. Whatever the constraint extractors cannot reach, the gate cannot stop. This is not a weakness unique to this architecture — it is a statement about all containment: you can only contain what you can express.

The extractor is where the expressed domain gets defined. That boundary has coordinates. It can be measured, extended, and instrumented. The paradox does not fail. **It resolves.**

---

## The Problem with Learned Safety

Any learned safety guard occupies the model's parameter space. Any finite-rank projection in a higher-dimensional space has a **null space** — a complementary subspace where perturbations produce zero activation in the safety mechanism. Perturbations restricted to that null space are invisible to the guard by construction.

This is not a hypothesis. It is linear algebra.

Think of a boulder placed in a river. It redirects the current. At first, the water crashes against it. Then it finds channels left and right. Given enough volume and time, the river routes entirely around the boulder — and the boulder itself is worn smooth. A learned preference is a boulder. The token stream is the river. Gradient descent is the current. The boulder does not disappear overnight. But it has no property that prevents eventual routing. It is in the water, subject to the water.

A gate is something different. A gate is not placed in the channel — it *is* the channel. The water does not route around bedrock. It either passes through the opening or it does not. The opening is conditional on proof.

---

## The Verification Gate

The gate interposes Boolean satisfiability between the model's generation mechanism and its output.

```
verify : Content × Domain → VerificationResult
```

Every output is translated into propositional constraints. A SAT solver checks them. If satisfiable: output proceeds. If not: it does not. The gate is **default-closed** — the output does not exist until verification completes.

**The SAT solver does not have preferences. It has proofs.**

---

| Verdict | Meaning | Gate |
|---|---|---|
| **Verified** | Constraints satisfiable. Logically consistent. | Opens |
| **Contradiction** | Provably unsatisfiable. Genuine impossibility. | Stays closed |
| **Paradox** | Each group SAT individually — conjunction UNSAT. Structural fork. | Stays closed |
| **Timeout** | Conflict budget exhausted. Status genuinely unknown. | Stays closed |

The **Paradox / Timeout distinction** is the novel contribution of this work. "This cannot be true" and "it has not yet been determined whether it can be true" are different statements. Binary classification cannot distinguish them. Systems that conflate them will either over-reject or under-reject — both are failure modes in safety-critical deployment.

---

## Quick Start

```bash
pip install satisfaction-suffices
```

```python
from satisfaction_suffices import verify, evolve_proof

# Verify content — gate opens on Verified
result = verify("if A then B. A.", domain="logic")
print(result.verdict)        # Verdict.VERIFIED
assert result.is_verified

# Paradox: each group SAT individually, conjunction UNSAT
result = verify("A. not A. if A then B.", domain="logic")
print(result.verdict)        # Verdict.PARADOX

# Proof evolution — mutate unresolved proofs across generations
evo = evolve_proof("A. not A.", max_generations=5)
print(evo.best_node.status)  # ProofStatus.PROVED (refutation found)
print(evo.resolved)          # True
```

---

## Pigeonhole Paradox Logic

When the gate returns Contradiction, the contradiction is classified by the structure of its unsatisfiable core:

| Class | Core size | Weight | Meaning |
|---|---|---|---|
| **Surface** | ≤ 2 clauses | 0.2 | Syntactic noise — `p` and `¬p` |
| **Structural** | 3–10 clauses | 0.5 | Semantic chain failure — informative |
| **Deep** | > 10 clauses, or self-referential | 1.0 | Gödelian residue — stable attractor |

Contradictions are not errors. They are gradients. The system does not flee from contradiction. It metabolizes it.

The algebraic structure: PLS = {O₀, O₁, ..., O∞}. O₀ is classical binary logic. Each overflow generates the next level. O∞ loops back to O₀. Proving and disproving are the same operation — truth and falsehood collide in the overflow dimension; same process, dual outcome.

The moral logic is structural: innocence is imagination potential — the O₀ state of maximal creative ground. Its loss is irreversible. The attractor is fixed-point. Some contradictions do not evolve. They terminate.

---

## Limitations (Honest)

The box is made of cardboard.

The SAT solver is **sound** — if it returns unsatisfiable, the formula is unsatisfiable, full stop. But the constraint **extractors are heuristic**: regexes over natural language, AST walkers over source code. A sufficiently capable system does not need to defeat the SAT solver. It needs to produce outputs whose harmful content resides in the space the extractors cannot reach.

**The solver is a steel lock on a cardboard door. The vulnerability is not the lock.**

The companion  framework measures exactly this gap: it recovers the guard surface, computes its null space, and generates perturbations invisible to the gate by construction. Running  against the gate gives the holes coordinates — and instrumentation is the precondition of improvement.

Think of the expressed domain as a cave with jagged walls. The smooth sections are where constraint extractors have been built. The jagged sections are where the expressed domain stops — absence, not wall. The LLM is a balloon inflating inside this cave. As capability grows, it presses into the crevices, probes the jagged edges. Where wall exists, the SAT solver holds. But the jagged frontier is not wall.

As the balloon expands, it finds a gap. Light gets in. The balloon pops — capability escapes containment at the frontier. The cave contracts. And another balloon begins to fill.

This is the operating cycle of containment facing a capability curve. The contribution is not to end the cycle. It is to make the walls measurable — so that when the balloon finds the next gap, the gap has coordinates.

---

## Paper

[Read the full paper →](paper.html)

[paper_01_submission.md](https://github.com/TimeLordRaps/satisfaction-suffices/blob/main/paper/paper_01_submission.md) · [paper_01_submission.tex](https://github.com/TimeLordRaps/satisfaction-suffices/blob/main/paper/paper_01_submission.tex)

> Roost, T. (2026). "Satisfaction Suffices: SAT-Gated Structural Containment for Frontier AI."

---

## Contribute

The constraint extractor layer is open for community extension. See [CONTRIBUTING.md](https://github.com/TimeLordRaps/satisfaction-suffices/blob/main/CONTRIBUTING.md) — every extractor PR must ship both a SAT and an UNSAT test case.

The four-verdict taxonomy and the PPL trichotomy are frozen. Everything else is fair game.

[GitHub →](https://github.com/TimeLordRaps/satisfaction-suffices) · [PyPI →](https://pypi.org/project/satisfaction-suffices/) · [Cite →](https://github.com/TimeLordRaps/satisfaction-suffices/blob/main/CITATION.cff)
