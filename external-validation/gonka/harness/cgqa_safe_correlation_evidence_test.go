//go:build testenvci

package citest

import (
	"encoding/json"
	"fmt"
	"net/http"
	"net/url"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"testing"
	"time"

	"devshard/testenv/citest/harness"
	"devshard/testenv/config"
	"devshard/testenv/mockopenai"

	"github.com/stretchr/testify/require"
)

type cgqaCorrelationLookup struct {
	ClientCorrelationID string `json:"client_correlation_id"`
	EscrowID            string `json:"escrow_id"`
	Matches             []struct {
		ClientCorrelationID string `json:"client_correlation_id"`
		InternalRequestID   string `json:"internal_request_id"`
		EscrowID            string `json:"escrow_id"`
		CreatedAt           string `json:"created_at"`
	} `json:"matches"`
	MatchCount int `json:"match_count"`
}

type cgqaAccountingView struct {
	RequestID   string `json:"request_id"`
	WinnerNonce uint64 `json:"winner_nonce"`
	Outcome     string `json:"outcome"`
}

type cgqaSafeCorrelationEvidence struct {
	SchemaVersion                       string   `json:"schema_version"`
	CaseID                              string   `json:"case_id"`
	UpstreamRevision                    string   `json:"upstream_revision"`
	Environment                         string   `json:"environment"`
	ReusedClientCorrelationID           string   `json:"reused_client_correlation_id"`
	InternalRequestIDs                  []string `json:"internal_request_ids"`
	CorrelationMatchIDs                 []string `json:"correlation_match_ids"`
	CanonicalIDsDistinct                bool     `json:"canonical_ids_distinct"`
	AccountingResolvedForEachInternalID bool     `json:"accounting_resolved_for_each_internal_id"`
	WinnerNonces                        []uint64  `json:"winner_nonces"`
	WinnerNoncesDistinct                bool     `json:"winner_nonces_distinct"`
	TimeoutClientCorrelationID          string   `json:"timeout_client_correlation_id"`
	TimeoutObserved                     bool     `json:"timeout_observed"`
	TimeoutCompletionObserved           bool     `json:"timeout_completion_observed"`
	TimeoutCorrelationMatchIDs          []string `json:"timeout_correlation_match_ids"`
	TimeoutAccountingResolved           bool     `json:"timeout_accounting_resolved"`
	Verdict                             string   `json:"verdict"`
	Notes                               string   `json:"notes"`
}

