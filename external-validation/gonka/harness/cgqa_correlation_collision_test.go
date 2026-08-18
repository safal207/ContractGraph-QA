package main

import (
	"encoding/json"
	"os"
	"path/filepath"
	"sort"
	"testing"
	"time"

	"github.com/stretchr/testify/require"
)

type cgqaCorrelationCollisionEvidence struct {
	SchemaVersion                    string   `json:"schema_version"`
	CaseID                           string   `json:"case_id"`
	UpstreamRevision                 string   `json:"upstream_revision"`
	ClientCorrelationID              string   `json:"client_correlation_id"`
	EscrowID                         string   `json:"escrow_id"`
	LogicalOperationsSimulated       int      `json:"logical_operations_simulated"`
	CanonicalRequestRows             int      `json:"canonical_request_rows"`
	AttemptNonces                    []uint64 `json:"attempt_nonces"`
	WinnerNonceAfterSecondCompletion uint64   `json:"winner_nonce_after_second_completion"`
	RecordsCoalesced                 bool     `json:"records_coalesced"`
	CandidateStatus                  string   `json:"candidate_status"`
	Notes                            string   `json:"notes"`
}

// TestCGQAGonkaClientCorrelationCanonicalizationCollision is a storage-level
// design guard, not a claim about Gonka's unmodified HTTP behavior. It models
// the tempting remediation "use caller X-Request-Id as canonical request_id"
// by persisting two independent logical operations under the same
// (request_id, escrow_id) key.
//
// If one request row ends up owning attempts from both operations and the
// second completion overwrites the winner, direct client-ID canonicalization
// is rejected as a production remediation even if it makes timeout lookup easy.
func TestCGQAGonkaClientCorrelationCanonicalizationCollision(t *testing.T) {
	store, err := NewPerfStore(filepath.Join(t.TempDir(), "perf.db"))
	require.NoError(t, err)
	t.Cleanup(func() { require.NoError(t, store.Close()) })
	perf := NewPerfTracker(store)

	clientID := "client-correlation-reused"
	escrowID := "42"
	model := "test-model"

	// Logical operation A.
	perf.RecordAccountingRequestStart(clientID, escrowID, model, time.Unix(100, 0))
	perf.RecordAccountingAttempt(RequestAccountingAttempt{
		RequestID: clientID, EscrowID: escrowID, Nonce: 101,
		HostIdx: 1, ParticipantKey: "host-a", CreatedAt: time.Unix(101, 0),
	})
	perf.CompleteAccountingRequest(clientID, escrowID, 101, "operation_a", "success", time.Unix(102, 0))

	// Independent logical operation B reuses the same caller-controlled ID.
	perf.RecordAccountingRequestStart(clientID, escrowID, model, time.Unix(200, 0))
	perf.RecordAccountingAttempt(RequestAccountingAttempt{
		RequestID: clientID, EscrowID: escrowID, Nonce: 202,
		HostIdx: 2, ParticipantKey: "host-b", CreatedAt: time.Unix(201, 0),
	})
	perf.CompleteAccountingRequest(clientID, escrowID, 202, "operation_b", "success", time.Unix(202, 0))

	rec, ok, err := store.FindAccountingRequest(clientID, escrowID)
	require.NoError(t, err)
	require.True(t, ok)

	var requestRows int
	require.NoError(t, store.db.QueryRow(
		`SELECT COUNT(*) FROM request_accounting WHERE request_id = ? AND escrow_id = ?`,
		clientID, escrowID,
	).Scan(&requestRows))

	nonces := make([]uint64, 0, len(rec.Attempts))
	for _, attempt := range rec.Attempts {
		nonces = append(nonces, attempt.Nonce)
	}
	sort.Slice(nonces, func(i, j int) bool { return nonces[i] < nonces[j] })

	coalesced := requestRows == 1 && len(nonces) == 2 && nonces[0] == 101 && nonces[1] == 202 && rec.WinnerNonce == 202
	status := "SAFE_FOR_CANONICALIZATION"
	notes := "two logical operations remained independently represented under the repeated client correlation id"
	if coalesced {
		status = "REJECTED_AS_PRODUCTION_FIX"
		notes = "two independent logical operations sharing one caller-controlled id coalesced into one canonical request row; attempts from both operations coexist and the second completion becomes the request winner"
	}

	evidence := cgqaCorrelationCollisionEvidence{
		SchemaVersion:                    "gonka-correlation-collision-v0.1",
		CaseID:                           "G-002-COLLISION",
		UpstreamRevision:                 os.Getenv("CGQA_UPSTREAM_REVISION"),
		ClientCorrelationID:              clientID,
		EscrowID:                         escrowID,
		LogicalOperationsSimulated:       2,
		CanonicalRequestRows:             requestRows,
		AttemptNonces:                    nonces,
		WinnerNonceAfterSecondCompletion: rec.WinnerNonce,
		RecordsCoalesced:                 coalesced,
		CandidateStatus:                  status,
		Notes:                            notes,
	}

	if dir := os.Getenv("CGQA_EVIDENCE_DIR"); dir != "" {
		require.NoError(t, os.MkdirAll(dir, 0o755))
		data, err := json.MarshalIndent(evidence, "", "  ")
		require.NoError(t, err)
		require.NoError(t, os.WriteFile(filepath.Join(dir, "reconciliation.json"), append(data, '\n'), 0o644))
	}

	// The current storage contract is expected to demonstrate the collision;
	// this guard fails if that assumption changes, forcing remediation design
	// to be re-evaluated rather than silently carrying an obsolete warning.
	require.True(t, coalesced, "expected repeated canonical request_id to coalesce request accounting records; observed=%+v", evidence)
}
