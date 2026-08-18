//go:build testenvci

package citest

import (
	"encoding/json"
	"fmt"
	"net/http"
	"net/url"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"devshard/testenv/citest/harness"
	"devshard/testenv/config"
	"devshard/testenv/mockopenai"
)

type timeoutIdentityEvidence struct {
	SchemaVersion                string  `json:"schema_version"`
	CaseID                       string  `json:"case_id"`
	RunID                        string  `json:"run_id"`
	UpstreamRevision             string  `json:"upstream_revision"`
	Environment                  string  `json:"environment"`
	ClientRequestID              string  `json:"client_request_id"`
	ResponseRequestID            string  `json:"response_request_id"`
	TransportOutcome             string  `json:"transport_outcome"`
	ClientTimeoutObserved        bool    `json:"client_timeout_observed"`
	EscrowID                     string  `json:"escrow_id"`
	AccountingResolvedByClientID bool    `json:"accounting_resolved_by_client_id"`
	StateNonceBefore             *uint64 `json:"state_nonce_before"`
	StateNonceAfter              *uint64 `json:"state_nonce_after"`
	StateProgressed              bool    `json:"state_progressed"`
	PerfRequestCountBefore       int     `json:"perf_request_count_before"`
	PerfRequestCountAfter        int     `json:"perf_request_count_after"`
	PerfRecordAddedAfterTimeout  bool    `json:"perf_record_added_after_timeout"`
	ExecutionObservedAfterTimeout bool   `json:"execution_observed_after_timeout"`
	Verdict                      string  `json:"verdict"`
	PrivateHypothesisID          *string `json:"private_hypothesis_id"`
	Notes                        string  `json:"notes"`
}

// TestCGQAGonkaTimeoutIdentityEvidence isolates the correlation problem that
// exists before a full timeout/retry experiment can be trusted. The pinned
// Gonka checkout is expected to have the CGQA-GONKA-001 background identity
// propagation proof patch applied by CI first. This test changes no criterion
// based on the observed result.
//
// The client supplies a known X-Request-Id, deterministic downstream latency
// forces the client to time out before a response is available, and then we
// require a post-timeout completed perf record before deciding whether the
// known client identity can address request accounting.
func TestCGQAGonkaTimeoutIdentityEvidence(t *testing.T) {
	harness.SkipUnlessEnv(t, "TESTENV_CITEST")
	harness.RequireDocker(t)

	_, cfg, eps := harness.BootAdversarialStack(t, "cgqa-gonka-timeout-id-*")
	client := harness.GatewayChatClient()
	model := config.PrimaryModelID(cfg)
	adminKey := harness.TestenvAdminAPIKey
	escrowID := harness.GetGatewayEscrowID(t, client, eps.GatewayHTTP)
	runID := fmt.Sprintf("cgqa-gonka-timeout-id-%d", time.Now().UTC().UnixNano())
	clientRequestID := runID + "-client"
	caseDir := timeoutIdentityCaseDir(t)

	t.Cleanup(func() {
		harness.ResetMockOpenAIFault(t, client, eps.MockOpenAIHTTP)
	})

	beforeStatus := requireGatewayJSON(t, client, eps.GatewayHTTP, adminKey, "/v1/status")
	beforeState := requireDevshardState(t, client, eps.GatewayHTTP, adminKey, escrowID)
	beforePerf := requireDevshardDebugPerf(t, client, eps.GatewayHTTP, adminKey, escrowID)
	beforePerfCount, ok := timeoutPerfRequestCount(beforePerf)
	if !ok {
		t.Fatalf("G-002-ID: unable to parse baseline debug/perf request count")
	}
	writeRawJSONArtifact(t, caseDir, "gateway_status.before.json", beforeStatus)
	writeRawJSONArtifact(t, caseDir, "devshard_state.before.json", beforeState)
	writeRawJSONArtifact(t, caseDir, "debug_perf.before.json", beforePerf)

	body := chatBody(t, model, "CGQA G-002-ID timeout identity addressability control")
	writeRawJSONArtifact(t, caseDir, "request.redacted.json", body)
	writeJSONArtifact(t, caseDir, "run_metadata.json", map[string]any{
		"case_id": "G-002-ID",
		"run_id": runID,
		"upstream_revision": cgqaUpstreamRevision,
		"environment": "gonka-local-devshard-testenv",
		"model": model,
		"escrow_id": escrowID,
		"client_request_id": clientRequestID,
		"fault_latency_ms": 1800,
		"client_timeout_ms": 350,
		"started_at": time.Now().UTC().Format(time.RFC3339Nano),
	})

	latencyMS := 1800
	harness.PatchMockOpenAIFault(t, client, eps.MockOpenAIHTTP, mockopenai.FaultPatch{LatencyMs: &latencyMS})
	shortClient := &http.Client{Timeout: 350 * time.Millisecond}
	transport := postIdentityChat(eps.GatewayHTTP, adminKey, clientRequestID, body, shortClient)
	clientTimedOut := isTimeout(transport.Err)
	transportOutcome := "unexpected_response"
	if clientTimedOut {
		transportOutcome = "client_timeout_ambiguous"
	} else if transport.Err != nil {
		transportOutcome = "transport_error"
	}
	writeJSONArtifact(t, caseDir, "transport.json", map[string]any{
		"client_request_id": clientRequestID,
		"response_request_id": transport.ResponseRequestID,
		"http_status": transport.Status,
		"outcome": transportOutcome,
		"started_at": transport.StartedAt.Format(time.RFC3339Nano),
		"ended_at": transport.EndedAt.Format(time.RFC3339Nano),
		"error": errorString(transport.Err),
	})

	// A nonce change alone is not enough to claim post-timeout execution.
	// Wait for a new PerfTracker RequestRecord, which is recorded when the
	// request-level race outcome has been finalized.
	afterPerf, afterPerfCount, perfRecordAdded := waitForPerfRequestAfter(
		client, eps.GatewayHTTP, adminKey, escrowID, beforePerfCount, 15*time.Second,
	)
	writeRawJSONArtifact(t, caseDir, "debug_perf.after.json", afterPerf)

	afterStatus := requireGatewayJSON(t, client, eps.GatewayHTTP, adminKey, "/v1/status")
	afterState := requireDevshardState(t, client, eps.GatewayHTTP, adminKey, escrowID)
	writeRawJSONArtifact(t, caseDir, "gateway_status.after.json", afterStatus)
	writeRawJSONArtifact(t, caseDir, "devshard_state.after.json", afterState)

	clientProbe := waitAccountingAddressProbe(client, eps.GatewayHTTP, adminKey, escrowID, clientRequestID, 8*time.Second)
	writeJSONArtifact(t, caseDir, "accounting.client-id.json", clientProbe)

	beforeNonce := identityStateNonce(beforeState)
	afterNonce := identityStateNonce(afterState)
	stateProgressed := beforeNonce != nil && afterNonce != nil && *afterNonce > *beforeNonce
	executionObservedAfterTimeout := clientTimedOut && perfRecordAdded

	verdict := "INCONCLUSIVE"
	notes := "the control did not prove a completed request after the client timeout"
	var hypothesis *string
	switch {
	case executionObservedAfterTimeout && clientProbe.Resolved:
		verdict = "PASS"
		notes = "a completed request was observed after client timeout and its accounting remained addressable by the predeclared client X-Request-Id"
	case executionObservedAfterTimeout && !clientProbe.Resolved:
		verdict = "FAIL"
		notes = "a completed request was observed after client timeout, but accounting was not addressable by the only request identity known to the timed-out client"
		h := "CGQA-GONKA-002"
		hypothesis = &h
	case !clientTimedOut:
		notes = "deterministic fault did not produce the required client timeout"
	}

	evidence := timeoutIdentityEvidence{
		SchemaVersion:                 "gonka-timeout-identity-boundary-v0.1",
		CaseID:                        "G-002-ID",
		RunID:                         runID,
		UpstreamRevision:              cgqaUpstreamRevision,
		Environment:                   "gonka-local-devshard-testenv",
		ClientRequestID:               clientRequestID,
		ResponseRequestID:             transport.ResponseRequestID,
		TransportOutcome:              transportOutcome,
		ClientTimeoutObserved:         clientTimedOut,
		EscrowID:                      escrowID,
		AccountingResolvedByClientID:  clientProbe.Resolved,
		StateNonceBefore:              beforeNonce,
		StateNonceAfter:               afterNonce,
		StateProgressed:               stateProgressed,
		PerfRequestCountBefore:        beforePerfCount,
		PerfRequestCountAfter:         afterPerfCount,
		PerfRecordAddedAfterTimeout:   perfRecordAdded,
		ExecutionObservedAfterTimeout: executionObservedAfterTimeout,
		Verdict:                       verdict,
		PrivateHypothesisID:           hypothesis,
		Notes:                         notes,
	}
	writeJSONArtifact(t, caseDir, "reconciliation.json", evidence)
	t.Logf("G-002-ID evidence collected with verdict=%s timeout=%v perf_added=%v client_accounting=%v", verdict, clientTimedOut, perfRecordAdded, clientProbe.Resolved)
}

