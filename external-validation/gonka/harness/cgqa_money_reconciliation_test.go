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
	"strconv"
	"strings"
	"testing"
	"time"

	"devshard/testenv/citest/harness"
	"devshard/testenv/config"
	"devshard/testenv/mockopenai"

	"github.com/stretchr/testify/require"
)

type cgqaMoneyState struct {
	Session struct {
		Balance uint64 `json:"balance"`
	} `json:"session"`
	HostStats map[string]struct {
		Cost uint64 `json:"cost"`
	} `json:"host_stats"`
}

type cgqaMoneyInference struct {
	Status       string `json:"status"`
	ReservedCost uint64 `json:"reserved_cost"`
	ActualCost   uint64 `json:"actual_cost"`
}

type cgqaMoneyInferenceDump struct {
	TotalInferences int                           `json:"total_inferences"`
	Inferences      map[string]cgqaMoneyInference `json:"inferences"`
}

type cgqaMoneyRequestEvidence struct {
	InternalRequestID        string                  `json:"internal_request_id"`
	WinnerNonce              uint64                  `json:"winner_nonce"`
	AttemptNonces            []uint64                `json:"attempt_nonces"`
	AttemptActualCost        uint64                  `json:"attempt_actual_cost"`
	ReportedAllAttemptsCost  uint64                  `json:"reported_all_attempts_actual_cost"`
	ReportedWinnerCost       uint64                  `json:"reported_winner_actual_cost"`
	ReportedOtherAttemptCost uint64                  `json:"reported_other_attempts_actual_cost"`
	ArithmeticReconciles     bool                    `json:"arithmetic_reconciles"`
	Attempts                 []cgqaAccountingAttempt `json:"attempts"`
}

type cgqaMoneyEvidence struct {
	SchemaVersion               string                     `json:"schema_version"`
	CaseID                      string                     `json:"case_id"`
	LogicalOperationID          string                     `json:"logical_operation_id"`
	UpstreamRevision            string                     `json:"upstream_revision"`
	Environment                 string                     `json:"environment"`
	ClientCorrelationID         string                     `json:"client_correlation_id"`
	InternalRequestIDs          []string                   `json:"internal_request_ids"`
	TimeoutObserved             bool                       `json:"timeout_observed"`
	FirstCompletionObserved     bool                       `json:"first_completion_observed"`
	RetryHTTPStatus             int                        `json:"retry_http_status"`
	Requests                    []cgqaMoneyRequestEvidence `json:"requests"`
	AttemptNonces               []uint64                   `json:"attempt_nonces"`
	AttemptNoncesUnique         bool                       `json:"attempt_nonces_unique"`
	TerminalInferenceStatuses   map[string]string          `json:"terminal_inference_statuses"`
	AccountingAttemptCost       uint64                     `json:"accounting_attempt_cost"`
	AccountingReportedCost      uint64                     `json:"accounting_reported_cost"`
	InferenceActualCost         uint64                     `json:"inference_actual_cost"`
	HostCostBefore              uint64                     `json:"host_cost_before"`
	HostCostAfter               uint64                     `json:"host_cost_after"`
	HostCostDelta               uint64                     `json:"host_cost_delta"`
	BalanceBefore               uint64                     `json:"balance_before"`
	BalanceAfter                uint64                     `json:"balance_after"`
	BalanceDebit                uint64                     `json:"balance_debit"`
	FourWayReconciles           bool                       `json:"four_way_reconciles"`
	UnexplainedFinancialEffects []string                   `json:"unexplained_financial_effects"`
	Verdict                     string                     `json:"verdict"`
	Notes                       string                     `json:"notes"`
}

