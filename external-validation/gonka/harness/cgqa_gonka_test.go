//go:build testenvci

package citest

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
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

const cgqaUpstreamRevision = "f040d0a5b5ef207a0c431894c9f9e2608f9d3073"

type cgqaTransportDisposition struct {
	AttemptID      string `json:"attempt_id"`
	RequestID      string `json:"request_id"`
	HTTPStatus     *int   `json:"http_status"`
	ClientExitCode *int   `json:"client_exit_code"`
	Outcome        string `json:"outcome"`
	StartedAt      string `json:"started_at,omitempty"`
	EndedAt        string `json:"ended_at,omitempty"`
	Notes          string `json:"notes,omitempty"`
}

type cgqaAccountingAttempt struct {
	RequestID      string `json:"request_id,omitempty"`
	EscrowID       string `json:"escrow_id,omitempty"`
	Nonce          uint64 `json:"nonce"`
	HostIdx        *int   `json:"host_idx,omitempty"`
	ParticipantKey string `json:"participant_key,omitempty"`
	Probe          bool   `json:"probe"`
	Winner         bool   `json:"winner"`
	ActualCost     uint64 `json:"actual_cost"`
}

type cgqaAccounting struct {
	RequestID           string                  `json:"request_id"`
	EscrowID            string                  `json:"escrow_id"`
	Outcome             string                  `json:"outcome"`
	Decision            string                  `json:"decision"`
	WinnerNonce         uint64                  `json:"winner_nonce"`
	CachedFromRequestID string                  `json:"cached_from_request_id"`
	CachedFromEscrowID  string                  `json:"cached_from_escrow_id"`
	Attempts            []cgqaAccountingAttempt `json:"attempts"`
	Cost                struct {
		WinnerActualCost        uint64 `json:"winner_actual_cost"`
		OtherAttemptsActualCost uint64 `json:"other_attempts_actual_cost"`
		AllAttemptsActualCost   uint64 `json:"all_attempts_actual_cost"`
	} `json:"cost"`
}

type cgqaCost struct {
	WinnerActualCost        uint64 `json:"winner_actual_cost"`
	OtherAttemptsActualCost uint64 `json:"other_attempts_actual_cost"`
	AllAttemptsActualCost   uint64 `json:"all_attempts_actual_cost"`
	ArithmeticReconciles    bool   `json:"arithmetic_reconciles"`
}

type cgqaEvidence struct {
	SchemaVersion           string                     `json:"schema_version"`
	CaseID                  string                     `json:"case_id"`
	RunID                   string                     `json:"run_id"`
	UpstreamRevision        string                     `json:"upstream_revision"`
	Environment             string                     `json:"environment"`
	LogicalOperationID      string                     `json:"logical_operation_id"`
	TransportRequestIDs     []string                   `json:"transport_request_ids"`
	TransportDispositions   []cgqaTransportDisposition `json:"transport_dispositions"`
	EscrowIDs               []string                   `json:"escrow_ids,omitempty"`
	ObservedExecutionNonces []uint64                   `json:"observed_execution_nonces"`
	Attempts                []cgqaAccountingAttempt    `json:"attempts,omitempty"`
	Cost                    cgqaCost                   `json:"cost"`
	SettlementRefs          []string                   `json:"settlement_refs,omitempty"`
	UnexplainedEffects      []string                   `json:"unexplained_effects"`
	Verdict                 string                     `json:"verdict"`
	PrivateHypothesisID     *string                    `json:"private_hypothesis_id"`
	Notes                   string                     `json:"notes,omitempty"`
}

type cgqaRunMetadata struct {
	CaseID             string `json:"case_id"`
	RunID              string `json:"run_id"`
	LogicalOperationID string `json:"logical_operation_id"`
	UpstreamRevision   string `json:"upstream_revision"`
	Environment        string `json:"environment"`
	Model              string `json:"model"`
	EscrowID           string `json:"escrow_id"`
	StartedAt          string `json:"started_at"`
}

