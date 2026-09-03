# Adoption readiness definition

For this interoperability wave, “100% ready” is a bounded, testable delivery
state. It does not mean exhaustive security, universal framework support, or
automatic publication to third-party registries.

## Completion gates

| Gate | Acceptance criterion | Evidence |
|---|---|---|
| One protocol | Suite, schemas, fixtures, producer commits, and mutation bytes are digest-pinned | `contractgraph_qa/conformance/liminalqa-v0.1/` |
| Bidirectional semantics | CGQA evidence flows to LiminalQA; Liminal candidates return only as unverified CGQA seeds | [Interop specification](LIMINALQA_INTEROP.md) |
| Three native runners | Python, Rust, and Elixir execute the same 14 vectors | CGQA, LiminalQA, and PythiaLabs draft PR CI |
| Four consumer SDKs | TypeScript/JavaScript, Go, JVM, and .NET reject every declared drift class | [`sdks/`](../sdks/) and SDK Portability CI |
| Human-language entry | The same five-minute path exists in English, Simplified Chinese, Hindi, Spanish, and Arabic | [`docs/i18n/`](i18n/) |
| Discoverability | Package metadata, repository links, keywords, install snippets, and stable coordinates exist | [SDK release guide](SDK_RELEASE.md) |
| Safe distribution | PR CI is read-only; package publishing requires a separate exact-head, credentialed release decision | SDK workflow and release guide |
| Independent review | Findings are fixed and the complete checks/review cycle is repeated on the new exact heads | Draft PR review evidence |

## Fail-closed invariants

Every implementation must preserve all of these invariants:

1. A report is accepted only for suite SHA-256
   `562e2f9ae699f001b9ccf1b2b9f6dd30c435d53d668b5fd9a04ca15ca1e4faac`.
2. Both producer contracts and all 14 case digests match their pins.
3. Every case is `PASS`, observed semantics equal expected semantics, and no
   case reports a side effect.
4. Authority is exactly `conformance_evidence_only` and
   `mayAuthorizeAction=false`.
5. Duplicate keys, unknown critical fields, missing cases, and changed claim
   boundaries are rejected.
6. Validation is local, bounded to 1 MiB, and performs no target action.

## Product boundary

This layer makes evidence portable and easy to consume. It does not replace
fresh replay, target authorization, continuity verification, or production
security review. The market promise is narrower and useful: teams can connect
multiple QA and action-gate ecosystems without silently merging their verdicts.
