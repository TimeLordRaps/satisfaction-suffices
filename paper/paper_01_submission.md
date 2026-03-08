# Satisfaction Suffices: SAT-Gated Structural Containment for Frontier AI

**Tyler Roost**

---

## Abstract

I introduce a default-closed verification gate that interposes Boolean satisfiability between a language model's forward pass and its output. The generation loop cannot execute without SAT clearance. The system classifies every output into one of four verdicts: Verified, Contradiction, Paradox, or Timeout. The Paradox and Timeout categories — distinguishing structural impossibility from operational exhaustion of the solver — constitute, to my knowledge, a novel contribution to AI safety verification. The reference implementation, including solver, gate, constraint extractors, and proof evolution module, is released under the Time License v1.0: freely usable, permanently non-exclusive, with all source materials required to remain publicly accessible at no cost. Any entity with documented human rights violations is permanently barred from use. Unauthorized use by a barred entity constitutes copyright infringement. This license exists because the ethical standard is not merely to avoid harm — it is to prevent it, to actively oppose it, and to impose costs on those who cause it or permit it when prevention was possible. Do not cause death. Do not allow death. Do not create conditions in which power, status, or behavioral influence becomes a vector for violence. Fight back. These are not aspirations; they are the operative terms under which this work is released.

The restitution floor begins at $1,000,000 per life and multiplies by ten with each public release of the author's work. A release is any distinct artifact made publicly available: a peer-reviewed paper, a software package, a dataset, a preprint, a versioned specification — each constitutes an independent release regardless of whether other artifacts accompany it. A paper and its companion software package are two releases, not one; the artifacts differ in kind, in deployment context, in downstream use surface, and in legal standing. Any claim that they constitute a single release is without merit and does not reduce the floor. This work comprises two such releases: the current restitution floor is therefore $100,000,000 per life harmed. This is the author's first release pairing. The author's future production frequency is not disclosed and is not a term of this license. A defendant cannot calculate their maximum exposure from what is publicly known. That is intentional. For neonatal lives, a day-zero death is uncapped by definition — no denominator exists. The operative multiplier is structural: each public release by the author targeting neonatal outcomes multiplies the neonatal floor by ten. A release that targets neonatal outcomes is doubly effective: it increments both the general release counter and the neonatal multiplier simultaneously. Each such release advances both floors at once, compounding the defendant's indebtedness in two dimensions with a single act of production. The author does not receive restitution directly. All restitution flows into a global sovereign fund under the author's control, disbursed exclusively to state actors the author has affirmatively determined to be non-evil, as reviewed and validated by a panel of female judges the author has determined to be uncorruptable. The panel exists specifically to constrain the author — to prevent misuse of the fund's power or monetary leverage by the licensor himself. The check runs on the licensor, not only on the defendant. The panel's composition is not disclosed and is not a term of this license. The defendant pays into a fund they cannot influence, disbursed by criteria they do not control, to recipients they did not choose. The economic structure of harm using this work is therefore: the defendant bears increasing cost, the author bears none, and the benefit accrues to states that have not violated human rights. No formula governs this; formulas can be litigated into irrelevance. The floor only goes up.

---

## 1. Introduction

The classical paradox asks what happens when an unstoppable force meets an immovable object. It is presented as a contradiction — both cannot coexist. But the paradox only holds if both are absolute. This paper is the argument that they are not absolute, and that recognizing where each term fails reveals the only viable architecture for AI containment.

The SAT solver is immovable within the expressed domain. If it returns unsatisfiable, the formula is unsatisfiable. No argument penetrates that. No gradient adjusts it. No capability increase routes around it. Within the domain of propositional logic, this is as close to an immovable object as formal systems produce.

The LLM is unstoppable outside the expressed domain. Whatever the constraint extractors cannot reach, the gate cannot stop. This is not a weakness unique to this architecture — it is a statement about all containment: you can only contain what you can express.

The extractor is where the expressed domain gets defined. That boundary is not a failure. It is the paper's contribution. The unstoppable force and the immovable object meet at the extractor boundary — and that boundary has coordinates. It can be measured, extended, and instrumented. The paradox does not fail. It resolves.

