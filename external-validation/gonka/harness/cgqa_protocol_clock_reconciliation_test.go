//go:build testenvci

package citest

import (
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"testing"
	"time"

	"devshard/testenv/citest/harness"
	"devshard/testenv/config"
	"devshard/testenv/mockopenai"

	"github.com/stretchr/testify/require"
)

type cgqaProtocolClockState struct {
	Session struct {
		Balance uint64 `json:"balance"`
		Fees    uint64 `json:"fees"`
	} `json:"session"`
	HostStats map[string]struct {
		Cost uint64 `json:"cost"`
	} `json:"host_stats"`
}

type cgqaProtocolClockEvidence struct {
	SchemaVersion              string `json:"schema_version"`
	CaseID                     string `json:"case_id"`
	LogicalOperationID         string `json:"logical_operation_id"`
	UpstreamRevision           string `json:"upstream_revision"`
	Environment                string `json:"environment"`
	ClientCorrelationID        string `json:"client_correlation_id"`
	RetryInternalRequestID     string `json:"retry_internal_request_id"`
	RetryWinnerNonce           uint64 `json:"retry_winner_nonce"`
	TimeoutObserved            bool   `json:"timeout_observed"`
	FirstCompletionObserved    bool   `json:"first_completion_observed"`
	RetryHTTPStatus            int    `json:"retry_http_status"`
	PendingBeforeAdvance       bool   `json:"pending_before_advance"`
	PendingReservedCost        uint64 `json:"pending_reserved_cost"`
	AdvanceCorrelationID       string `json:"advance_correlation_id"`
	AdvanceInternalRequestID   string `json:"advance_internal_request_id"`
	AdvanceWinnerNonce         uint64 `json:"advance_winner_nonce"`
	AdvanceHTTPStatus          int    `json:"advance_http_status"`
	ProtocolAdvanceObserved    bool   `json:"protocol_advance_observed"`
	RetryTerminalAfterAdvance  bool   `json:"retry_terminal_after_advance"`
	RetryTerminalStatus        string `json:"retry_terminal_status"`
	RetryActualCost            uint64 `json:"retry_actual_cost"`
	RetrySurplusRelease        uint64 `json:"retry_surplus_release"`
	LiabilityBefore            uint64 `json:"liability_before"`
	LiabilityAfter             uint64 `json:"liability_after"`
	FeesBefore                 uint64 `json:"fees_before"`
	FeesAfter                  uint64 `json:"fees_after"`
	BalanceBefore              uint64 `json:"balance_before"`
	BalanceAfter               uint64 `json:"balance_after"`
	ExpectedBalanceAfter       int64  `json:"expected_balance_after"`
	BalanceReconciles          bool   `json:"balance_reconciles"`
	ActualCostBefore           uint64 `json:"actual_cost_before"`
	ActualCostAfter            uint64 `json:"actual_cost_after"`
	HostCostBefore             uint64 `json:"host_cost_before"`
	HostCostAfter              uint64 `json:"host_cost_after"`
	HostCostReconciles         bool   `json:"host_cost_reconciles"`
	UnexplainedEffects         []string `json:"unexplained_effects"`
	Verdict                    string `json:"verdict"`
	Notes                      string `json:"notes"`
}

