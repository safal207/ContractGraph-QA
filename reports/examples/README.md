# Finding examples

- `CGQA-001` — payout-conservation violation found by action-sequence exploration.
- `CGQA-002` — deposit-cap boundary violation found by parameter corpus exploration.
- `CGQA-003` — refund-timing violation found by explicit temporal action exploration.

Each `.finding.json` file is rendered through `tools/render_finding.py` and checked byte-for-byte against its `.md` golden report in CI.

All examples use deliberately vulnerable local fixtures owned by this repository.