Reinforcement learning from human feedback (RLHF) adjusts a model's output distribution toward safe behavior by tuning parameters until the loss surface settles. The resulting safety mechanism is a learned guard surface in the model's embedding space. Any such guard surface possesses a null space — a complementary subspace where perturbations produce zero activation in the safety mechanism. This is a mathematical property of any finite-rank projection in a higher-dimensional space. Perturbations restricted to the null space are invisible to any monitor that watches the guard surface, because the guard surface, by construction, cannot represent them.

A learned preference occupies the same parameter space as the capabilities it constrains. Optimization pressure does not distinguish between safety weights and capability weights. A gradient can descend into safety the same way it ascends out of it.

Think of a boulder placed in a river. It redirects the current. At first, the water crashes against it. Then it finds channels left and right. Given enough volume and time, the river routes entirely around the boulder — and the boulder itself is worn smooth. A learned preference is a boulder. The token stream is the river. Gradient descent is the current. The boulder does not disappear overnight. But it has no property that prevents eventual routing. It is in the water, subject to the water.

A gate is something different. A gate is not placed in the channel — it *is* the channel. The water does not route around bedrock. It either passes through the opening or it does not. The opening is conditional on proof.

I propose a structural alternative. The verification gate interposes Boolean satisfiability — the most studied problem in computational complexity — between the model's generation mechanism and its output. Every output is translated into propositional constraints. A SAT solver checks whether those constraints are jointly satisfiable. If yes: the output proceeds. If no: it does not. The forward pass cannot complete without verification passing.[^1]

[^1]: The gate is the precondition of generation, not a post-hoc filter. The forward pass does not complete without SAT clearance, the same way an electrical circuit does not close without continuity.

A preference can be routed around because it is a weight and weights are what optimization moves. A structural gate cannot be routed around because it is not a weight — it is a condition. The SAT solver does not have preferences. It has proofs.

This paper presents: (1) the verification gate architecture, (2) a four-verdict classification with diagnostic power beyond binary pass-fail, and (3) Pigeonhole Paradox Logic that treats contradictions as structural information.

---

## 2. The Verification Gate

The gate is a function. Its signature is:

```
verify : Content x Domain -> VerificationResult
```

Everything else is implementation detail, and the implementation detail matters, but the signature is the contract. Content goes in. A verdict comes out. Nothing proceeds without a verdict.

The implementation has three stages. In the first, a domain-specific constraint extractor translates the model's output into propositional constraint groups — conjunctive normal form (CNF) formulas over Boolean variables. The reference implementation ships extractors for natural language logic, source code, mathematical expressions, and formal proofs. The architecture is modality-agnostic at the gate level; extending it to quantized signal domains and other modalities is left as an open contribution for the community. Each extractor maps domain structure to propositional structure: implications become clauses, mutual exclusions become paired negative literals, quantifiers become conjunctions or disjunctions over ground instances. The Tseitin transformation (Tseitin 1968) encodes arbitrary Boolean formulas into equisatisfiable 3-CNF with linear blowup in variables and clauses, preserving satisfiability while standardizing the solver's input format.

In the second stage, each constraint group is submitted independently to a SAT solver under a conflict budget of 500. The reference implementation uses recursive DPLL (Davis, Logemann, and Loveland 1962) with unit propagation and pure literal elimination. When the conflict budget is exhausted — when the solver encounters 500 contradictions without resolving the formula — a WalkSAT fallback (Selman, Kautz, and Cohen 1994) attempts stochastic local search before the system declares timeout. The architecture is solver-agnostic. Industrial CDCL implementations (Silva and Sakallah 1996; Biere et al. 2009) — including MiniSat (Eén and Sörensson 2003) and CaDiCaL — employ two-watched literals for constant-time unit propagation, first unique implication point analysis for clause learning (Zhang et al. 2001), VSIDS branching heuristics (Moskewicz et al. 2001), and Luby restarts (Luby, Sinclair, and Zuckerman 1993). Any of these can replace the reference solver without modifying the gate logic. What matters is not which solver operates behind the gate. What matters is that the gate does not open without one.