func TestCGQAGonkaMoneyReconciliation(t *testing.T) {
	harness.SkipUnlessEnv(t, "TESTENV_CITEST")
	harness.RequireDocker(t)

	stack, cfg, eps := harness.BootAdversarialStack(t, "cgqa-gonka-money-*")
	client := harness.GatewayChatClient()
	model := config.PrimaryModelID(cfg)
	adminKey := harness.TestenvAdminAPIKey
	escrowID := harness.GetGatewayEscrowID(t, client, eps.GatewayHTTP)
	root := moneyEvidenceRoot(t)

	t.Cleanup(func() {
		harness.ResetMockOpenAIFault(t, client, eps.MockOpenAIHTTP)
		if t.Failed() {
			harness.DumpComposeLogs(t, stack, "devshardctl", "versiond-0", "versiond-1", "mock-openai")
		}
	})

	stamp := time.Now().UTC().UnixNano()
	logicalID := fmt.Sprintf("cgqa-g004-logical-%d", stamp)
	clientCorrelationID := fmt.Sprintf("cgqa-g004-correlation-%d", stamp)
	body := chatBody(t, model, "CGQA G-004 causal money reconciliation after ambiguous timeout retry")

	beforeStateRaw := requireDevshardState(t, client, eps.GatewayHTTP, adminKey, escrowID)
	beforeState := decodeMoneyState(t, beforeStateRaw)
	beforeInferences := requireMoneyInferenceDump(t, client, eps.GatewayHTTP, adminKey, escrowID)
	writeRawJSONArtifact(t, root, "devshard_state.before.json", beforeStateRaw)
	writeJSONArtifact(t, root, "inferences.before.json", beforeInferences)
	writeRawJSONArtifact(t, root, "request.redacted.json", body)

	beforePerf := requireDevshardDebugPerf(t, client, eps.GatewayHTTP, adminKey, escrowID)
	beforePerfCount, ok := timeoutPerfRequestCount(beforePerf)
	require.True(t, ok, "G-004 could not establish request-count control")

	latencyMS := 1800
	harness.PatchMockOpenAIFault(t, client, eps.MockOpenAIHTTP, mockopenai.FaultPatch{LatencyMs: &latencyMS})
	shortClient := &http.Client{Timeout: 350 * time.Millisecond}
	first := postIdentityChat(eps.GatewayHTTP, adminKey, clientCorrelationID, body, shortClient)
	timeoutObserved := isTimeout(first.Err)
	writeJSONArtifact(t, root, "attempt-1.transport.json", map[string]any{
		"client_correlation_id": clientCorrelationID,
		"timeout_observed":      timeoutObserved,
		"response_request_id":   first.ResponseRequestID,
		"error":                 errorString(first.Err),
	})

	_, _, firstCompletion := waitForPerfRequestAfter(client, eps.GatewayHTTP, adminKey, escrowID, beforePerfCount, 15*time.Second)
	firstLookup := requireCorrelationLookup(t, client, eps.GatewayHTTP, adminKey, escrowID, clientCorrelationID, 1, 8*time.Second)
	firstIDs := correlationInternalIDs(firstLookup)

	zero := 0
	harness.PatchMockOpenAIFault(t, client, eps.MockOpenAIHTTP, mockopenai.FaultPatch{LatencyMs: &zero})
	second := postIdentityChat(eps.GatewayHTTP, adminKey, clientCorrelationID, body, client)
	require.NoError(t, second.Err)
	require.GreaterOrEqual(t, second.Status, http.StatusOK)
	require.Less(t, second.Status, http.StatusMultipleChoices)
	writeJSONArtifact(t, root, "attempt-2.transport.json", map[string]any{
		"client_correlation_id": clientCorrelationID,
		"http_status":           second.Status,
		"response_request_id":   second.ResponseRequestID,
	})

	lookup := requireCorrelationLookup(t, client, eps.GatewayHTTP, adminKey, escrowID, clientCorrelationID, 2, 8*time.Second)
	internalIDs := correlationInternalIDs(lookup)
	writeJSONArtifact(t, root, "correlation.lookup.json", lookup)

	unexplained := []string{}
	if !timeoutObserved {
		unexplained = append(unexplained, "first transport did not produce the expected ambiguous client timeout")
	}
	if !firstCompletion {
		unexplained = append(unexplained, "timed-out request did not produce a completion witness before retry")
	}
	if len(firstIDs) != 1 {
		unexplained = append(unexplained, "first correlation did not resolve exactly one internal request before retry")
	}
	if len(internalIDs) != 2 || internalIDs[0] == internalIDs[1] {
		unexplained = append(unexplained, "timeout/retry did not retain two distinct canonical internal request IDs")
	}

	requests := make([]cgqaMoneyRequestEvidence, 0, len(internalIDs))
	allAttemptNonces := []uint64{}
	accountingAttemptCost := uint64(0)
	accountingReportedCost := uint64(0)
	for _, internalID := range internalIDs {
		acct, resolved := requireFullInternalAccounting(t, client, eps.GatewayHTTP, adminKey, escrowID, internalID, 8*time.Second)
		if !resolved {
			unexplained = append(unexplained, "request accounting unresolved for "+internalID)
			continue
		}
		writeJSONArtifact(t, root, "accounting."+sanitizeMoneyName(internalID)+".json", acct)

		attemptSum := uint64(0)
		attemptNonces := make([]uint64, 0, len(acct.Attempts))
		for _, attempt := range acct.Attempts {
			attemptSum += attempt.ActualCost
			attemptNonces = append(attemptNonces, attempt.Nonce)
			allAttemptNonces = append(allAttemptNonces, attempt.Nonce)
		}
		sort.Slice(attemptNonces, func(i, j int) bool { return attemptNonces[i] < attemptNonces[j] })
		arithmeticOK := attemptSum == acct.Cost.AllAttemptsActualCost &&
			acct.Cost.WinnerActualCost+acct.Cost.OtherAttemptsActualCost == acct.Cost.AllAttemptsActualCost
		if !arithmeticOK {
			unexplained = append(unexplained, "request accounting aggregate arithmetic mismatch for "+internalID)
		}
		accountingAttemptCost += attemptSum
		accountingReportedCost += acct.Cost.AllAttemptsActualCost
		requests = append(requests, cgqaMoneyRequestEvidence{
			InternalRequestID:        internalID,
			WinnerNonce:              acct.WinnerNonce,
			AttemptNonces:            attemptNonces,
			AttemptActualCost:        attemptSum,
			ReportedAllAttemptsCost:  acct.Cost.AllAttemptsActualCost,
			ReportedWinnerCost:       acct.Cost.WinnerActualCost,
			ReportedOtherAttemptCost: acct.Cost.OtherAttemptsActualCost,
			ArithmeticReconciles:     arithmeticOK,
			Attempts:                 acct.Attempts,
		})
	}

	sort.Slice(allAttemptNonces, func(i, j int) bool { return allAttemptNonces[i] < allAttemptNonces[j] })
	uniqueNonces := uniqueMoneyNonces(allAttemptNonces)
	attemptNoncesUnique := len(uniqueNonces) == len(allAttemptNonces) && len(uniqueNonces) > 0
	if !attemptNoncesUnique {
		unexplained = append(unexplained, "an execution nonce appeared in more than one request-accounting lineage or no nonce was observed")
	}

	afterInferences, terminalStatuses, inferenceActualCost, terminalOK := waitMoneyTerminalInferences(
		t, client, eps.GatewayHTTP, adminKey, escrowID, uniqueNonces, 20*time.Second,
	)
	writeJSONArtifact(t, root, "inferences.after.json", afterInferences)
	if !terminalOK {
		unexplained = append(unexplained, "not every accounting attempt reached a v0.1 terminal state (finished or timed_out)")
	}
	for nonce, status := range terminalStatuses {
		if status == "challenged" || status == "invalidated" {
			unexplained = append(unexplained, fmt.Sprintf("nonce %s entered dispute semantics excluded from G-004 v0.1: %s", nonce, status))
		}
	}

	afterStateRaw := requireDevshardState(t, client, eps.GatewayHTTP, adminKey, escrowID)
	afterState := decodeMoneyState(t, afterStateRaw)
	writeRawJSONArtifact(t, root, "devshard_state.after.json", afterStateRaw)

	hostBefore := sumMoneyHostCost(beforeState)
	hostAfter := sumMoneyHostCost(afterState)
	hostDelta, hostDeltaOK := moneyDecrease(hostAfter, hostBefore)
	if !hostDeltaOK {
		unexplained = append(unexplained, "aggregate host cost decreased across the isolated G-004 window")
	}
	balanceDebit, balanceOK := moneyDecrease(beforeState.Session.Balance, afterState.Session.Balance)
	if !balanceOK {
		unexplained = append(unexplained, "escrow balance increased across the isolated no-dispute G-004 window")
	}

	fourWay := accountingAttemptCost == accountingReportedCost &&
		accountingAttemptCost == inferenceActualCost &&
		accountingAttemptCost == hostDelta &&
		accountingAttemptCost == balanceDebit
	if !fourWay {
		unexplained = append(unexplained, fmt.Sprintf(
			"four-way financial mismatch: attempt=%d reported=%d inference=%d host_delta=%d balance_debit=%d",
			accountingAttemptCost, accountingReportedCost, inferenceActualCost, hostDelta, balanceDebit,
		))
	}

	verdict := "PASS"
	if len(unexplained) > 0 {
		verdict = "FAIL"
	}
	evidence := cgqaMoneyEvidence{
		SchemaVersion:               "gonka-causal-money-reconciliation-v0.1",
		CaseID:                      "G-004",
		LogicalOperationID:          logicalID,
		UpstreamRevision:            cgqaUpstreamRevision,
		Environment:                 "gonka-local-devshard-testenv",
		ClientCorrelationID:         clientCorrelationID,
		InternalRequestIDs:          internalIDs,
		TimeoutObserved:             timeoutObserved,
		FirstCompletionObserved:     firstCompletion,
		RetryHTTPStatus:             second.Status,
		Requests:                    requests,
		AttemptNonces:               uniqueNonces,
		AttemptNoncesUnique:         attemptNoncesUnique,
		TerminalInferenceStatuses:   terminalStatuses,
		AccountingAttemptCost:       accountingAttemptCost,
		AccountingReportedCost:      accountingReportedCost,
		InferenceActualCost:         inferenceActualCost,
		HostCostBefore:              hostBefore,
		HostCostAfter:               hostAfter,
		HostCostDelta:               hostDelta,
		BalanceBefore:               beforeState.Session.Balance,
		BalanceAfter:                afterState.Session.Balance,
		BalanceDebit:                balanceDebit,
		FourWayReconciles:           fourWay,
		UnexplainedFinancialEffects: unexplained,
		Verdict:                     verdict,
		Notes:                       "PASS proves causal financial reconciliation for an isolated timeout/retry window without challenge/invalidation semantics; it does not claim retry idempotency or mainnet settlement correctness",
	}
	writeJSONArtifact(t, root, "reconciliation.json", evidence)
	t.Logf("G-004 verdict=%s attempt=%d reported=%d inference=%d host_delta=%d balance_debit=%d", verdict, accountingAttemptCost, accountingReportedCost, inferenceActualCost, hostDelta, balanceDebit)
	if verdict != "PASS" {
		t.Errorf("G-004 causal money reconciliation FAIL: %v", unexplained)
	}
}

