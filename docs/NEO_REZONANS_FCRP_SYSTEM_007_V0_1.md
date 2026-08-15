# FCRP-SYSTEM-007 — Full-Chain Conformance v0.1

FCRP-SYSTEM-007 is the first bounded proof that one explicit logical operation can be carried through the existing Neo Resonance trust spine and independently reconstructed at the destination.

It does not create a new runtime or a cross-repository transaction coordinator. The workflow composes existing native capabilities at exact revisions:

~~~text
explicit intent
    ↓
ProofPath native SCIG verification
    ↓
CML parent-cause record
    ↓
LiminalDB local_test_only durable write and reopen
    ↓
RINSE read-only source trace and bounded reflection
    ↓
ContractGraph-QA independent replay
~~~

## What is bound

The operation is:

~~~text
logical_operation_id = neo-resonance-system-007-001
nonce                = system-007-nonce-0001
~~~

The intent carries a canonical SHA-256 digest of its argument object. The same logical operation ID is required in the provider decision, ProofPath SCIG, every CML record, the durable summary, the RINSE source trace and the final result.

The workflow pins:

- ProofPath \`4a05ee31d7497979c2505dd55bfef08823302e24\`;
- Causal-Memory-Layer \`2a649903693fc61a560ee056834127ada3120206\`;
- LiminalDB \`61b02fc81e0cb5cf1f1ed4658ecff58f683cb728\`;
- RINSE \`3be0d2ceb1440641b141cdb80c82ed118e4186dd\`;
- the ContractGraph-QA PR subject to the exact workflow head.

A remote \`main\` head drift or an initial/final local checkout mismatch fails the workflow.

## Native transitions

1. The runner validates the explicit intent, including the nonce, argument digest, expected outcome and authority boundary.
2. The existing ContractGraph-QA provider evidence adapter builds the reviewed STOP decision and projects it into the existing ProofPath SCIG contract.
3. ProofPath is checked out at its pinned canonical capability commit and its native \`proofpath-scig\` verifier emits \`RESULT VALID\` and \`VERIFICATION PASSED\`.
4. CML's actual \`CausalRecord\` and \`reconstruct_chain\` APIs create and replay the deterministic root-first chain: \`intent → proofpath decision → CML causal record\`.
5. The existing LiminalDB artifact validator admits the event only as a dry-run artifact. The native \`ProofPathDurableLedger\` then writes a separate ephemeral \`local_test_only\` record.
6. A new LiminalDB consumer process reopens the store and reproduces the original event and admission bytes. A same-semantic retry returns \`ALREADY_PRESENT\` and preserves the first transaction time.
7. The existing RINSE \`liminaldb_durable_proof\` adapter consumes the recovered bytes, derives \`ACCEPT_WITH_LIMITS\`, keeps \`REFLECTION_ONLY\` authority, and performs no write-back.
8. ContractGraph-QA recomputes the native receipt, durable event, CML chain, RINSE loop and FCRP result from raw artifacts.

## Negative-path matrix

The final replay must reject all six cases:

- missing intent;
- replayed nonce;
- changed argument object under the old digest;
- stale dependency head;
- tampered durable record;
- attempted RINSE reflection-to-execution escalation.

A rejected negative case is evidence of the guard, not evidence that an arbitrary external system is safe.

## Authority boundary

Every stage carries:

~~~json
{
  "execution_authorized": false,
  "mutation_authorized": false,
  "external_effects_authorized": false
}
~~~

The LiminalDB write is an explicitly separate local/test storage admission. It is not production persistence authority. RINSE reflection is not truth authority and cannot create an executable handoff. The workflow performs no provider request, wallet action, deployment, merge, financial action or external side effect.

## Run locally

The native external operations require Rust/Cargo and the pinned repositories. From a ContractGraph-QA checkout:

~~~bash
python -m unittest tools.tests.test_fcrp_system_007 -v
python tools/run_fcrp_system_007.py --help
~~~

The complete CI workflow is:

~~~text
.github/workflows/fcrp-system-007-full-chain-conformance.yml
~~~

The machine-readable FCRP case is:

~~~text
benchmarks/fcrp-v0.2/FCRP-SYSTEM-007-full-chain-conformance.json
~~~

## Claim limits

A passing SYSTEM-007 run proves only the bounded fixture and the exact revisions recorded in its evidence manifest. It does not prove:

- production interoperability;
- distributed transactionality;
- tenant or account authorization;
- correctness of every CML, LiminalDB or RINSE use case;
- security of an arbitrary smart contract or external provider;
- completeness of the causal model;
- that a reflection is real-world truth;
- that a green run authorizes merge, deploy or mutation.

The result is advisory evidence for the next system transition. Human review remains the authority for merge, release, disclosure and production use.
