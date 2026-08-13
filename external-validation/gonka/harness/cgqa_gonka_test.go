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

	t.Cleanup(func() {
		harness.ResetMockOpenAIFault(t, client, eps.MockOpenAIHTTP)
		if t.Failed() {
			harness.DumpComposeLogs(t, stack, "devshardctl", "versiond-0", "versiond-1", "mock-openai")
		}
	})

	// G-001: clean control.
	g001ReqID := runID + "-g001"
	g001Body := chatBody(t, model, "CGQA G-001 deterministic control")
	g001HTTP := postChat(eps.GatewayHTTP, adminKey, g001ReqID, g001Body, client)
	require.NoError(t, g001HTTP.Err)
	require.Equal(t, http.StatusOK, g001HTTP.Status, "G-001 response: %s", string(g001HTTP.Body))
	g001Accounting, ok := waitAccounting(client, eps.GatewayHTTP, adminKey, escrowID, g001ReqID, 20*time.Second)
	require.True(t, ok, "G-001 request accounting not observed")
	g001 := buildEvidence("G-001", runID+"-g001", "g001-control", []string{g001ReqID}, []cgqaTransportDisposition{
		disposition("transport-1", g001HTTP, "success", "single control request"),
	}, []cgqaAccounting{g001Accounting})
	require.Equal(t, "PASS", g001.Verdict, "G-001 reconciliation: %+v", g001.UnexplainedEffects)
	writeEvidence(t, "G-001.json", g001)

	// G-002A: induce an ambiguous client-side timeout, then immediately retry
	// with the same X-Request-Id. A 429 while the first operation is still in
	// flight is a valid reconciled outcome and must not be mistaken for a
	// second execution.
	latencyMs := 1800
	harness.PatchMockOpenAIFault(t, client, eps.MockOpenAIHTTP, mockopenai.FaultPatch{LatencyMs: &latencyMs})
	g002aReqID := runID + "-g002a"
	g002aBody := chatBody(t, model, "CGQA G-002A timeout retry same request id")
	shortClient := &http.Client{Timeout: 350 * time.Millisecond}
	firstA := postChat(eps.GatewayHTTP, adminKey, g002aReqID, g002aBody, shortClient)
	require.True(t, isTimeout(firstA.Err), "G-002A expected client timeout, got status=%d err=%v body=%s", firstA.Status, firstA.Err, string(firstA.Body))
	zero := 0
	harness.PatchMockOpenAIFault(t, client, eps.MockOpenAIHTTP, mockopenai.FaultPatch{LatencyMs: &zero})
	secondA := postChat(eps.GatewayHTTP, adminKey, g002aReqID, g002aBody, client)
	require.True(t, secondA.Err == nil, "G-002A retry transport failed: %v", secondA.Err)
	require.Contains(t, []int{http.StatusOK, http.StatusTooManyRequests}, secondA.Status, "G-002A retry status=%d body=%s", secondA.Status, string(secondA.Body))
	acctA, okA := waitAccounting(client, eps.GatewayHTTP, adminKey, escrowID, g002aReqID, 20*time.Second)
	accountsA := []cgqaAccounting{}
	if okA {
		accountsA = append(accountsA, acctA)
	}
	outcomeA2 := "success"
	if secondA.Status == http.StatusTooManyRequests {
		outcomeA2 = "rejected_429_in_flight"
	}
	g002a := buildEvidence("G-002A", runID+"-g002a", "g002a-same-request-id", []string{g002aReqID}, []cgqaTransportDisposition{
		disposition("transport-1", firstA, "client_timeout_ambiguous", "request dispatched; client timed out while downstream latency was injected"),
		disposition("transport-2", secondA, outcomeA2, "immediate retry reused X-Request-Id"),
	}, accountsA)
	if !okA {
		g002a.Verdict = "INCONCLUSIVE"
		g002a.Notes += "; no request-accounting record was observable after the ambiguity window"
	}
	writeEvidence(t, "G-002A.json", g002a)

	// G-002B: timeout one transport request, let protocol completion converge,
	// then retry the same semantic body with a fresh transport request id. If
	// upstream returns a cached alias, deduplicate that lineage instead of
	// double-counting the same accounting source.
	harness.PatchMockOpenAIFault(t, client, eps.MockOpenAIHTTP, mockopenai.FaultPatch{LatencyMs: &latencyMs})
	g002bReq1 := runID + "-g002b-1"
	g002bReq2 := runID + "-g002b-2"
	g002bBody := chatBody(t, model, "CGQA G-002B timeout retry fresh transport id")
	firstB := postChat(eps.GatewayHTTP, adminKey, g002bReq1, g002bBody, shortClient)
	require.True(t, isTimeout(firstB.Err), "G-002B expected client timeout, got status=%d err=%v body=%s", firstB.Status, firstB.Err, string(firstB.Body))
	harness.PatchMockOpenAIFault(t, client, eps.MockOpenAIHTTP, mockopenai.FaultPatch{LatencyMs: &zero})
	acctB1, okB1 := waitAccounting(client, eps.GatewayHTTP, adminKey, escrowID, g002bReq1, 20*time.Second)
	secondB := postChat(eps.GatewayHTTP, adminKey, g002bReq2, g002bBody, client)
	require.NoError(t, secondB.Err)
	require.Contains(t, []int{http.StatusOK, http.StatusTooManyRequests}, secondB.Status, "G-002B retry status=%d body=%s", secondB.Status, string(secondB.Body))
	acctB2, okB2 := waitAccounting(client, eps.GatewayHTTP, adminKey, escrowID, g002bReq2, 20*time.Second)
	accountsB := make([]cgqaAccounting, 0, 2)
	if okB1 {
		accountsB = append(accountsB, acctB1)
	}
	if okB2 {
		accountsB = append(accountsB, acctB2)
	}
	outcomeB2 := "success"
	if secondB.Status == http.StatusTooManyRequests {
		outcomeB2 = "rejected_429_in_flight"
	} else if okB2 && acctB2.CachedFromRequestID != "" {
		outcomeB2 = "cached_or_replayed"
	}
	g002b := buildEvidence("G-002B", runID+"-g002b", "g002b-fresh-transport-id", []string{g002bReq1, g002bReq2}, []cgqaTransportDisposition{
		disposition("transport-1", firstB, "client_timeout_ambiguous", "first transport timed out after dispatch"),
		disposition("transport-2", secondB, outcomeB2, "retry used a fresh X-Request-Id for the same semantic request body"),
	}, accountsB)
	if !okB1 && !okB2 {
		g002b.Verdict = "INCONCLUSIVE"
		g002b.Notes += "; neither transport request produced observable request accounting"
	}
	writeEvidence(t, "G-002B.json", g002b)

	// Do not convert a reconciled multi-execution observation into a vulnerability
	// claim here. The harness proves evidence quality; semantic triage happens in
	// ContractGraph-QA after the bundle is collected.
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

