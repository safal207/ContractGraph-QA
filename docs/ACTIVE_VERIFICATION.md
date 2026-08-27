# Active Verification Planner

The active-verification layer ranks verification work under explicit capacity and budget constraints.

Run:

```bash
python -m contractgraph_qa.active_verification_cli plan --input campaign.json
python -m contractgraph_qa.active_verification_cli record-cost --input observation.json
```

Every work item receives one deterministic disposition: `SELECTED`, `DEFERRED_CAPACITY`, `DEFERRED_BUDGET`, `DEFERRED_OVERSIZED`, `BLOCKED_PREREQUISITE`, or `UNMODELED_INFORMATION_VALUE`.

Cost provenance remains separated into declared, estimated, and observed cost. Scheduling uses observed cost when an observation receipt exists, otherwise estimated cost; declared cost is retained for provenance but is not trusted as the planning value.

Expected information gain is a ranking input only. `Selected != Verified`, `ExpectedInformationGain != Truth`, and deferred required work remains verification debt.

The policy score combines explicit risk, priority, age, information-gain, and cost weights. Age must have a positive weight to provide anti-starvation pressure. Ties are stable by work ID.

Planner output includes verification-debt receipts compatible with the Phase 2 debt evaluator. A selected work item remains `ADMITTED` debt until a later execution result explicitly resolves it.