func timeoutIdentityCaseDir(t *testing.T) string {
	t.Helper()
	root := strings.TrimSpace(os.Getenv("CGQA_EVIDENCE_DIR"))
	if root == "" {
		root = filepath.Join(t.TempDir(), "cgqa-evidence")
	}
	dir := filepath.Join(root, "G-002-ID")
	if err := os.MkdirAll(dir, 0o755); err != nil {
		t.Fatalf("create G-002-ID evidence dir: %v", err)
	}
	return dir
}

func timeoutPerfRequestCount(raw []byte) (int, bool) {
	var payload struct {
		Requests []json.RawMessage `json:"requests"`
	}
	if err := json.Unmarshal(raw, &payload); err != nil {
		return 0, false
	}
	return len(payload.Requests), true
}

func waitForPerfRequestAfter(client *http.Client, gatewayURL, adminKey, escrowID string, baseline int, timeout time.Duration) ([]byte, int, bool) {
	endpoint := strings.TrimRight(gatewayURL, "/") + "/devshard/" + url.PathEscape(escrowID) + "/v1/debug/perf"
	deadline := time.Now().Add(timeout)
	var last []byte
	lastCount := baseline
	for time.Now().Before(deadline) {
		raw, status, err := getBytes(client, endpoint, adminKey)
		if err == nil && status >= http.StatusOK && status < http.StatusMultipleChoices && json.Valid(raw) {
			last = append(last[:0], raw...)
			if count, ok := timeoutPerfRequestCount(raw); ok {
				lastCount = count
				if count > baseline {
					return raw, count, true
				}
			}
		}
		time.Sleep(250 * time.Millisecond)
	}
	if len(last) == 0 {
		last = []byte(`{"requests":[],"cgqa_observation":"debug/perf unavailable during wait"}`)
	}
	return last, lastCount, false
}

func errorString(err error) string {
	if err == nil {
		return ""
	}
	return err.Error()
}