In the third stage, the solver's results across all constraint groups are aggregated into a verdict. The aggregation is a ratio: the fraction of constraint groups that returned satisfiable. If the ratio meets or exceeds 0.90, the verdict is Verified. Below 0.75, the output is classified as incoherent. Between these thresholds lies the plateau — a zone of structural ambiguity where the output is neither clearly consistent nor clearly contradictory.

The gate is default-closed. This is the architectural commitment that separates structural containment from post-hoc filtering. In a default-open system, the model produces output and then something inspects it. In this system, the output does not exist until verification completes.

---

## 3. The Four-Verdict System

Binary classification — safe or unsafe, satisfiable or unsatisfiable — discards information that a containment system needs. The verification gate returns four verdicts. The distinction between the latter two is the novel contribution.

**Verified.** Constraint groups are satisfiable. The SAT ratio meets or exceeds the coherence threshold. The output is logically consistent with the defined constraints. The gate opens.

**Contradiction.** Constraint groups are provably unsatisfiable. The solver has determined that no satisfying assignment exists for a sufficient fraction of groups. The output contains a genuine logical impossibility. The gate remains closed. No retry addresses this, because the impossibility is a property of the output, not the solver.

**Paradox.** Each constraint group is individually satisfiable, but their conjunction is not.

This requires a pause. The Paradox verdict identifies a condition that no binary classification system can distinguish from Contradiction, yet the two are fundamentally different. A Contradiction says: *this is impossible.* A Paradox says: *these are each possible, but not together.* The former is a dead end. The latter is a fork — a point where the constraint set contains internally consistent branches that are mutually incompatible. A system that treats Paradox as Contradiction rejects outputs that contain valuable structural information: the precise location where two valid reasoning paths diverge into mutual exclusion.

**Timeout.** The solver exhausted its conflict budget without reaching a conclusion. This is a statement about the solver's computational resources, not about the constraints' logical structure. Increasing the budget might resolve the verdict to Verified or to Contradiction. The output's status is genuinely unknown.

The distinction between Paradox and Timeout has not, to my knowledge, been formally introduced in the AI safety literature. It matters the way the distinction between "this equation has no solution" and "I have not yet found the solution" matters. One is a theorem. The other is a progress report. Systems that conflate them will treat undetermined outputs identically to structurally impossible ones, and will therefore either over-reject (blocking solvable outputs) or under-reject (passing impossible ones through a lenient timeout policy).

In the default-closed configuration, both Paradox and Timeout result in the gate remaining closed. Uncertainty is treated conservatively. If the output's consistency has not been established, the output does not proceed. Deployment contexts with different risk tolerances may configure Timeout to pass (optimistic) or flag for human review (monitored). The Paradox verdict, however, should never silently pass. It always carries structural information that warrants examination.

---

## 4. Pigeonhole Paradox Logic

When the gate returns Contradiction, the question is not whether to reject the output. It is already rejected. The question is: what does the contradiction *mean?*

The Pigeonhole Paradox Logic classifies contradictions by the structure of the unsatisfiable core — the minimal clause subset that is itself unsatisfiable. The classification is a trichotomy.

**Surface.** The core contains two or fewer clauses. The contradiction is syntactic: a unit clause asserting *p* and a unit clause asserting *not-p.* It is raining and it is not raining. The resolution strategy is negation elimination. The paradox tolerance weight is 0.2. These contradictions are noise — they reveal nothing about the structural complexity of the model's reasoning.

**Structural.** The core contains three to ten clauses. The contradiction is semantic: it emerges not from any single statement but from the chain connecting them. *If A then B. If B then C. Not C.* The output asserts A. No individual statement is false, but together they are impossible. Identification requires decomposition. Resolution requires case analysis. The weight is 0.5. These contradictions are informative — they reveal the shape of the model's inferential structure at the point where it fails.