func TestCGQAGonkaProtocolClockReconciliation(t *testing.T) {
	harness.SkipUnlessEnv(t, "TESTENV_CITEST")
	harness.RequireDocker(t)

	stack, cfg, eps := harness.BootAdversarialStack(t, "cgqa-gonka-g004q-*")
	client := harness.GatewayChatClient()
	model := config.PrimaryModelID(cfg)
	adminKey := harness.TestenvAdminAPIKey
	escrowID := harness.GetGatewayEscrowID(t, client, eps.GatewayHTTP)
	root := g004qEvidenceRoot(t)

	t.Cleanup(func() {
		harness.ResetMockOpenAIFault(t, client, eps.MockOpenAIHTTP)
		if t.Failed() {
			harness.DumpComposeLogs(t, stack, "devshardctl", "versiond-0", "versiond-1", "mock-openai")
		}
	})

	stamp := time.Now().UTC().UnixNano()
	logicalID := fmt.Sprintf("cgqa-g004q-logical-%d", stamp)
	correlationID := fmt.Sprintf("cgqa-g004q-correlation-%d", stamp)
	body := chatBody(t, model, "CGQA G-004Q protocol-clock retry reconciliation")

	beforePerf := requireDevshardDebugPerf(t, client, eps.GatewayHTTP, adminKey, escrowID)
	beforePerfCount, ok := timeoutPerfRequestCount(beforePerf)
	require.True(t, ok, "G-004Q could not establish request-count control")

	latencyMS := 1800
	harness.PatchMockOpenAIFault(t, client, eps.MockOpenAIHTTP, mockopenai.FaultPatch{LatencyMs: &latencyMS})
	shortClient := &http.Client{Timeout: 350 * time.Millisecond}
	first := postIdentityChat(eps.GatewayHTTP, adminKey, correlationID, body, shortClient)
	timeoutObserved := isTimeout(first.Err)
	writeJSONArtifact(t, root, "attempt-1.transport.json", map[string]any{
		"client_correlation_id": correlationID,
		"timeout_observed": timeoutObserved,
		"response_request_id": first.ResponseRequestID,
		"error": errorString(first.Err),
	})

	_, _, firstCompletionObserved := waitForPerfRequestAfter(client, eps.GatewayHTTP, adminKey, escrowID, beforePerfCount, 15*time.Second)
	firstLookup := requireCorrelationLookup(t, client, eps.GatewayHTTP, adminKey, escrowID, correlationID, 1, 8*time.Second)
	firstIDs := correlationInternalIDs(firstLookup)
	require.Len(t, firstIDs, 1, "G-004Q first correlation must resolve exactly one internal request before retry")

	zero := 0
	harness.PatchMockOpenAIFault(t, client, eps.MockOpenAIHTTP, mockopenai.FaultPatch{LatencyMs: &zero})
	second := postIdentityChat(eps.GatewayHTTP, adminKey, correlationID, body, client)
	require.NoError(t, second.Err)
	require.GreaterOrEqual(t, second.Status, http.StatusOK)
	require.Less(t, second.Status, http.StatusMultipleChoices)
	require.NotEmpty(t, second.ResponseRequestID)
	writeJSONArtifact(t, root, "attempt-2.transport.json", map[string]any{
		"client_correlation_id": correlationID,
		"http_status": second.Status,
		"response_request_id": second.ResponseRequestID,
	})

	lookup := requireCorrelationLookup(t, client, eps.GatewayHTTP, adminKey, escrowID, correlationID, 2, 8*time.Second)
	internalIDs := correlationInternalIDs(lookup)
	writeJSONArtifact(t, root, "correlation.lookup.json", lookup)
	require.Len(t, internalIDs, 2, "G-004Q timeout/retry must retain two internal request IDs")

	retryAccounting, retryAccountingResolved := requireInternalAccounting(t, client, eps.GatewayHTTP, adminKey, escrowID, second.ResponseRequestID, 8*time.Second)
	require.True(t, retryAccountingResolved, "G-004Q retry accounting unresolved")
	retryWinnerNonce := retryAccounting.WinnerNonce
	require.NotZero(t, retryWinnerNonce)
	writeJSONArtifact(t, root, "retry.accounting.json", retryAccounting)

	pendingDump, pendingRetry, pendingBeforeAdvance := waitG004QStatus(t, client, eps.GatewayHTTP, adminKey, escrowID, retryWinnerNonce, "pending", 8*time.Second)
	writeJSONArtifact(t, root, "inferences.pending-before-advance.json", pendingDump)
	pendingStateRaw := requireDevshardState(t, client, eps.GatewayHTTP, adminKey, escrowID)
	pendingState := decodeG004QState(t, pendingStateRaw)
	writeRawJSONArtifact(t, root, "devshard_state.pending-before-advance.json", pendingStateRaw)

	advanceCorrelationID := fmt.Sprintf("cgqa-g004q-advance-%d", stamp)
	advanceBody := chatBody(t, model, "CGQA G-004Q advance protocol clock by one eligible diff")
	advance := postIdentityChat(eps.GatewayHTTP, adminKey, advanceCorrelationID, advanceBody, client)
	require.NoError(t, advance.Err)
	require.GreaterOrEqual(t, advance.Status, http.StatusOK)
	require.Less(t, advance.Status, http.StatusMultipleChoices)
	require.NotEmpty(t, advance.ResponseRequestID)
	writeJSONArtifact(t, root, "advance.transport.json", map[string]any{
		"client_correlation_id": advanceCorrelationID,
		"http_status": advance.Status,
		"response_request_id": advance.ResponseRequestID,
	})

	advanceAccounting, advanceAccountingResolved := requireInternalAccounting(t, client, eps.GatewayHTTP, adminKey, escrowID, advance.ResponseRequestID, 8*time.Second)
	writeJSONArtifact(t, root, "advance.accounting.json", advanceAccounting)

	afterDump, terminalRetry, retryTerminalAfterAdvance := waitG004QTerminal(t, client, eps.GatewayHTTP, adminKey, escrowID, retryWinnerNonce, 10*time.Second)
	writeJSONArtifact(t, root, "inferences.after-advance.json", afterDump)
	afterStateRaw := requireDevshardState(t, client, eps.GatewayHTTP, adminKey, escrowID)
	afterState := decodeG004QState(t, afterStateRaw)
	writeRawJSONArtifact(t, root, "devshard_state.after-advance.json", afterStateRaw)

	unexplained := []string{}
	if !timeoutObserved {
		unexplained = append(unexplained, "first transport did not produce the expected ambiguous client timeout")
	}
	if !firstCompletionObserved {
		unexplained = append(unexplained, "timed-out request did not produce a completion witness before retry")
	}
	if len(internalIDs) != 2 || internalIDs[0] == internalIDs[1] {
		unexplained = append(unexplained, "timeout/retry did not retain two distinct canonical internal request IDs")
	}
	if !pendingBeforeAdvance {
		unexplained = append(unexplained, "retry winner was not observed pending before the protocol-clock advance")
	}
	if !advanceAccountingResolved || advanceAccounting.WinnerNonce == 0 {
		unexplained = append(unexplained, "advance request accounting did not resolve a winner nonce")
	}

	protocolAdvanceObserved := advance.Status >= http.StatusOK && advance.Status < http.StatusMultipleChoices && afterState.Session.Fees > pendingState.Session.Fees
	if !protocolAdvanceObserved {
		unexplained = append(unexplained, "no state-advancing fee/nonce effect was observed after the advance request")
	}
	if !retryTerminalAfterAdvance {
		unexplained = append(unexplained, "retry winner remained non-terminal after an actual state-advance opportunity")
	}
	if retryTerminalAfterAdvance && terminalRetry.Status != "finished" {
		unexplained = append(unexplained, "client-visible successful retry terminalized to "+terminalRetry.Status+" instead of finished")
	}

	retryRelease := uint64(0)
	if pendingBeforeAdvance && retryTerminalAfterAdvance {
		if pendingRetry.ReservedCost < terminalRetry.ActualCost {
			unexplained = append(unexplained, fmt.Sprintf("retry actual cost exceeded reservation: reserved=%d actual=%d", pendingRetry.ReservedCost, terminalRetry.ActualCost))
		} else {
			retryRelease = pendingRetry.ReservedCost - terminalRetry.ActualCost
		}
	}

	liabilityBefore, liabilityBeforeOK := g004qLiability(pendingDump)
	liabilityAfter, liabilityAfterOK := g004qLiability(afterDump)
	if !liabilityBeforeOK || !liabilityAfterOK {
		unexplained = append(unexplained, "G-004Q encountered inference states outside the no-dispute accounting model")
	}

	feeDeltaOK := afterState.Session.Fees >= pendingState.Session.Fees
	feeDelta := uint64(0)
	if feeDeltaOK {
		feeDelta = afterState.Session.Fees - pendingState.Session.Fees
	} else {
		unexplained = append(unexplained, "session fees decreased across the protocol-clock advance")
	}

	expectedBalanceAfter := int64(pendingState.Session.Balance) - (int64(liabilityAfter) - int64(liabilityBefore)) - int64(feeDelta)
	balanceReconciles := liabilityBeforeOK && liabilityAfterOK && feeDeltaOK && expectedBalanceAfter >= 0 && uint64(expectedBalanceAfter) == afterState.Session.Balance
	if !balanceReconciles {
		unexplained = append(unexplained, fmt.Sprintf("state-level balance reconciliation failed: before=%d liability_before=%d liability_after=%d fee_delta=%d expected_after=%d observed_after=%d", pendingState.Session.Balance, liabilityBefore, liabilityAfter, feeDelta, expectedBalanceAfter, afterState.Session.Balance))
	}

	actualBefore := g004qActualCost(pendingDump)
	actualAfter := g004qActualCost(afterDump)
	hostBefore := g004qHostCost(pendingState)
	hostAfter := g004qHostCost(afterState)
	actualDeltaOK := actualAfter >= actualBefore
	hostDeltaOK := hostAfter >= hostBefore
	hostCostReconciles := actualDeltaOK && hostDeltaOK && actualAfter-actualBefore == hostAfter-hostBefore
	if !hostCostReconciles {
		unexplained = append(unexplained, fmt.Sprintf("HostStats cost delta did not match inference ActualCost delta: actual_before=%d actual_after=%d host_before=%d host_after=%d", actualBefore, actualAfter, hostBefore, hostAfter))
	}

	verdict := "PASS"
	if len(unexplained) > 0 {
		verdict = "FAIL"
	}

	evidence := cgqaProtocolClockEvidence{
		SchemaVersion:             "gonka-protocol-clock-reconciliation-v0.1",
		CaseID:                    "G-004Q",
		LogicalOperationID:        logicalID,
		UpstreamRevision:          cgqaUpstreamRevision,
		Environment:               "gonka-local-devshard-testenv",
		ClientCorrelationID:       correlationID,
		RetryInternalRequestID:    second.ResponseRequestID,
		RetryWinnerNonce:          retryWinnerNonce,
		TimeoutObserved:           timeoutObserved,
		FirstCompletionObserved:   firstCompletionObserved,
		RetryHTTPStatus:           second.Status,
		PendingBeforeAdvance:      pendingBeforeAdvance,
		PendingReservedCost:       pendingRetry.ReservedCost,
		AdvanceCorrelationID:      advanceCorrelationID,
		AdvanceInternalRequestID:  advance.ResponseRequestID,
		AdvanceWinnerNonce:        advanceAccounting.WinnerNonce,
		AdvanceHTTPStatus:         advance.Status,
		ProtocolAdvanceObserved:   protocolAdvanceObserved,
		RetryTerminalAfterAdvance: retryTerminalAfterAdvance,
		RetryTerminalStatus:       terminalRetry.Status,
		RetryActualCost:           terminalRetry.ActualCost,
		RetrySurplusRelease:       retryRelease,
		LiabilityBefore:           liabilityBefore,
		LiabilityAfter:            liabilityAfter,
		FeesBefore:                pendingState.Session.Fees,
		FeesAfter:                 afterState.Session.Fees,
		BalanceBefore:             pendingState.Session.Balance,
		BalanceAfter:              afterState.Session.Balance,
		ExpectedBalanceAfter:      expectedBalanceAfter,
		BalanceReconciles:         balanceReconciles,
		ActualCostBefore:          actualBefore,
		ActualCostAfter:           actualAfter,
		HostCostBefore:            hostBefore,
		HostCostAfter:             hostAfter,
		HostCostReconciles:        hostCostReconciles,
		UnexplainedEffects:        unexplained,
		Verdict:                   verdict,
		Notes:                     "PASS means the retry was pending before a real protocol-clock advance, then became finished after the next eligible state-advancing request, while the full inference-liability + fee delta reconciled escrow balance and inference ActualCost delta reconciled HostStats.Cost. It does not assert autonomous wall-clock finality without a subsequent diff.",
	}
	writeJSONArtifact(t, root, "reconciliation.json", evidence)
	t.Logf("G-004Q verdict=%s retry_nonce=%d pending_before=%v terminal_after=%v terminal_status=%s release=%d balance_reconciles=%v host_reconciles=%v", verdict, retryWinnerNonce, pendingBeforeAdvance, retryTerminalAfterAdvance, terminalRetry.Status, retryRelease, balanceReconciles, hostCostReconciles)
	if verdict != "PASS" {
		t.Errorf("G-004Q protocol-clock reconciliation FAIL: %v", unexplained)
	}
}