type cgqaAccountingObservation struct {
	Observed  bool            `json:"observed"`
	RequestID string          `json:"request_id"`
	Reason    string          `json:"reason,omitempty"`
	Accounting *cgqaAccounting `json:"accounting,omitempty"`
}

type cgqaHTTPResult struct {
	Status    int
	Body      []byte
	RequestID string
	StartedAt time.Time
	EndedAt   time.Time
	Err       error
}

func TestCGQAGonkaG001G002(t *testing.T) {
	harness.SkipUnlessEnv(t, "TESTENV_CITEST")
	harness.RequireDocker(t)

	stack, cfg, eps := harness.BootAdversarialStack(t, "cgqa-gonka-*")
	client := harness.GatewayChatClient()
	model := config.PrimaryModelID(cfg)
	adminKey := harness.TestenvAdminAPIKey
	escrowID := harness.GetGatewayEscrowID(t, client, eps.GatewayHTTP)
	runID := fmt.Sprintf("cgqa-gonka-%d", time.Now().UTC().UnixNano())
	evidenceRoot := cgqaEvidenceRoot(t)

	t.Cleanup(func() {
		harness.ResetMockOpenAIFault(t, client, eps.MockOpenAIHTTP)
		if t.Failed() {
			harness.DumpComposeLogs(t, stack, "devshardctl", "versiond-0", "versiond-1", "mock-openai")
		}
	})

	runG001(t, client, eps.GatewayHTTP, adminKey, escrowID, model, runID, evidenceRoot)
	runG002A(t, client, eps.GatewayHTTP, eps.MockOpenAIHTTP, adminKey, escrowID, model, runID, evidenceRoot)
	runG002B(t, client, eps.GatewayHTTP, eps.MockOpenAIHTTP, adminKey, escrowID, model, runID, evidenceRoot)
}

func runG001(t *testing.T, client *http.Client, gatewayURL, adminKey, escrowID, model, runID, root string) {
	t.Helper()
	caseID := "G-001"
	logicalID := runID + "-logical-g001"
	requestID := runID + "-g001"
	caseDir := cgqaCaseDir(t, root, caseID)
	body := chatBody(t, model, "CGQA G-001 deterministic control")

	writeJSONArtifact(t, caseDir, "run_metadata.json", runMetadata(caseID, runID+"-g001", logicalID, model, escrowID))
	writeRawJSONArtifact(t, caseDir, "request.redacted.json", body)
	writeRawJSONArtifact(t, caseDir, "gateway_status.before.json", requireGatewayJSON(t, client, gatewayURL, adminKey, "/v1/status"))
	writeRawJSONArtifact(t, caseDir, "devshard_state.before.json", requireDevshardState(t, client, gatewayURL, adminKey, escrowID))

	result := postChat(gatewayURL, adminKey, requestID, body, client)
	require.NoError(t, result.Err)
	require.Equal(t, http.StatusOK, result.Status, "G-001 response: %s", string(result.Body))
	writeRawJSONArtifact(t, caseDir, "response.redacted.json", result.Body)

	acct, rawAccounting, ok := waitAccounting(client, gatewayURL, adminKey, escrowID, requestID, 20*time.Second)
	require.True(t, ok, "G-001 request accounting not observed")
	writeRawJSONArtifact(t, caseDir, "accounting.json", rawAccounting)
	writeRawJSONArtifact(t, caseDir, "gateway_status.after.json", requireGatewayJSON(t, client, gatewayURL, adminKey, "/v1/status"))
	writeRawJSONArtifact(t, caseDir, "devshard_state.after.json", requireDevshardState(t, client, gatewayURL, adminKey, escrowID))

	evidence := buildEvidence(caseID, runID+"-g001", logicalID, []string{requestID}, []cgqaTransportDisposition{
		disposition("transport-1", result, "success", "single control request"),
	}, []cgqaAccounting{acct})
	writeJSONArtifact(t, caseDir, "reconciliation.json", evidence)
	require.Equal(t, "PASS", evidence.Verdict, "G-001 reconciliation: %+v", evidence.UnexplainedEffects)
}

