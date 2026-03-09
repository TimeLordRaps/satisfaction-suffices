# Security Policy

## Reporting a Vulnerability

Report security vulnerabilities via [GitHub Security Advisories](https://github.com/TimeLordRaps/satisfaction-suffices/security/advisories/new) — not via public issues.

Include:
- Description of the vulnerability
- Steps to reproduce
- Affected version(s)
- Potential impact

You will receive a response within 72 hours. Coordinated disclosure preferred: allow time for a patch before public disclosure.

---

## Scope

**In scope:**
- SAT solver correctness issues — bugs where the solver returns SAT on UNSAT input, or vice versa
- Gate bypass vulnerabilities — inputs that reach a closed-gate verdict path incorrectly
- Constraint extractor logic errors that produce systematically wrong verdicts
- Dependency vulnerabilities in transitive packages

**Out of scope:**
- Performance issues (slow solving, timeout behavior) — these are operational, not security
- Theoretical attacks on the constraint extractor coverage (the extractor boundary is documented as a known limitation in the paper)
- Issues in the example code in README/docs that are not part of the installed package

---

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.0.x   | Yes       |

---

## Disclosure Policy

A CVE will be requested for confirmed vulnerabilities affecting the gate's correctness. The patch plus a description of the vulnerability class will be published in the GitHub release notes.