func decodeMoneyState(t *testing.T, raw []byte) cgqaMoneyState {
	t.Helper()
	var state cgqaMoneyState
	require.NoError(t, json.Unmarshal(raw, &state))
	require.NotNil(t, state.HostStats)
	return state
}

func sumMoneyHostCost(state cgqaMoneyState) uint64 {
	var total uint64
	for _, host := range state.HostStats {
		total += host.Cost
	}
	return total
}

func requireMoneyInferenceDump(t *testing.T, client *http.Client, gatewayURL, adminKey, escrowID string) cgqaMoneyInferenceDump {
	t.Helper()
	endpoint := strings.TrimRight(gatewayURL, "/") + "/devshard/" + url.PathEscape(escrowID) + "/v1/debug/inferences"
	raw, status, err := getBytes(client, endpoint, adminKey)
	require.NoError(t, err)
	require.GreaterOrEqual(t, status, http.StatusOK)
	require.Less(t, status, http.StatusMultipleChoices)
	var dump cgqaMoneyInferenceDump
	require.NoError(t, json.Unmarshal(raw, &dump))
	if dump.Inferences == nil {
		dump.Inferences = map[string]cgqaMoneyInference{}
	}
	return dump
}

func waitMoneyTerminalInferences(t *testing.T, client *http.Client, gatewayURL, adminKey, escrowID string, nonces []uint64, timeout time.Duration) (cgqaMoneyInferenceDump, map[string]string, uint64, bool) {
	t.Helper()
	deadline := time.Now().Add(timeout)
	var last cgqaMoneyInferenceDump
	for time.Now().Before(deadline) {
		last = requireMoneyInferenceDump(t, client, gatewayURL, adminKey, escrowID)
		statuses := map[string]string{}
		cost := uint64(0)
		allTerminal := len(nonces) > 0
		for _, nonce := range nonces {
			key := strconv.FormatUint(nonce, 10)
			rec, ok := last.Inferences[key]
			if !ok {
				allTerminal = false
				continue
			}
			statuses[key] = rec.Status
			cost += rec.ActualCost
			if rec.Status != "finished" && rec.Status != "timed_out" {
				allTerminal = false
			}
		}
		if allTerminal {
			return last, statuses, cost, true
		}
		time.Sleep(250 * time.Millisecond)
	}
	statuses := map[string]string{}
	cost := uint64(0)
	for _, nonce := range nonces {
		key := strconv.FormatUint(nonce, 10)
		if rec, ok := last.Inferences[key]; ok {
			statuses[key] = rec.Status
			cost += rec.ActualCost
		}
	}
	return last, statuses, cost, false
}