func runG002A(t *testing.T, client *http.Client, gatewayURL, mockOpenAIURL, adminKey, escrowID, model, runID, root string) {
	t.Helper()
	caseID := "G-002A"
	logicalID := runID + "-logical-g002a"
	requestID := runID + "-g002a"
	caseDir := cgqaCaseDir(t, root, caseID)
	body := chatBody(t, model, "CGQA G-002A timeout retry same request id")

	writeJSONArtifact(t, caseDir, "run_metadata.json", runMetadata(caseID, runID+"-g002a", logicalID, model, escrowID))
	writeRawJSONArtifact(t, caseDir, "attempt-1.request.redacted.json", body)
	writeRawJSONArtifact(t, caseDir, "attempt-2.request.redacted.json", body)
	writeRawJSONArtifact(t, caseDir, "gateway_status.before.json", requireGatewayJSON(t, client, gatewayURL, adminKey, "/v1/status"))
	writeRawJSONArtifact(t, caseDir, "devshard_state.before.json", requireDevshardState(t, client, gatewayURL, adminKey, escrowID))

	latencyMs := 1800
	harness.PatchMockOpenAIFault(t, client, mockOpenAIURL, mockopenai.FaultPatch{LatencyMs: &latencyMs})
	shortClient := &http.Client{Timeout: 350 * time.Millisecond}
	first := postChat(gatewayURL, adminKey, requestID, body, shortClient)
	require.True(t, isTimeout(first.Err), "G-002A expected client timeout, got status=%d err=%v body=%s", first.Status, first.Err, string(first.Body))
	firstDisposition := disposition("transport-1", first, "client_timeout_ambiguous", "request dispatched; client timed out while deterministic downstream latency was injected")
	writeJSONArtifact(t, caseDir, "attempt-1.transport-outcome.json", firstDisposition)

	acctBeforeRetry, rawBeforeRetry, seenBeforeRetry := getAccounting(client, gatewayURL, adminKey, escrowID, requestID)
	writeAccountingObservation(t, caseDir, "attempt-1.accounting.json", requestID, acctBeforeRetry, rawBeforeRetry, seenBeforeRetry, "not observed at the pre-retry snapshot")
	writeRawJSONArtifact(t, caseDir, "gateway_status.after-attempt-1.json", requireGatewayJSON(t, client, gatewayURL, adminKey, "/v1/status"))

	zero := 0
	harness.PatchMockOpenAIFault(t, client, mockOpenAIURL, mockopenai.FaultPatch{LatencyMs: &zero})
	second := postChat(gatewayURL, adminKey, requestID, body, client)
	require.NoError(t, second.Err)
	require.Contains(t, []int{http.StatusOK, http.StatusTooManyRequests}, second.Status, "G-002A retry status=%d body=%s", second.Status, string(second.Body))
	outcome2 := "success"
	if second.Status == http.StatusTooManyRequests {
		outcome2 = "rejected_429_in_flight"
	}
	secondDisposition := disposition("transport-2", second, outcome2, "immediate retry reused X-Request-Id")
	writeJSONArtifact(t, caseDir, "attempt-2.transport-outcome.json", secondDisposition)
	if len(second.Body) > 0 {
		writeRawJSONArtifact(t, caseDir, "attempt-2.response.redacted.json", second.Body)
	}

	acctFinal, rawFinal, okFinal := waitAccounting(client, gatewayURL, adminKey, escrowID, requestID, 20*time.Second)
	writeAccountingObservation(t, caseDir, "attempt-2.accounting.json", requestID, acctFinal, rawFinal, okFinal, "no final accounting observed")
	writeRawJSONArtifact(t, caseDir, "gateway_status.after-attempt-2.json", requireGatewayJSON(t, client, gatewayURL, adminKey, "/v1/status"))
	writeRawJSONArtifact(t, caseDir, "devshard_state.after.json", requireDevshardState(t, client, gatewayURL, adminKey, escrowID))

	accounts := []cgqaAccounting{}
	if okFinal {
		accounts = append(accounts, acctFinal)
	}
	evidence := buildEvidence(caseID, runID+"-g002a", logicalID, []string{requestID}, []cgqaTransportDisposition{firstDisposition, secondDisposition}, accounts)
	if !okFinal {
		markInconclusive(&evidence, "final request accounting was not observed after the ambiguity window")
	}
	writeJSONArtifact(t, caseDir, "reconciliation.json", evidence)
	recordG002Verdict(t, evidence)
}

