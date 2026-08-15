# GLOBAL P2-1 — Trust-Spine Cost and Latency Benchmark v0.1

Status: **experimental / observed / read-only**

## Purpose

P2-1 measures one already-completed Neo Resonance trust-spine run without re-executing the full system solely to create timing data.

Measured route:

```text
intent → ProofPath → CML → LiminalDB → RINSE → ContractGraph-QA
```

The frozen observation is GitHub Actions run `31879737027`, job `95000538396`, measured subject:

```text
7fd3e744037832b74b2ee4c4c71cc8fce18fc329
```

That run was the successful FCRP-SYSTEM-007 full-chain conformance run.

The P2-1 verifier is a later, separate exact-head subject. Measured subject and verifier subject must never be conflated.

## Observed result

The GitHub Actions source timestamps are one-second resolution.

| Metric | Observed |
|---|---:|
| Full job elapsed | 45 s |
| Substantive window | 35 s |
| Sum of substantive step durations | 35 s |
| Runner/setup/teardown outside substantive window | 10 s |
| Substantive steps | 13 |
| Evidence artifact count | 1 |
| Evidence artifact bytes | 28,222 |

Measurement groups inside the 35-second substantive window:

| Group | Observed seconds | Share of substantive window |
|---|---:|---:|
| `liminaldb` | 23 | 65.7% |
| `proofpath` | 8 | 22.9% |
| `preflight` | 3 | 8.6% |
| `rinse` | 1 | 2.9% |
| `intent_cml` | 0 | below source resolution |
| `contractgraph_qa` | 0 | below source resolution |
| `evidence_packaging` | 0 | below source resolution |

The dominant measured group is therefore `liminaldb`, specifically the workflow interval containing durable write/reopen work.

This is a routing/engineering signal, not a performance SLA. It says where this one observed run spent visible wall-clock time.

## Cost boundary

P2-1 deliberately separates measured cost proxies from unknown cost.

Measured:

- GitHub Actions wall-clock time;
- per-step/group time at source resolution;
- substantive step count;
- evidence artifact bytes.

Not measured:

- GitHub/provider billing in USD;
- CPU seconds;
- memory consumption;
- network bytes;
- energy use;
- production latency.

Therefore:

```text
monetary_cost_status = NOT_MEASURED
monetary_cost_usd = null
```

The benchmark must fail closed if a monetary value is fabricated.

## Source integrity

The source observation records:

- workflow run ID;
- job ID;
- exact measured head;
- exact substantive step names/numbers/timestamps;
- artifact ID, byte size and SHA-256 digest;
- a canonical snapshot digest.

CI also reads the GitHub Actions API for the frozen run and independently compares the immutable source fields with the committed observation.

Artifact expiration state is not treated as an immutable field during later live attestation; the original observation records that the artifact was unexpired when captured.

## Independent verification

`tools/trust_spine_cost_latency.py` derives a deterministic measurement receipt.

`tools/trust_spine_measurement_verifier.py` independently recomputes:

- source snapshot integrity;
- job elapsed time;
- substantive window;
- every step duration;
- group aggregates;
- runner overhead;
- step count;
- artifact count/bytes;
- receipt digest;
- authority boundary.

The independent verifier does not import the producer module.

## Negative controls

The regression suite rejects at least:

- reordered steps;
- impossible/negative duration;
- changed measured subject;
- changed source artifact identity;
- fabricated monetary cost;
- inconsistent aggregate even after re-sealing the receipt;
- receipt digest tamper;
- authority escalation.

## Authority boundary

Policy:

```text
READ_ONLY_MEASUREMENT_NO_AUTHORITY
```

Every measurement and verification receipt keeps all authority flags false.

P2-1 grants no merge, deployment, production persistence, payment, execution, mutation, security, or external-effect authority.

## Relationship to Graph–Field Dynamics

GFD v0.2 selected P2-1 before this measurement was inspected.

The observed P2-1 result is therefore usable as a **post-selection outcome observation**:

- it produced discriminating information;
- it identifies `liminaldb` as the dominant visible latency group in this run;
- it quantifies evidence-package size;
- it keeps monetary cost explicitly unknown.

This does not by itself prove GFD beat FIFO, human routing, or another baseline. A calibration update must remain blocked until an explicit comparison baseline is available under frozen utility criteria.