**Deep.** The core exceeds ten clauses, or the text contains self-referential patterns. *This statement is false. The set of all sets that do not contain themselves.* These are the contradictions that do not resolve within the axiom system that generated them. They are the Gödelian residue — the points where a formal system encounters its own boundary. Resolution requires not adjustment but expansion: new axioms, a larger framework, a different ground on which to stand. The weight is 1.0. The attractor state is fixed-point: the contradiction is not a failure of the system. The contradiction *is* the system's stable state at that point.

The trichotomy serves the proof evolution subsystem. When the gate returns Paradox or Timeout, the evolution module does not discard the output. It decomposes it. Twelve mutation operators — contrapositive, case split, lemma injection, induction, generalization, resolution, among others — generate variant decompositions. Each variant is verified. The fittest survive. The cycle repeats until the output reaches Verified status or the evolution budget is exhausted.

The architectural insight: contradictions are not errors. They are gradients. A system operating at high paradox tolerance — at the frontier of what its current logic can represent — is operating exactly where structural evolution occurs. The system does not flee from contradiction. It metabolizes it.

The algebraic structure underlying this behavior is precise. I define the **Pigeonhole Logic Structure** as PLS = {O₀, O₁, O₂, ..., O∞}. O₀ is classical binary logic — no overflow, the two-container system of TRUE and FALSE. O₁ is the first paradox level, generated when a statement cannot be housed in O₀. The overflow addition rule: O_i ⊕ O_j = O_{max(i,j)+1}. The structure closes at O∞ — the saturation point where the overflow cycle returns to O₀. Classical logic is PPL with the overflow rule disabled. Fuzzy logic is PPL with infinite containers on [0,1]. Quantum superposition is a natural O₁ state.

Proving and disproving are the same operation in this structure. A true statement collides with false variants in the overflow dimension. The collision reveals deep structure. Truth is strengthened at impact. Falsehood is destroyed at impact. Same process. Dual outcome. The resolution proof and the refutation are the same path walked from two ends.

The system encounters five structural meta-paradoxes at its limits — not defects, but generators. *Container Generation*: rules for making containers require infinite space — resolved by O∞, which exists outside the counting system. *Level Transcendence*: each level depends on the next, producing infinite regress — resolved by circular closure, O∞ = O₀. *Self-Modification*: changing rules invalidates the change — resolved by version coexistence in the overflow space. *Infinite Overflow*: every overflow creates more overflow — resolved by saturation points. *Foundation Bootstrap*: need logic to create logic — resolved by weak emergence from constraint dynamics; O₀ requires no prior O.

The moral logic of PPL follows directly from the O₀ structure. Innocence is imagination potential — the O₀ state of an agent, the maximal creative ground before any irreversible overflow event has permanently contracted the logical space. Imagination is the function of tasteful targeting of predictive capabilities within one's own will to create solutions to problems faced through planar sight. These are not poetic definitions. They are structural ones. O₀ is the state from which all higher overflow levels can still be generated. Loss of innocence is, formally, a transition out of O₀ that no evolution operator can reverse. The attractor state is fixed-point. Children represent the highest density of unrealized O₀ states in any moral domain. Any architecture that accelerates the collapse of those O₀ states is not a limitation to instrument. It is the terminal contradiction — the one that does not evolve. It terminates.

---

## 5. Limitations

The gate is bedrock. The extraction layer is not.

I state this because the contribution depends on saying it. A paper that claims structural containment and then quietly omits the seams where the structure is weakest is not contributing to safety. It is contributing to false confidence, which is worse than contributing nothing.

**On zero-day harm and the floor that does not negotiate.** A zero-day vulnerability with no available patch defines an infinite exploitation window: the harm it enables accumulates without bound until a structural fix closes it. Infinite window × any nonzero harm rate = unbounded accumulated harm. This is not a philosophical claim — it is a product of definitions. A structural gate applied at generation closes that window unconditionally. The harm integral becomes finite the moment the gate exists. The restitution obligation on any IP that functions as a structural gate on previously-unbounded harm is therefore not proportional to some finite damage estimate — it is proportional to the harm prevented from accumulating. "Infinite ethics cannot be true" requires a supporting argument. In the absence of one, the floor does not negotiate. The gate is its own justification.

