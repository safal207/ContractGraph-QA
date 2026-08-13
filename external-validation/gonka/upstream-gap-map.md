# Gonka upstream coverage map

This file maps ContractGraph-QA verification cases to Gonka's own testenv so we add independent value instead of duplicating existing tests.

## Upstream stack already covers

Gonka's `devshard/testenv` boots a production-like local stack with mock-chain, mock-dapi, mock-openai, two versiond replicas, versiond-router, devshardctl, and shared Postgres. Their shipped scenarios include gateway chat, epoch switch, sticky routing, versiond failover/restart persistence, stale-standby catch-up, validation lease races, rolling updates, escrow warmup, and gRPC-only escrow create/read/chat transport.

## Mapping

| CGQA case | Closest upstream coverage | CGQA delta |
|---|---|---|
| G-001 normal inference | `TestGatewayChat`, `TestG3_GatewayChatGRPCOnly` | Preserve a cross-boundary evidence bundle linking client intent → gateway outcome → devshard/accounting state → later settlement reconciliation. |
| G-002 ambiguous timeout + retry | No direct named scenario found in the current testenv scenario index/search | Inject ambiguity at the client/gateway boundary, preserve one `logical_operation_id` across unique attempts, and verify there is no unexplained duplicate usage/billing effect. |
| G-004 ambiguous settlement retry | gRPC settlement transport and chain mocks exist, but no direct exactly-once ambiguity case identified yet | Distinguish submitted/unknown/confirmed states and reconcile a retry against chain truth. |
| G-005 gateway restart with pending usage | `TestVersiondRestartSessionPersistence`, HA catch-up tests | Extend persistence testing from session survival to causal linkage and accounting reconciliation. |
| G-006 epoch/devshard rotation boundary | `TestEpochSwitch`, escrow long-poll/rotation-related coverage | Verify pending usage has exactly one authoritative settlement owner across the boundary. |

## First independent target

**G-002 is the best first delta.**

Why:
1. It is adjacent to an already healthy `TestGatewayChat` control.
2. It targets a semantic boundary that ordinary transport tests can miss: one user intent vs multiple transport attempts.
3. It can run entirely inside Gonka's Docker-backed local testenv with mock components; no mainnet, real funds, or public disruption is required.
4. It produces an evidence story useful even if the implementation is correct.

## Proposed upstream-shaped execution

1. Boot the standard `devshard/testenv` stack.
2. Run the existing gateway chat control and capture baseline state.
3. Add a test-only fault proxy or client harness behavior that causes the first request result to become ambiguous after dispatch.
4. Retry once under the same `logical_operation_id`, using a distinct `execution_attempt_id`.
5. Query the mock-chain/devshard storage/accounting state after both attempts.
6. Reconcile observed executions and usage effects.
7. Emit a CGQA evidence bundle rather than relying only on a boolean test result.

## PASS contract

A timeout must not be interpreted as proof of non-execution. Final state must be explainable as either:

- one execution / one billable effect, with the retry safely converging; or
- multiple protocol-permitted executions that are explicitly distinguishable and fully reconcilable.

An unexplained duplicate billable mutation, orphan usage record, or inability to map settlement state back to attempts is a failure hypothesis and should be handled privately until triaged.

## Source pin

Coverage analysis was performed against Gonka repository revision `f040d0a5b5ef207a0c431894c9f9e2608f9d3073` so later upstream changes can be diffed explicitly.