func waitG004QStatus(t *testing.T, client *http.Client, gatewayURL, adminKey, escrowID string, nonce uint64, status string, timeout time.Duration) (cgqaMoneyInferenceDump, cgqaMoneyInference, bool) {
	t.Helper()
	deadline := time.Now().Add(timeout)
	key := strconv.FormatUint(nonce, 10)
	var last cgqaMoneyInferenceDump
	for time.Now().Before(deadline) {
		last = requireMoneyInferenceDump(t, client, gatewayURL, adminKey, escrowID)
		if rec, ok := last.Inferences[key]; ok && rec.Status == status {
			return last, rec, true
		}
		time.Sleep(200 * time.Millisecond)
	}
	return last, last.Inferences[key], false
}

func waitG004QTerminal(t *testing.T, client *http.Client, gatewayURL, adminKey, escrowID string, nonce uint64, timeout time.Duration) (cgqaMoneyInferenceDump, cgqaMoneyInference, bool) {
	t.Helper()
	deadline := time.Now().Add(timeout)
	key := strconv.FormatUint(nonce, 10)
	var last cgqaMoneyInferenceDump
	for time.Now().Before(deadline) {
		last = requireMoneyInferenceDump(t, client, gatewayURL, adminKey, escrowID)
		if rec, ok := last.Inferences[key]; ok && (rec.Status == "finished" || rec.Status == "timed_out") {
			return last, rec, true
		}
		time.Sleep(200 * time.Millisecond)
	}
	return last, last.Inferences[key], false
}