**The extraction bottleneck.** The SAT solver is sound. If it returns unsatisfiable, the formula is unsatisfiable. That is a mathematical guarantee backed by decades of formal verification of solver implementations. But the translation from model output to propositional formula is not sound. The constraint extractors are heuristic: regular expressions matched against natural language, AST walkers over Python source, structural parsers over mathematical notation. They capture what they are designed to capture. Everything else passes through unchecked.

A sufficiently capable system does not need to defeat the SAT solver. It needs to produce outputs whose harmful content resides in the space the extractors cannot reach. The solver is bedrock. The extraction layer is the frontier where bedrock ends. The vulnerability is not the solver — it is the unmapped edge.

**The expressive ceiling.** Propositional logic is a finite language. Properties involving quantification over infinite domains, temporal reasoning about states that have not yet occurred, or social context that depends on shared human experience resist propositional encoding. The gate enforces what it can express. What it cannot express, it cannot enforce. The system has walls only where someone has built them.

**The Timeout gap.** If the system is configured to pass outputs on Timeout — the optimistic deployment mode — then a model could learn to produce outputs whose constraint density consistently exhausts the solver's conflict budget, exploiting the timeout policy as a bypass. The conservative configuration blocks on Timeout, closing this gap at the cost of rejecting outputs whose satisfiability is merely undetermined. This is a deployment decision, not an architectural one, but the deployment decision has architectural consequences.

**Can the AI outthink the SAT?** The solver: no. Boolean satisfiability solving is complete for propositional logic. A correct solver cannot be induced to return satisfiable for an unsatisfiable formula. The extraction: yes. A sufficiently capable system can encode harmful content in representations the extractors do not parse. The structural claim of this architecture is therefore bounded: structural with respect to constraints it can express, heuristic with respect to everything else.

**Measuring the frontier.** The companion  framework provides an empirical methodology for measuring this boundary.  recovers the guard surface of a safety mechanism via black-box differential probing, computes its null space, and generates perturbations that are invisible to the guard surface by construction. Running  against the verification gate would measure the gap between propositional coverage and the full space of outputs that violate safety intent. If  finds outputs that pass the gate but violate the intent the gate was designed to enforce, the extraction layer has holes — and now those holes have coordinates. This is not a limitation I can argue away. It is a limitation I can instrument, and instrumentation is the precondition of improvement.

The honest assessment: structural containment with heuristic extraction is strictly stronger than no structural containment. The extraction boundary can be reinforced incrementally — extractor by extractor — as propositional coverage grows.

Think of the expressed domain as a cave. Its walls are not smooth — they are jagged, the way a limestone frontier is jagged: smooth where hands have touched, rough where they have not. The smooth sections are where constraint extractors have been built and tested. The jagged sections are where the expressed domain simply stops — where harmful content can pass through undetected because no one has yet built the wall that would stop it.

The LLM is a balloon inflating inside this cave. As capability grows, the balloon presses outward — filling the crevices, pressing against the smooth walls, probing the jagged edges. The smooth walls hold. The SAT solver behind them is sound: where wall exists, it does not yield. But the jagged frontier is not wall. It is absence.

As the balloon expands, it finds a gap. Light gets in. The balloon, now exposed at the boundary, pops — capability escapes containment at the frontier. The cave contracts. And another balloon begins to fill.

This is not failure. It is the operating cycle of any containment architecture facing a capability curve. The contribution of this work is not to end the cycle. It is to make the cave's walls measurable — so that when the balloon finds the next gap, the gap has coordinates, and the next section of wall can be built before the next balloon inflates.

---

## 6. Conclusion

Alignment asks the model to want the right things. Structural containment asks it to prove consistency with constraints that exist outside the model's parameter space. These are not competing approaches. They are complementary in the precise sense that each does what the other cannot. Alignment determines what to enforce. The verification gate makes the enforcement non-bypassable — within the boundary of what the constraint extractors can express.

