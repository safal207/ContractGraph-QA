# Attenu observer-envelope v1.2 — independent row-19 proof

**Result: 19/19 AGREE.** The unchanged v1.1 independent envelope-verification core accepted all five controls, rejected all fourteen negative cases, reported every required `{reason, seq, node}` at its declared position, and reproduced every expected entry state.

The only added adversarial row is:

`reject_duplicate_subject_defective_second`

It asks whether a verifier claims `subject.seq` before validating the rest of a second envelope. The second envelope targets the same entry as an earlier valid envelope but carries a defective signature. A validate-first implementation can discard it as merely invalid and leave the first statement `witness-signed`; a claim-first implementation reports `envelope_duplicate_subject` and falls the contested entry back to `process-asserted`.

## Frozen subject

| Subject | Pin |
|---|---|
| Python repository | `attenu-io/attenu-guard@8a8d598e2036d6815b50df01b776a13777c1d72b` |
| Python release | `v0.15.0` |
| PyPI distribution | `attenu-guard==0.15.0` |
| TypeScript repository | `attenu-io/attenu-guard-ts@ae055c92ce2f23e476c42b1a742c3babfa543bb2` |
| TypeScript release | `v0.9.0` |
| Contract / revision | `envelope_vectors_v1` / `envelope_vectors_v1.2` |
| Cases | `19` |
| Bytes | `197,346` |
| Vector SHA-256 | `a8be5ff764a86122ca09e94340416b7169531bf5d0cc76a0b1fc87f8272eb16e` |
| Generated report SHA-256 | `4328c5a38e647b601b73fa5ff4a8b8f9f5375296318ba1a5d440372c9edbbd6b` |

The npm tarball is not treated as a raw-vector source because it does not ship the fixture. Hosted CI requires byte identity among the pinned Python repository file, the exact PyPI wheel copy, and the pinned TypeScript repository fixture before scoring.

## Why the new result is meaningful

`verify_envelope_vectors.py` has Git blob `194a68e4c89653e7c819f1ed12156f758bfd7de9`, exactly the same blob used by the published v1.1 18/18 proof. Its ordinary SHA-256 is:

`e814afb84f7e9ecaff4183a3a685f249ca6065309e293e4a224ec9afbba64a8d`

No envelope-validation order or rule was changed for row 19. `run_pinned_proof.py` changes only the subject pins, declared revision, appended case name, report metadata, and an explicit discrimination observation.

The committed report preserves three separately checked facts:

1. **Full row:** `envelope_duplicate_subject` at `seq=1`; entry state is `process-asserted`.
2. **First envelope alone:** no failure; entry state is `witness-signed`.
3. **Defective second envelope alone:** `envelope_bad_signature`; entry state is `process-asserted`.

Together these distinguish the intended claim-first rule from a validate-first prefilter that could silently retain the first envelope's stronger state after a contested duplicate appears.

## Reproduce

The read-only workflow:

`.github/workflows/attenu-envelope-v12-proof.yml`

performs the complete check:

1. checks out the two pinned upstream commits;
2. downloads the exact `attenu-guard==0.15.0` wheel;
3. proves all three available source copies are 197,346-byte-identical and hash to the pinned vector digest;
4. proves the envelope core is byte-identical to the v1.1 proof;
5. regenerates the 19-case report;
6. verifies the row-19 discrimination facts;
7. requires byte-for-byte equality with committed `report.json`.

## Claim ceiling

This establishes independent agreement with one frozen 19-case interoperability corpus. It does **not** establish:

- global capture completeness;
- intended witness coverage;
- witness freshness, independence, or non-equivocation;
- deployment non-bypassability;
- integrity of a stripped top-level `envelopes` array;
- correctness of every implementation;
- A2A adoption, certification, or endorsement.

The existing v1 limits remain visible: an absent envelope does not reveal whether coverage was promised, and envelope-array presence is not committed by the current ledger anchor.