func runG002B(t *testing.T, client *http.Client, gatewayURL, mockOpenAIURL, adminKey, escrowID, model, runID, root string) {
	t.Helper()
	caseID := "G-002B"
	logicalID := runID + "-logical-g002b"
	requestID1 := runID + "-g002b-1"
	requestID2 := runID + "-g002b-2"
	caseDir := cgqaCaseDir(t, root, caseID)
	body := chatBody(t, model, "CGQA G-002B timeout retry fresh transport id")

	writeJSONArtifact(t, caseDir, "run_metadata.json", runMetadata(caseID, runID+"-g002b", logicalID, model, escrowID))
	writeRawJSONArtifact(t, caseDir, "attempt-1.request.redacted.json", body)
	writeRawJSONArtifact(t, caseDir, "attempt-2.request.redacted.json", body)
	writeRawJSONArtifact(t, caseDir, "gateway_status.before.json", requireGatewayJSON(t, client, gatewayURL, adminKey, "/v1/status"))
	writeRawJSONArtifact(t, caseDir, "devshard_state.before.json", requireDevshardState(t, client, gatewayURL, adminKey, escrowID))

	latencyMs := 1800
	harness.PatchMockOpenAIFault(t, client, mockOpenAIURL, mockopenai.FaultPatch{LatencyMs: &latencyMs})
	shortClient := &http.Client{Timeout: 350 * time.Millisecond}
	first := postChat(gatewayURL, adminKey, requestID1, body, shortClient)
	require.True(t, isTimeout(first.Err), "G-002B expected client timeout, got status=%d err=%v body=%s", first.Status, first.Err, string(first.Body))
	firstDisposition := disposition("transport-1", first, "client_timeout_ambiguous", "first transport timed out after dispatch")
	writeJSONArtifact(t, caseDir, "attempt-1.transport-outcome.json", firstDisposition)

	zero := 0
	harness.PatchMockOpenAIFault(t, client, mockOpenAIURL, mockopenai.FaultPatch{LatencyMs: &zero})
	acct1, raw1, ok1 := waitAccounting(client, gatewayURL, adminKey, escrowID, requestID1, 20*time.Second)
	writeAccountingObservation(t, caseDir, "attempt-1.accounting.json", requestID1, acct1, raw1, ok1, "first ambiguous transport has no resolved accounting lineage")
	writeRawJSONArtifact(t, caseDir, "gateway_status.after-attempt-1.json", requireGatewayJSON(t, client, gatewayURL, adminKey, "/v1/status"))

	second := postChat(gatewayURL, adminKey, requestID2, body, client)
	require.NoError(t, second.Err)
	require.Contains(t, []int{http.StatusOK, http.StatusTooManyRequests}, second.Status, "G-002B retry status=%d body=%s", second.Status, string(second.Body))

	acct2, raw2, ok2 := cgqaAccounting{}, []byte(nil), false
	outcome2 := "success"
	if second.Status == http.StatusTooManyRequests {
		outcome2 = "rejected_429_in_flight"
	} else {
		acct2, raw2, ok2 = waitAccounting(client, gatewayURL, adminKey, escrowID, requestID2, 20*time.Second)
		if ok2 && acct2.CachedFromRequestID != "" {
			outcome2 = "cached_or_replayed"
		}
	}
	secondDisposition := disposition("transport-2", second, outcome2, "retry used a fresh X-Request-Id for the same CGQA logical operation")
	writeJSONArtifact(t, caseDir, "attempt-2.transport-outcome.json", secondDisposition)
	if len(second.Body) > 0 {
		writeRawJSONArtifact(t, caseDir, "attempt-2.response.redacted.json", second.Body)
	}
	if second.Status == http.StatusTooManyRequests {
		writeAccountingObservation(t, caseDir, "attempt-2.accounting.json", requestID2, cgqaAccounting{}, nil, false, "explicit 429 rejection; no execution accounting expected for this retry boundary")
	} else {
		writeAccountingObservation(t, caseDir, "attempt-2.accounting.json", requestID2, acct2, raw2, ok2, "successful retry has no resolved accounting lineage")
	}
	writeRawJSONArtifact(t, caseDir, "gateway_status.after-attempt-2.json", requireGatewayJSON(t, client, gatewayURL, adminKey, "/v1/status"))
	writeRawJSONArtifact(t, caseDir, "devshard_state.after.json", requireDevshardState(t, client, gatewayURL, adminKey, escrowID))

	accounts := make([]cgqaAccounting, 0, 2)
	if ok1 {
		accounts = append(accounts, acct1)
	}
	if ok2 {
		accounts = append(accounts, acct2)
	}
	evidence := buildEvidence(caseID, runID+"-g002b", logicalID, []string{requestID1, requestID2}, []cgqaTransportDisposition{firstDisposition, secondDisposition}, accounts)
	if !ok1 {
		markInconclusive(&evidence, "first ambiguous transport lacks resolved accounting lineage")
	}
	if second.Status == http.StatusOK && !ok2 {
		markInconclusive(&evidence, "successful retry lacks resolved accounting lineage")
	}
	writeJSONArtifact(t, caseDir, "reconciliation.json", evidence)
	recordG002Verdict(t, evidence)
}