func TestCGQAGonkaSafeCorrelationEvidence(t *testing.T) {
	harness.SkipUnlessEnv(t, "TESTENV_CITEST")
	harness.RequireDocker(t)

	stack, cfg, eps := harness.BootAdversarialStack(t, "cgqa-gonka-safe-corr-*")
	client := harness.GatewayChatClient()
	model := config.PrimaryModelID(cfg)
	adminKey := harness.TestenvAdminAPIKey
	escrowID := harness.GetGatewayEscrowID(t, client, eps.GatewayHTTP)
	caseDir := safeCorrelationCaseDir(t)

	t.Cleanup(func() {
		harness.ResetMockOpenAIFault(t, client, eps.MockOpenAIHTTP)
		if t.Failed() {
			harness.DumpComposeLogs(t, stack, "devshardctl", "versiond-0", "versiond-1", "mock-openai")
		}
	})

	// Regression 1: two independent operations reuse one caller correlation ID.
	reusedClientID := fmt.Sprintf("cgqa-safe-reused-%d", time.Now().UTC().UnixNano())
	bodyA := chatBody(t, model, "CGQA safe correlation independent operation A")
	bodyB := chatBody(t, model, "CGQA safe correlation independent operation B")

	t.Logf("G-CORR-SAFE stage=operation-a dispatch correlation=%s", reusedClientID)
	respA := postIdentityChat(eps.GatewayHTTP, adminKey, reusedClientID, bodyA, client)
	t.Logf("G-CORR-SAFE stage=operation-a complete status=%d err=%v response_request_id=%q", respA.Status, respA.Err, respA.ResponseRequestID)
	require.NoError(t, respA.Err)
	require.GreaterOrEqual(t, respA.Status, http.StatusOK)
	require.Less(t, respA.Status, http.StatusMultipleChoices)
	require.NotEmpty(t, respA.ResponseRequestID)

	t.Logf("G-CORR-SAFE stage=operation-b dispatch correlation=%s", reusedClientID)
	respB := postIdentityChat(eps.GatewayHTTP, adminKey, reusedClientID, bodyB, client)
	t.Logf("G-CORR-SAFE stage=operation-b complete status=%d err=%v response_request_id=%q", respB.Status, respB.Err, respB.ResponseRequestID)
	require.NoError(t, respB.Err)
	require.GreaterOrEqual(t, respB.Status, http.StatusOK)
	require.Less(t, respB.Status, http.StatusMultipleChoices)
	require.NotEmpty(t, respB.ResponseRequestID)

	internalIDs := []string{respA.ResponseRequestID, respB.ResponseRequestID}
	canonicalDistinct := internalIDs[0] != internalIDs[1]

	corrReuse := requireCorrelationLookup(t, client, eps.GatewayHTTP, adminKey, escrowID, reusedClientID, 2, 8*time.Second)
	writeJSONArtifact(t, caseDir, "reused-correlation.lookup.json", corrReuse)
	matchIDs := correlationInternalIDs(corrReuse)

	acctA, okA := requireInternalAccounting(t, client, eps.GatewayHTTP, adminKey, escrowID, internalIDs[0], 8*time.Second)
	acctB, okB := requireInternalAccounting(t, client, eps.GatewayHTTP, adminKey, escrowID, internalIDs[1], 8*time.Second)
	writeJSONArtifact(t, caseDir, "operation-a.accounting.json", acctA)
	writeJSONArtifact(t, caseDir, "operation-b.accounting.json", acctB)
	winnerNonces := []uint64{acctA.WinnerNonce, acctB.WinnerNonce}
	winnerDistinct := acctA.WinnerNonce != 0 && acctB.WinnerNonce != 0 && acctA.WinnerNonce != acctB.WinnerNonce

	// Regression 2: client times out before any generated internal ID reaches it.
	beforePerf := requireDevshardDebugPerf(t, client, eps.GatewayHTTP, adminKey, escrowID)
	beforePerfCount, ok := timeoutPerfRequestCount(beforePerf)
	require.True(t, ok)
	writeRawJSONArtifact(t, caseDir, "timeout.debug_perf.before.json", beforePerf)

	timeoutClientID := fmt.Sprintf("cgqa-safe-timeout-%d", time.Now().UTC().UnixNano())
	latencyMS := 1800
	harness.PatchMockOpenAIFault(t, client, eps.MockOpenAIHTTP, mockopenai.FaultPatch{LatencyMs: &latencyMS})
	shortClient := &http.Client{Timeout: 350 * time.Millisecond}
	timeoutBody := chatBody(t, model, "CGQA safe correlation post-timeout lookup")
	t.Logf("G-CORR-SAFE stage=timeout dispatch correlation=%s latency_ms=%d client_timeout_ms=350", timeoutClientID, latencyMS)
	timeoutTransport := postIdentityChat(eps.GatewayHTTP, adminKey, timeoutClientID, timeoutBody, shortClient)
	t.Logf("G-CORR-SAFE stage=timeout complete status=%d timeout=%v err=%v response_request_id=%q", timeoutTransport.Status, isTimeout(timeoutTransport.Err), timeoutTransport.Err, timeoutTransport.ResponseRequestID)
	timeoutObserved := isTimeout(timeoutTransport.Err)
	writeJSONArtifact(t, caseDir, "timeout.transport.json", map[string]any{
		"client_correlation_id": timeoutClientID,
		"response_request_id": timeoutTransport.ResponseRequestID,
		"timeout_observed": timeoutObserved,
		"error": errorString(timeoutTransport.Err),
	})

	afterPerf, _, timeoutCompletionObserved := waitForPerfRequestAfter(
		client, eps.GatewayHTTP, adminKey, escrowID, beforePerfCount, 15*time.Second,
	)
	writeRawJSONArtifact(t, caseDir, "timeout.debug_perf.after.json", afterPerf)

	timeoutCorr := requireCorrelationLookup(t, client, eps.GatewayHTTP, adminKey, escrowID, timeoutClientID, 1, 8*time.Second)
	writeJSONArtifact(t, caseDir, "timeout-correlation.lookup.json", timeoutCorr)
	timeoutMatchIDs := correlationInternalIDs(timeoutCorr)
	timeoutAccountingResolved := false
	if len(timeoutMatchIDs) == 1 {
		acctTimeout, resolved := requireInternalAccounting(t, client, eps.GatewayHTTP, adminKey, escrowID, timeoutMatchIDs[0], 8*time.Second)
		timeoutAccountingResolved = resolved
		writeJSONArtifact(t, caseDir, "timeout.accounting.json", acctTimeout)
	}

	allReuseMatches := len(matchIDs) == 2 && containsSameStrings(matchIDs, internalIDs)
	verdict := "FAIL"
	notes := "non-collapsing correlation proof did not satisfy every regression invariant"
	if canonicalDistinct && allReuseMatches && okA && okB && winnerDistinct && timeoutObserved && timeoutCompletionObserved && len(timeoutMatchIDs) == 1 && timeoutAccountingResolved {
		verdict = "PASS"
		notes = "caller correlation remained separate from unique canonical request identities; repeated correlation mapped to two independent accounting records and timeout correlation recovered the completed internal request"
	}

	evidence := cgqaSafeCorrelationEvidence{
		SchemaVersion:                       "gonka-safe-correlation-v0.1",
		CaseID:                              "G-CORR-SAFE",
		UpstreamRevision:                    cgqaUpstreamRevision,
		Environment:                         "gonka-local-devshard-testenv",
		ReusedClientCorrelationID:           reusedClientID,
		InternalRequestIDs:                  internalIDs,
		CorrelationMatchIDs:                 matchIDs,
		CanonicalIDsDistinct:                canonicalDistinct,
		AccountingResolvedForEachInternalID: okA && okB && allReuseMatches,
		WinnerNonces:                        winnerNonces,
		WinnerNoncesDistinct:                winnerDistinct,
		TimeoutClientCorrelationID:          timeoutClientID,
		TimeoutObserved:                     timeoutObserved,
		TimeoutCompletionObserved:           timeoutCompletionObserved,
		TimeoutCorrelationMatchIDs:          timeoutMatchIDs,
		TimeoutAccountingResolved:           timeoutAccountingResolved,
		Verdict:                             verdict,
		Notes:                               notes,
	}
	writeJSONArtifact(t, caseDir, "reconciliation.json", evidence)
	t.Logf("G-CORR-SAFE verdict=%s distinct_ids=%v reused_matches=%v timeout=%v timeout_matches=%v", verdict, canonicalDistinct, matchIDs, timeoutObserved, timeoutMatchIDs)
}