func waitAccounting(client *http.Client, gatewayURL, adminKey, escrowID, requestID string, timeout time.Duration) (cgqaAccounting, bool) {
	deadline := time.Now().Add(timeout)
	for time.Now().Before(deadline) {
		if acct, ok := getAccounting(client, gatewayURL, adminKey, escrowID, requestID); ok {
			if acct.Outcome != "" || len(acct.Attempts) > 0 {
				return acct, true
			}
		}
		time.Sleep(250 * time.Millisecond)
	}
	return cgqaAccounting{}, false
}

func getAccounting(client *http.Client, gatewayURL, adminKey, escrowID, requestID string) (cgqaAccounting, bool) {
	base := strings.TrimRight(gatewayURL, "/")
	id := url.PathEscape(requestID)
	paths := []string{
		base + "/v1/requests/" + id,
		base + "/devshard/" + url.PathEscape(escrowID) + "/v1/requests/" + id,
	}
	for _, endpoint := range paths {
		req, err := http.NewRequest(http.MethodGet, endpoint, nil)
		if err != nil {
			continue
		}
		if adminKey != "" {
			req.Header.Set("Authorization", "Bearer "+adminKey)
		}
		resp, err := client.Do(req)
		if err != nil {
			continue
		}
		body, _ := io.ReadAll(resp.Body)
		resp.Body.Close()
		if resp.StatusCode == http.StatusNotFound {
			continue
		}
		if resp.StatusCode >= 300 {
			continue
		}
		var acct cgqaAccounting
		if json.Unmarshal(body, &acct) == nil && acct.RequestID != "" {
			return acct, true
		}
	}
	return cgqaAccounting{}, false
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
		Notes:                 "PASS means observed execution/accounting effects are structurally reconciled; it does not assert HTTP idempotency or declare multiple protocol-permitted executions a vulnerability.",
	}

	// Cached accounting aliases point at the same source lineage. Count each
	// source once so a cache replay does not look like a second financial effect.
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
		if acct.Cost.WinnerActualCost+acct.Cost.OtherAttemptsActualCost != acct.Cost.AllAttemptsActualCost {
			e.UnexplainedEffects = append(e.UnexplainedEffects, "accounting cost arithmetic does not reconcile for source "+sourceReq)
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
			nonceSet[attempt.Nonce] = true
		}
	}
	e.Cost.ArithmeticReconciles = e.Cost.WinnerActualCost+e.Cost.OtherAttemptsActualCost == e.Cost.AllAttemptsActualCost
	if !e.Cost.ArithmeticReconciles {
		e.UnexplainedEffects = append(e.UnexplainedEffects, "aggregate accounting cost arithmetic does not reconcile")
	}
	for nonce := range nonceSet {
		if nonce != 0 {
			e.ObservedExecutionNonces = append(e.ObservedExecutionNonces, nonce)
		}
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
	}
	return e
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

func writeEvidence(t *testing.T, name string, evidence cgqaEvidence) {
	t.Helper()
	dir := strings.TrimSpace(os.Getenv("CGQA_EVIDENCE_DIR"))
	if dir == "" {
		dir = filepath.Join(t.TempDir(), "cgqa-evidence")
	}
	require.NoError(t, os.MkdirAll(dir, 0o755))
	data, err := json.MarshalIndent(evidence, "", "  ")
	require.NoError(t, err)
	data = append(data, '\n')
	require.NoError(t, os.WriteFile(filepath.Join(dir, name), data, 0o644))
	t.Logf("CGQA evidence: %s", filepath.Join(dir, name))
}