func decodeG004QState(t *testing.T, raw []byte) cgqaProtocolClockState {
	t.Helper()
	var out cgqaProtocolClockState
	require.NoError(t, json.Unmarshal(raw, &out))
	return out
}

func g004qHostCost(state cgqaProtocolClockState) uint64 {
	var total uint64
	for _, host := range state.HostStats {
		total += host.Cost
	}
	return total
}

func g004qActualCost(dump cgqaMoneyInferenceDump) uint64 {
	var total uint64
	for _, rec := range dump.Inferences {
		total += rec.ActualCost
	}
	return total
}

func g004qLiability(dump cgqaMoneyInferenceDump) (uint64, bool) {
	var total uint64
	for _, rec := range dump.Inferences {
		switch rec.Status {
		case "pending", "started":
			total += rec.ReservedCost
		case "finished", "validated", "timed_out":
			total += rec.ActualCost
		case "challenged", "invalidated":
			return 0, false
		default:
			return 0, false
		}
	}
	return total, true
}

func g004qEvidenceRoot(t *testing.T) string {
	t.Helper()
	root := strings.TrimSpace(os.Getenv("CGQA_EVIDENCE_DIR"))
	if root == "" {
		root = filepath.Join(t.TempDir(), "cgqa-g004q-protocol-clock")
	}
	require.NoError(t, os.MkdirAll(root, 0o755))
	return root
}