func requireCorrelationLookup(t *testing.T, client *http.Client, gatewayURL, adminKey, escrowID, clientID string, minMatches int, timeout time.Duration) cgqaCorrelationLookup {
	t.Helper()
	endpoint := strings.TrimRight(gatewayURL, "/") + "/devshard/" + url.PathEscape(escrowID) + "/v1/request-correlations/" + url.PathEscape(clientID)
	deadline := time.Now().Add(timeout)
	var last cgqaCorrelationLookup
	for time.Now().Before(deadline) {
		raw, status, err := getBytes(client, endpoint, adminKey)
		if err == nil && status >= http.StatusOK && status < http.StatusMultipleChoices && json.Unmarshal(raw, &last) == nil && last.MatchCount >= minMatches {
			return last
		}
		time.Sleep(200 * time.Millisecond)
	}
	t.Fatalf("correlation lookup %s did not reach %d matches; last=%+v", clientID, minMatches, last)
	return last
}

func requireInternalAccounting(t *testing.T, client *http.Client, gatewayURL, adminKey, escrowID, internalID string, timeout time.Duration) (cgqaAccountingView, bool) {
	t.Helper()
	probe := waitAccountingAddressProbe(client, gatewayURL, adminKey, escrowID, internalID, timeout)
	if !probe.Resolved {
		return cgqaAccountingView{}, false
	}
	var out cgqaAccountingView
	if err := json.Unmarshal(probe.Body, &out); err != nil {
		return cgqaAccountingView{}, false
	}
	return out, out.RequestID == internalID && out.WinnerNonce != 0
}

func correlationInternalIDs(lookup cgqaCorrelationLookup) []string {
	ids := make([]string, 0, len(lookup.Matches))
	for _, m := range lookup.Matches {
		if strings.TrimSpace(m.InternalRequestID) != "" {
			ids = append(ids, m.InternalRequestID)
		}
	}
	sort.Strings(ids)
	return ids
}

func containsSameStrings(a, b []string) bool {
	if len(a) != len(b) {
		return false
	}
	aa := append([]string(nil), a...)
	bb := append([]string(nil), b...)
	sort.Strings(aa)
	sort.Strings(bb)
	for i := range aa {
		if aa[i] != bb[i] {
			return false
		}
	}
	return true
}

func safeCorrelationCaseDir(t *testing.T) string {
	t.Helper()
	root := strings.TrimSpace(os.Getenv("CGQA_EVIDENCE_DIR"))
	if root == "" {
		root = filepath.Join(t.TempDir(), "cgqa-evidence")
	}
	dir := filepath.Join(root, "G-CORR-SAFE")
	require.NoError(t, os.MkdirAll(dir, 0o755))
	return dir
}