func requireFullInternalAccounting(t *testing.T, client *http.Client, gatewayURL, adminKey, escrowID, internalID string, timeout time.Duration) (cgqaAccounting, bool) {
	t.Helper()
	probe := waitAccountingAddressProbe(client, gatewayURL, adminKey, escrowID, internalID, timeout)
	if !probe.Resolved {
		return cgqaAccounting{}, false
	}
	var acct cgqaAccounting
	if err := json.Unmarshal(probe.Body, &acct); err != nil {
		return cgqaAccounting{}, false
	}
	return acct, acct.RequestID == internalID && acct.WinnerNonce != 0 && len(acct.Attempts) > 0
}

func uniqueMoneyNonces(values []uint64) []uint64 {
	out := make([]uint64, 0, len(values))
	var last uint64
	for _, value := range values {
		if value == 0 {
			continue
		}
		if len(out) == 0 || value != last {
			out = append(out, value)
			last = value
		}
	}
	return out
}

// moneyDecrease returns first-second when first >= second. Callers deliberately
// order arguments according to the expected direction: hostAfter-hostBefore for
// monotonic host cost, and balanceBefore-balanceAfter for escrow debit.
func moneyDecrease(first, second uint64) (uint64, bool) {
	if first < second {
		return 0, false
	}
	return first - second, true
}

func sanitizeMoneyName(value string) string {
	value = strings.Map(func(r rune) rune {
		if (r >= 'a' && r <= 'z') || (r >= 'A' && r <= 'Z') || (r >= '0' && r <= '9') || r == '-' || r == '_' {
			return r
		}
		return '_'
	}, value)
	return strings.Trim(value, "_")
}

func moneyEvidenceRoot(t *testing.T) string {
	t.Helper()
	root := strings.TrimSpace(os.Getenv("CGQA_EVIDENCE_DIR"))
	if root == "" {
		root = filepath.Join(t.TempDir(), "cgqa-g004-money")
	}
	require.NoError(t, os.MkdirAll(root, 0o755))
	return root
}
