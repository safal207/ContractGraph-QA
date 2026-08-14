# NEO REZONANS P0-4 — Exact Subject and Ancestry Gate

P0-4 is a machine-only gate for distinguishing the exact checked-out pull
request subject from a stale ancestor, a mutable default-branch observation or
an artifact produced by a different workflow subject.

The workflow reports five independent checks:

1. initial checkout subject equals `EXACT_HEAD`;
2. final subject after the checks still equals `EXACT_HEAD`;
3. the expected pull-request base is an ancestor of `EXACT_HEAD`;
4. workflow name, workflow ref, run id and run attempt identify the expected workflow;
5. the declared artifact subject equals `EXACT_HEAD`.

The report schema is `cgqa.p0-4-ancestry-gate.v0.1`. Each check is explicitly
`PASS`, `HOLD`, `NOT_RUN` or `INCOMPLETE`; unknown or unavailable state never
becomes green. GitHub artifact metadata is checked separately against the
workflow run's `head_sha`, so the report's declared artifact subject cannot be
mistaken for an unverified upload fact.

This gate proves repository/workflow identity and ancestry for the bounded
subject. It does not prove semantic correctness, production readiness, merge
approval, deployment, security certification or external authority. Human review
is not a required transition gate for the bounded advisory scope.
