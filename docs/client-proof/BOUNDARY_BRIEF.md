# One-Page Recovery Boundary Brief

Use this brief to freeze **one** ambiguous-outcome boundary before a paid fixture begins. Keep unresolved fields as `TBD`; silence or missing evidence is not approval.

| Brief control | Value |
|---|---|
| Boundary name | `[one logical financial operation]` |
| Business owner | `[name / role]` |
| Technical owner | `[name / role]` |
| Version / date | `[version / YYYY-MM-DD]` |
| Source inputs | `[public docs / synthetic trace / sandbox / authorized material]` |
| Authorized test surface | `[local / synthetic / sandbox / written authorization reference]` |

## 1. Business promise

> For `[logical operation and customer outcome]`, the system promises `[economic or control guarantee]` before `[next consequential decision]`.

- Logical operation identity: `[stable business identifier]`
- Promise owner: `[team / role]`
- Explicitly out of scope: `[second provider, rail, wallet, ledger, or operation]`

## 2. Ambiguous action and duplicate-risk retry

- Action dispatched: `[payment / payout / transfer / mint / bridge / other]`
- Ambiguity trigger: `[timeout / lost response / delayed or conflicting evidence / fallback]`
- Next action that becomes possible: `[retry / fallback / release / new credential / other]`
- Duplicate-risk path: `[how that next action could create a second economic effect]`
- Identity that must remain continuous: `[logical operation / attempt / idempotency / authority references]`

## 3. Evidence surfaces

| Surface | Observed signal | What it may prove | What it cannot prove | Freshness / authority condition |
|---|---|---|---|---|
| `[provider / rail / wallet / chain / ledger]` | `[status / webhook / receipt / event / posting]` | `[bounded claim]` | `[remaining uncertainty]` | `[rule or TBD]` |
| `[surface]` | `[signal]` | `[bounded claim]` | `[remaining uncertainty]` | `[rule or TBD]` |

## 4. Authoritative close-out

- Evidence that closes the operation as `ZERO`: `[authoritative rule or TBD]`
- Evidence that closes the operation as `ONE`: `[authoritative rule or TBD]`
- Conflict / precedence rule: `[which evidence wins, why, and at what freshness]`
- Conditions that must remain `UNKNOWN`: `[missing, delayed, conflicting, stale, or non-authoritative evidence]`

## 5. Decision contract

| Classification | Required evidence | Permitted decision |
|---|---|---|
| `ZERO` | Authoritative evidence proves no economic effect | Retry **may** be allowed under the same logical operation and policy |
| `ONE` | Authoritative evidence proves the intended economic effect | Stop; do not create another monetary action |
| `UNKNOWN` | Close-out evidence is incomplete, conflicting, delayed, stale, or non-authoritative | Fail closed; hold retry until reconciliation resolves the state |

## 6. Decision impact

- If `ZERO` is classified incorrectly: `[duplicate / customer / liquidity / accounting impact]`
- If `ONE` is classified incorrectly: `[missed execution / customer / operational impact]`
- If `UNKNOWN` persists: `[hold / support / reconciliation / SLA impact]`
- Owner of the retry, stop, or hold decision: `[team / role]`

## Client checkpoints

- [ ] **Promise** — the business promise, ambiguous action, duplicate-risk retry, identity, and scope are accurate. Owner/date: `[ ]`
- [ ] **Evidence** — the evidence surfaces, authority, freshness, precedence, and unresolved gaps are accurate. Owner/date: `[ ]`
- [ ] **Decision** — the `ZERO / ONE / UNKNOWN` actions and decision impact are accurate. Owner/date: `[ ]`

This brief records the declared contract; it does not make any evidence source authoritative by itself. The fixture and results remain bounded to the confirmed brief, supplied evidence, adapter, environment, and executed test scope. Active non-local testing still requires explicit authorization.
