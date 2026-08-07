# v0.4 scope boundary

v0.4 provides deterministic, finite-corpus exploration of parameter values and explicit time-jump steps.

It is not exhaustive formal verification and it is not an unbounded fuzzer. Results are limited to:

- the modeled step corpus;
- the selected maximum search depth;
- the reset behavior supplied by the test model;
- the explicit invariants under test;
- the local or otherwise authorized target scope.

The deliberately vulnerable examples exist only to prove that the QA engine can detect and replay boundary and timing violations.