func runMetadata(caseID, runID, logicalID, model, escrowID string) cgqaRunMetadata {
	return cgqaRunMetadata{
		CaseID:             caseID,
		RunID:              runID,
		LogicalOperationID: logicalID,
		UpstreamRevision:   cgqaUpstreamRevision,
		Environment:        "gonka-local-devshard-testenv",
		Model:              model,
		EscrowID:           escrowID,
		StartedAt:          time.Now().UTC().Format(time.RFC3339Nano),
	}
}

func chatBody(t *testing.T, model, content string) []byte {
	t.Helper()
	body, err := json.Marshal(harness.ChatCompletionRequest{
		Model: model,
		Messages: []harness.ChatMessage{{Role: "user", Content: content}},
		MaxTokens: 32,
	})
	require.NoError(t, err)
	return body
}

func postChat(baseURL, adminKey, requestID string, body []byte, client *http.Client) cgqaHTTPResult {
	if client == nil {
		client = &http.Client{Timeout: 3 * time.Minute}
	}
	result := cgqaHTTPResult{RequestID: requestID, StartedAt: time.Now().UTC()}
	req, err := http.NewRequest(http.MethodPost, strings.TrimRight(baseURL, "/")+"/v1/chat/completions", bytes.NewReader(body))
	if err != nil {
		result.Err = err
		result.EndedAt = time.Now().UTC()
		return result
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-Request-Id", requestID)
	if adminKey != "" {
		req.Header.Set("Authorization", "Bearer "+adminKey)
	}
	resp, err := client.Do(req)
	result.EndedAt = time.Now().UTC()
	if err != nil {
		result.Err = err
		return result
	}
	defer resp.Body.Close()
	result.Status = resp.StatusCode
	result.Body, _ = io.ReadAll(resp.Body)
	if echoed := strings.TrimSpace(resp.Header.Get("X-Request-Id")); echoed != "" {
		result.RequestID = echoed
	}
	return result
}

func disposition(attemptID string, result cgqaHTTPResult, outcome, notes string) cgqaTransportDisposition {
	var status *int
	if result.Status != 0 {
		v := result.Status
		status = &v
	}
	return cgqaTransportDisposition{
		AttemptID:  attemptID,
		RequestID:  result.RequestID,
		HTTPStatus: status,
		Outcome:    outcome,
		StartedAt:  result.StartedAt.Format(time.RFC3339Nano),
		EndedAt:    result.EndedAt.Format(time.RFC3339Nano),
		Notes:      notes,
	}
}

func isTimeout(err error) bool {
	if err == nil {
		return false
	}
	if errors.Is(err, context.DeadlineExceeded) {
		return true
	}
	type timeout interface{ Timeout() bool }
	var te timeout
	return errors.As(err, &te) && te.Timeout()
}

func waitAccounting(client *http.Client, gatewayURL, adminKey, escrowID, requestID string, timeout time.Duration) (cgqaAccounting, []byte, bool) {
	deadline := time.Now().Add(timeout)
	for time.Now().Before(deadline) {
		if acct, raw, ok := getAccounting(client, gatewayURL, adminKey, escrowID, requestID); ok {
			if acct.Outcome != "" || len(acct.Attempts) > 0 {
				return acct, raw, true
			}
		}
		time.Sleep(250 * time.Millisecond)
	}
	return cgqaAccounting{}, nil, false
}

func getAccounting(client *http.Client, gatewayURL, adminKey, escrowID, requestID string) (cgqaAccounting, []byte, bool) {
	base := strings.TrimRight(gatewayURL, "/")
	id := url.PathEscape(requestID)
	paths := []string{
		base + "/v1/requests/" + id,
		base + "/devshard/" + url.PathEscape(escrowID) + "/v1/requests/" + id,
	}
	for _, endpoint := range paths {
		raw, status, err := getBytes(client, endpoint, adminKey)
		if err != nil || status == http.StatusNotFound || status >= 300 {
			continue
		}
		var acct cgqaAccounting
		if json.Unmarshal(raw, &acct) == nil && acct.RequestID != "" {
			return acct, raw, true
		}
	}
	return cgqaAccounting{}, nil, false
}

func requireGatewayJSON(t *testing.T, client *http.Client, gatewayURL, adminKey, path string) []byte {
	t.Helper()
	raw, status, err := getBytes(client, strings.TrimRight(gatewayURL, "/")+path, adminKey)
	require.NoError(t, err)
	require.Less(t, status, 300, "GET %s returned %d: %s", path, status, string(raw))
	require.True(t, json.Valid(raw), "GET %s did not return JSON: %s", path, string(raw))
	return raw
}

func requireDevshardState(t *testing.T, client *http.Client, gatewayURL, adminKey, escrowID string) []byte {
	t.Helper()
	base := strings.TrimRight(gatewayURL, "/")
	paths := []string{
		base + "/devshard/" + url.PathEscape(escrowID) + "/v1/state",
		base + "/v1/state",
	}
	for _, endpoint := range paths {
		raw, status, err := getBytes(client, endpoint, adminKey)
		if err == nil && status < 300 && json.Valid(raw) {
			return raw
		}
	}
	t.Fatalf("unable to capture devshard state for escrow %s", escrowID)
	return nil
}

func getBytes(client *http.Client, endpoint, adminKey string) ([]byte, int, error) {
	req, err := http.NewRequest(http.MethodGet, endpoint, nil)
	if err != nil {
		return nil, 0, err
	}
	if adminKey != "" {
		req.Header.Set("Authorization", "Bearer "+adminKey)
	}
	resp, err := client.Do(req)
	if err != nil {
		return nil, 0, err
	}
	defer resp.Body.Close()
	raw, readErr := io.ReadAll(resp.Body)
	return raw, resp.StatusCode, readErr
}

func buildEvidence(caseID, runID, logicalOperationID string, requestIDs []string, dispositions []cgqaTransportDisposition, accounts []cgqaAccounting) cgqaEvidence {
	e := cgqaEvidence{
		SchemaVersion:         "gonka-reconciliation-v0.1",
		CaseID:                caseID,
		RunID:                 runID,
		UpstreamRevision:      cgqaUpstreamRevision,
		Environment:           "gonka-local-devshard-testenv",
		LogicalOperationID:    logicalOperationID,
		TransportRequestIDs:   uniqueStrings(requestIDs),
		TransportDispositions: dispositions,
		SettlementRefs:        []string{},
		UnexplainedEffects:    []string{},
		Verdict:               "PASS",
		Notes:                 "PASS means transport, execution, and accounting evidence is structurally reconciled; it does not assert HTTP idempotency or automatically classify multiple protocol-permitted executions as a vulnerability.",
	}

	if len(dispositions) == 0 {
		e.UnexplainedEffects = append(e.UnexplainedEffects, "no transport dispositions were recorded")
	}
	dispositionIDs := map[string]bool{}
	for _, d := range dispositions {
		if d.RequestID != "" {
			dispositionIDs[d.RequestID] = true
		}
	}
	for _, requestID := range e.TransportRequestIDs {
		if !dispositionIDs[requestID] {
			e.UnexplainedEffects = append(e.UnexplainedEffects, "transport request lacks disposition: "+requestID)
		}
	}

	seenSources := map[string]bool{}
	seenAttempts := map[string]bool{}
	nonceSet := map[uint64]bool{}
	escrowSet := map[string]bool{}
	for _, acct := range accounts {
		sourceReq := acct.RequestID
		sourceEscrow := acct.EscrowID
		if acct.CachedFromRequestID != "" {
			sourceReq = acct.CachedFromRequestID
			if acct.CachedFromEscrowID != "" {
				sourceEscrow = acct.CachedFromEscrowID
			}
		}
		sourceKey := sourceEscrow + "\x00" + sourceReq
		if seenSources[sourceKey] {
			continue
		}
		seenSources[sourceKey] = true
		if sourceEscrow != "" {
			escrowSet[sourceEscrow] = true
		}

		var derivedWinner, derivedOther uint64
		for _, attempt := range acct.Attempts {
			if attempt.Winner {
				derivedWinner += attempt.ActualCost
			} else {
				derivedOther += attempt.ActualCost
			}
		}
		derivedAll := derivedWinner + derivedOther
		if derivedWinner != acct.Cost.WinnerActualCost {
			e.UnexplainedEffects = append(e.UnexplainedEffects, fmt.Sprintf("winner attempt costs disagree with reported winner cost for source %s: derived=%d reported=%d", sourceReq, derivedWinner, acct.Cost.WinnerActualCost))
		}
		if derivedOther != acct.Cost.OtherAttemptsActualCost {
			e.UnexplainedEffects = append(e.UnexplainedEffects, fmt.Sprintf("non-winner attempt costs disagree with reported other-attempt cost for source %s: derived=%d reported=%d", sourceReq, derivedOther, acct.Cost.OtherAttemptsActualCost))
		}
		if derivedAll != acct.Cost.AllAttemptsActualCost {
			e.UnexplainedEffects = append(e.UnexplainedEffects, fmt.Sprintf("attempt-derived total disagrees with reported all-attempt cost for source %s: derived=%d reported=%d", sourceReq, derivedAll, acct.Cost.AllAttemptsActualCost))
		}
		if acct.Cost.WinnerActualCost+acct.Cost.OtherAttemptsActualCost != acct.Cost.AllAttemptsActualCost {
			e.UnexplainedEffects = append(e.UnexplainedEffects, "reported accounting cost arithmetic does not reconcile for source "+sourceReq)
		}

		e.Cost.WinnerActualCost += acct.Cost.WinnerActualCost
		e.Cost.OtherAttemptsActualCost += acct.Cost.OtherAttemptsActualCost
		e.Cost.AllAttemptsActualCost += acct.Cost.AllAttemptsActualCost
		for _, attempt := range acct.Attempts {
			if attempt.RequestID == "" {
				attempt.RequestID = sourceReq
			}
			if attempt.EscrowID == "" {
				attempt.EscrowID = sourceEscrow
			}
			key := fmt.Sprintf("%s\x00%d", attempt.EscrowID, attempt.Nonce)
			if seenAttempts[key] {
				continue
			}
			seenAttempts[key] = true
			e.Attempts = append(e.Attempts, attempt)
			if attempt.Nonce != 0 {
				nonceSet[attempt.Nonce] = true
			}
		}
	}

	e.Cost.ArithmeticReconciles = e.Cost.WinnerActualCost+e.Cost.OtherAttemptsActualCost == e.Cost.AllAttemptsActualCost
	if !e.Cost.ArithmeticReconciles {
		e.UnexplainedEffects = append(e.UnexplainedEffects, "aggregate accounting cost arithmetic does not reconcile")
	}
	for nonce := range nonceSet {
		e.ObservedExecutionNonces = append(e.ObservedExecutionNonces, nonce)
	}
	sort.Slice(e.ObservedExecutionNonces, func(i, j int) bool { return e.ObservedExecutionNonces[i] < e.ObservedExecutionNonces[j] })
	for escrow := range escrowSet {
		e.EscrowIDs = append(e.EscrowIDs, escrow)
	}
	sort.Strings(e.EscrowIDs)

	if len(accounts) == 0 {
		e.Verdict = "INCONCLUSIVE"
	}
	if len(e.UnexplainedEffects) > 0 {
		e.Verdict = "FAIL"
		hypothesis := "CGQA-GONKA-001"
		e.PrivateHypothesisID = &hypothesis
	}
	return e
}

func markInconclusive(e *cgqaEvidence, reason string) {
	if e == nil || e.Verdict == "FAIL" {
		return
	}
	e.Verdict = "INCONCLUSIVE"
	if e.Notes != "" {
		e.Notes += "; "
	}
	e.Notes += reason
}

func recordG002Verdict(t *testing.T, evidence cgqaEvidence) {
	t.Helper()
	switch evidence.Verdict {
	case "PASS":
		t.Logf("%s reconciliation PASS", evidence.CaseID)
	case "INCONCLUSIVE":
		t.Logf("%s reconciliation INCONCLUSIVE: %s", evidence.CaseID, evidence.Notes)
	case "FAIL":
		t.Errorf("%s reconciliation FAIL: %+v", evidence.CaseID, evidence.UnexplainedEffects)
	default:
		t.Errorf("%s produced unknown verdict %q", evidence.CaseID, evidence.Verdict)
	}
}

func writeAccountingObservation(t *testing.T, dir, name, requestID string, acct cgqaAccounting, raw []byte, observed bool, reason string) {
	t.Helper()
	if observed && len(raw) > 0 {
		writeRawJSONArtifact(t, dir, name, raw)
		return
	}
	obs := cgqaAccountingObservation{Observed: false, RequestID: requestID, Reason: reason}
	if observed {
		obs.Observed = true
		obs.Accounting = &acct
	}
	writeJSONArtifact(t, dir, name, obs)
}

func cgqaEvidenceRoot(t *testing.T) string {
	t.Helper()
	root := strings.TrimSpace(os.Getenv("CGQA_EVIDENCE_DIR"))
	if root == "" {
		root = filepath.Join(t.TempDir(), "cgqa-evidence")
	}
	require.NoError(t, os.MkdirAll(root, 0o755))
	return root
}

func cgqaCaseDir(t *testing.T, root, caseID string) string {
	t.Helper()
	dir := filepath.Join(root, caseID)
	require.NoError(t, os.MkdirAll(dir, 0o755))
	return dir
}

func writeJSONArtifact(t *testing.T, dir, name string, value any) {
	t.Helper()
	data, err := json.MarshalIndent(value, "", "  ")
	require.NoError(t, err)
	data = append(data, '\n')
	path := filepath.Join(dir, name)
	require.NoError(t, os.WriteFile(path, data, 0o644))
	t.Logf("CGQA evidence: %s", path)
}

func writeRawJSONArtifact(t *testing.T, dir, name string, raw []byte) {
	t.Helper()
	require.True(t, json.Valid(raw), "artifact %s is not valid JSON: %s", name, string(raw))
	var value any
	require.NoError(t, json.Unmarshal(raw, &value))
	writeJSONArtifact(t, dir, name, value)
}

func uniqueStrings(in []string) []string {
	seen := map[string]bool{}
	out := make([]string, 0, len(in))
	for _, s := range in {
		if s == "" || seen[s] {
			continue
		}
		seen[s] = true
		out = append(out, s)
	}
	return out
}