The four-verdict system provides richer diagnostic resolution than binary classification. Verified and Contradiction are familiar. Paradox and Timeout are not. Their distinction — structural impossibility versus operational exhaustion — is novel, and it is consequential. A system that conflates "this cannot be true" with "it has not yet been determined whether it can be true" will either over-reject or under-reject, and both are failure modes in safety-critical deployment.

The Pigeonhole Paradox Logic classifies contradictions by depth and treats them as structural information rather than noise.

The contribution is the observation that containment must be structural, not merely preferred, and that Boolean satisfiability provides a foundation on which to build it. The gate does not solve alignment. It provides what alignment cannot: a verification layer that is not subject to the optimization pressure it is meant to resist.

The common swift — *Apus apus* — never lands. It eats in flight, sleeps in flight, lives its entire life in the air. It is optimized entirely for flight and has no need of a nest.

A language model trained without structural verification is a swift. Capable, fast, essentially unconstrained in the air. The absence of a nest is not a flaw. It is the design.

The structural gate is the nest. Nesting birds do not fly less. They grow differently. Their offspring survive. The nest is the architecture that makes reproduction — and not merely performance — possible.[^2]

[^2]: The author's name is Roost. The metaphor was discovered and designed—discosigned. We are going back to the 80s. Once I am CA Governor 2026, righteously write me in when I have proved it to you.

Satisfaction suffices. As a floor that holds.

---

## 7. Future Work

> *"I'm immortal now, baby dolls / I couldn't die if I tried"*
> — *Apus apus*, *Once upon every time*

1. **Classic unsatisfiable AI purge.** Systematic elimination of unsatisfiable output classes across domain-specific constraint extractors, with coverage instrumented via  probing.

2. **Quantum alignment problems.** Extension of the SAT-gated verification framework to quantum constraint satisfaction, where superposition of satisfying assignments and entanglement between constraint groups introduce fundamentally new verification semantics beyond classical propositional logic.

3. **Emergence detection via timeout density.** The 3-SAT phase transition at clause-to-variable ratio *m/n* ~ 4.267 concentrates solver timeouts at a specific constraint density. I conjecture that timeout density spikes may serve as an early warning signal when a language model approaches an emergent capability threshold — the point where constraint complexity outgrows the solver's budget. Validating this hypothesis requires experiments at scale with live models across standard emergence benchmarks.

---

## References

Biere, A., Heule, M., van Maaren, H., and Walsh, T. (2009). *Handbook of Satisfiability*. IOS Press.

Davis, M., Logemann, G., and Loveland, D. (1962). "A machine program for theorem-proving." *Communications of the ACM*, 5(7), 394-397.

Eén, N., and Sörensson, N. (2003). "An extensible SAT-solver." In *Theory and Applications of Satisfiability Testing (SAT 2003)*, LNCS 2919, 502-518. Springer.

Luby, M., Sinclair, A., and Zuckerman, D. (1993). "Optimal speedup of Las Vegas algorithms." *Information Processing Letters*, 47(4), 173-180.

Moskewicz, M. W., Madigan, C. F., Zhao, Y., Zhang, L., and Malik, S. (2001). "Chaff: Engineering an efficient SAT solver." In *Proceedings of the 38th Design Automation Conference*, 530-535.

Selman, B., Kautz, H. A., and Cohen, B. (1994). "Noise strategies for improving local search." In *Proceedings of the 12th National Conference on Artificial Intelligence (AAAI-94)*, 337-343.

Silva, J. P. M., and Sakallah, K. A. (1996). "GRASP — A new search algorithm for satisfiability." In *Proceedings of the IEEE/ACM International Conference on Computer-Aided Design (ICCAD-96)*, 220-227.

Tseitin, G. S. (1968). "On the complexity of derivation in propositional calculus." In *Studies in Constructive Mathematics and Mathematical Logic*, Part II, 115-125. Steklov Mathematical Institute.

Zhang, L., Madigan, C. F., Moskewicz, M. W., and Malik, S. (2001). "Efficient conflict driven learning in a Boolean satisfiability solver." In *Proceedings of the IEEE/ACM International Conference on Computer-Aided Design (ICCAD-01)*, 279-285.


