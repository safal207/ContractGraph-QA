//go:build testenvci

package citest

import (
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

type cgqaLivenessSample struct {
	ElapsedMS    int64  `json:"elapsed_ms"`
	Status       string `json:"status"`
	ReservedCost uint64 `json:"reserved_cost"`
	ActualCost   uint64 `json:"actual_cost"`
	Balance      uint64 `json:"balance"`
	HostCost     uint64 `json:"host_cost"`
}

type cgqaPostSuccessLivenessEvidence struct {
	SchemaVersion               string              `json:"schema_version"`
	CaseID                      string              `json:"case_id"`
	LogicalOperationID          string              `json:"logical_operation_id"`
	UpstreamRevision            string              `json:"upstream_revision"`
	Environment                 string              `json:"environment"`
	ClientCorrelationID         string              `json:"client_correlation_id"`
	InternalRequestIDs          []string            `json:"internal_request_ids"`
	RetryInternalRequestID      string              `json:"retry_internal_request_id"`
	RetryWinnerNonce            uint64              `json:"retry_winner_nonce"`
	TimeoutObserved             bool                `json:"timeout_observed"`
	FirstCompletionObserved     bool                `json:"first_completion_observed"`
	RetryHTTPStatus             int                 `json:"retry_http_status"`
	ObservationWindowMS         int64               `json:"observation_window_ms"`
	PendingObserved             bool                `json:"pending_observed"`
	PendingFirstObservedMS      int64               `json:"pending_first_observed_ms,omitempty"`
	PendingReservedCost         uint64              `json:"pending_reserved_cost,omitempty"`
	PendingBalance              uint64              `json:"pending_balance,omitempty"`
	PendingHostCost             uint64              `json:"pending_host_cost,omitempty"`
	TerminalObserved            bool                `json:"terminal_observed"`
	TerminalStatus              string              `json:"terminal_status,omitempty"`
	TerminalObservedMS          int64               `json:"terminal_observed_ms,omitempty"`
	TerminalActualCost          uint64              `json:"terminal_actual_cost,omitempty"`
	TerminalBalance             uint64              `json:"terminal_balance,omitempty"`
	TerminalHostCost            uint64              `json:"terminal_host_cost,omitempty"`
	ExpectedSurplusRelease      uint64              `json:"expected_surplus_release,omitempty"`
	ObservedBalanceRebound      uint64              `json:"observed_balance_rebound,omitempty"`
	ObservedHostCostDelta       uint64              `json:"observed_host_cost_delta,omitempty"`
	ReleaseReconciles           bool                `json:"release_reconciles"`
	Classification              string              `json:"classification"`
	Timeline                    []cgqaLivenessSample `json:"timeline"`
	UnexplainedFinancialEffects []string            `json:"unexplained_financial_effects"`
	Verdict                     string              `json:"verdict"`
	Notes                       string              `json:"notes"`
}

func TestCGQAGonkaPostSuccessReserveLiveness(t *testing.T) {
	harness.SkipUnlessEnv(t, "TESTENV_CITEST")
	harness.RequireDocker(t)

	stack, cfg, eps := harness.BootAdversarialStack(t, "cgqa-gonka-g004p-*")
	client := harness.GatewayChatClient()
	model := config.PrimaryModelID(cfg)
	adminKey := harness.TestenvAdminAPIKey
	escrowID := harness.GetGatewayEscrowID(t, client, eps.GatewayHTTP)
	root := g004pEvidenceRoot(t)

	t.Cleanup(func() {
		harness.ResetMockOpenAIFault(t, client, eps.MockOpenAIHTTP)
		if t.Failed() {
			harness.DumpComposeLogs(t, stack, "devshardctl", "versiond-0", "versiond-1", "mock-openai")
		}
	})

	stamp := time.Now().UTC().UnixNano()
	logicalID := fmt.Sprintf("cgqa-g004p-logical-%d", stamp)
	correlationID := fmt.Sprintf("cgqa-g004p-correlation-%d", stamp)
	body := chatBody(t, model, "CGQA G-004P post-success pending reserve liveness")

	beforePerf := requireDevshardDebugPerf(t, client, eps.GatewayHTTP, adminKey, escrowID)
	beforePerfCount, ok := timeoutPerfRequestCount(beforePerf)
	require.True(t, ok, "G-004P could not establish request-count control")

	latencyMS := 1800
	harness.PatchMockOpenAIFault(t, client, eps.MockOpenAIHTTP, mockopenai.FaultPatch{LatencyMs: &latencyMS})
	shortClient := &http.Client{Timeout: 350 * time.Millisecond}
	first := postIdentityChat(eps.GatewayHTTP, adminKey, correlationID, body, shortClient)
	timeoutObserved := isTimeout(first.Err)
	writeJSONArtifact(t, root, "attempt-1.transport.json", map[string]any{
		"client_correlation_id": correlationID,
		"timeout_observed":      timeoutObserved,
		"response_request_id":   first.ResponseRequestID,
		"error":                 errorString(first.Err),
	})

	_, _, firstCompletionObserved := waitForPerfRequestAfter(client, eps.GatewayHTTP, adminKey, escrowID, beforePerfCount, 15*time.Second)
	firstLookup := requireCorrelationLookup(t, client, eps.GatewayHTTP, adminKey, escrowID, correlationID, 1, 8*time.Second)
	firstIDs := correlationInternalIDs(firstLookup)
	require.Len(t, firstIDs, 1, "G-004P first correlation must resolve exactly one internal request before retry")

	zero := 0
	harness.PatchMockOpenAIFault(t, client, eps.MockOpenAIHTTP, mockopenai.FaultPatch{LatencyMs: &zero})
	retryStarted := time.Now()
	second := postIdentityChat(eps.GatewayHTTP, adminKey, correlationID, body, client)
	require.NoError(t, second.Err)
	require.GreaterOrEqual(t, second.Status, http.StatusOK)
	require.Less(t, second.Status, http.StatusMultipleChoices)
	require.NotEmpty(t, second.ResponseRequestID)
	writeJSONArtifact(t, root, "attempt-2.transport.json", map[string]any{
		"client_correlation_id": correlationID,
		"http_status":           second.Status,
		"response_request_id":   second.ResponseRequestID,
	})

	lookup := requireCorrelationLookup(t, client, eps.GatewayHTTP, adminKey, escrowID, correlationID, 2, 8*time.Second)
	internalIDs := correlationInternalIDs(lookup)
	writeJSONArtifact(t, root, "correlation.lookup.json", lookup)
	require.Len(t, internalIDs, 2, "G-004P timeout/retry must retain two internal request IDs")
	require.True(t, containsString(internalIDs, second.ResponseRequestID), "retry response request ID missing from correlation lookup")

	retryAccounting, retryAccountingResolved := requireInternalAccounting(t, client, eps.GatewayHTTP, adminKey, escrowID, second.ResponseRequestID, 8*time.Second)
	require.True(t, retryAccountingResolved, "G-004P retry accounting unresolved")
	writeJSONArtifact(t, root, "retry.accounting.json", retryAccounting)
	winnerNonce := retryAccounting.WinnerNonce
	require.NotZero(t, winnerNonce)

	const observationWindow = 120 * time.Second
	const sampleInterval = 2 * time.Second
	deadline := time.Now().Add(observationWindow)
	winnerKey := strconv.FormatUint(winnerNonce, 10)
	timeline := make([]cgqaLivenessSample, 0, int(observationWindow/sampleInterval)+2)

	pendingObserved := false
	pendingFirstMS := int64(0)
	pendingReserved := uint64(0)
	pendingBalance := uint64(0)
	pendingHostCost := uint64(0)
	terminalObserved := false
	terminalStatus := ""
	terminalObservedMS := int64(0)
	terminalActualCost := uint64(0)
	terminalBalance := uint64(0)
	terminalHostCost := uint64(0)

	for {
		dump := requireMoneyInferenceDump(t, client, eps.GatewayHTTP, adminKey, escrowID)
		rec, exists := dump.Inferences[winnerKey]
		stateRaw := requireDevshardState(t, client, eps.GatewayHTTP, adminKey, escrowID)
		state := decodeMoneyState(t, stateRaw)
		elapsed := time.Since(retryStarted).Milliseconds()
		sample := cgqaLivenessSample{ElapsedMS: elapsed, Balance: state.Session.Balance, HostCost: sumMoneyHostCost(state)}
		if exists {
			sample.Status = rec.Status
			sample.ReservedCost = rec.ReservedCost
			sample.ActualCost = rec.ActualCost
		}
		timeline = append(timeline, sample)

		if exists && rec.Status == "pending" && !pendingObserved {
			pendingObserved = true
			pendingFirstMS = elapsed
			pendingReserved = rec.ReservedCost
			pendingBalance = state.Session.Balance
			pendingHostCost = sumMoneyHostCost(state)
			t.Logf("G-004P pending observed nonce=%d elapsed_ms=%d reserved=%d balance=%d host_cost=%d", winnerNonce, elapsed, pendingReserved, pendingBalance, pendingHostCost)
		}
		if exists && (rec.Status == "finished" || rec.Status == "timed_out") {
			terminalObserved = true
			terminalStatus = rec.Status
			terminalObservedMS = elapsed
			terminalActualCost = rec.ActualCost
			terminalBalance = state.Session.Balance
			terminalHostCost = sumMoneyHostCost(state)
			t.Logf("G-004P terminal observed nonce=%d status=%s elapsed_ms=%d actual=%d balance=%d host_cost=%d", winnerNonce, terminalStatus, elapsed, terminalActualCost, terminalBalance, terminalHostCost)
			break
		}
		if time.Now().After(deadline) {
			break
		}
		time.Sleep(sampleInterval)
	}

	writeJSONArtifact(t, root, "timeline.json", timeline)
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
	if !retryAccountingResolved || winnerNonce == 0 {
		unexplained = append(unexplained, "retry winner nonce could not be resolved from request accounting")
	}
	if !terminalObserved {
		unexplained = append(unexplained, fmt.Sprintf("successful retry winner nonce remained non-terminal for at least %s", observationWindow))
	}

	expectedRelease := uint64(0)
	balanceRebound := uint64(0)
	hostDelta := uint64(0)
	releaseReconciles := !pendingObserved
	if pendingObserved && terminalObserved {
		reserveOK := pendingReserved >= terminalActualCost
		if !reserveOK {
			unexplained = append(unexplained, fmt.Sprintf("terminal actual cost exceeded prior reservation: reserved=%d actual=%d", pendingReserved, terminalActualCost))
		} else {
			expectedRelease = pendingReserved - terminalActualCost
		}
		balanceOK := terminalBalance >= pendingBalance
		if balanceOK {
			balanceRebound = terminalBalance - pendingBalance
		} else {
			unexplained = append(unexplained, fmt.Sprintf("balance did not rebound across pending->terminal transition: pending=%d terminal=%d", pendingBalance, terminalBalance))
		}
		hostOK := terminalHostCost >= pendingHostCost
		if hostOK {
			hostDelta = terminalHostCost - pendingHostCost
		} else {
			unexplained = append(unexplained, fmt.Sprintf("aggregate HostStats.Cost decreased across pending->terminal transition: pending=%d terminal=%d", pendingHostCost, terminalHostCost))
		}
		releaseReconciles = reserveOK && balanceOK && hostOK && balanceRebound == expectedRelease && hostDelta == terminalActualCost
		if !releaseReconciles {
			unexplained = append(unexplained, fmt.Sprintf("pending reserve release did not reconcile: reserved=%d actual=%d expected_balance_rebound=%d observed_balance_rebound=%d observed_host_delta=%d", pendingReserved, terminalActualCost, expectedRelease, balanceRebound, hostDelta))
		}
	}

	classification := "terminal_without_observed_pending"
	if pendingObserved && terminalObserved {
		classification = "pending_then_terminal"
	}
	if !terminalObserved {
		classification = "nonterminal_after_observation_window"
	}
	verdict := "PASS"
	if len(unexplained) > 0 {
		verdict = "FAIL"
	}
	evidence := cgqaPostSuccessLivenessEvidence{
		SchemaVersion:               "gonka-post-success-reserve-liveness-v0.1",
		CaseID:                      "G-004P",
		LogicalOperationID:          logicalID,
		UpstreamRevision:            cgqaUpstreamRevision,
		Environment:                 "gonka-local-devshard-testenv",
		ClientCorrelationID:         correlationID,
		InternalRequestIDs:          internalIDs,
		RetryInternalRequestID:      second.ResponseRequestID,
		RetryWinnerNonce:            winnerNonce,
		TimeoutObserved:             timeoutObserved,
		FirstCompletionObserved:     firstCompletionObserved,
		RetryHTTPStatus:             second.Status,
		ObservationWindowMS:         observationWindow.Milliseconds(),
		PendingObserved:             pendingObserved,
		PendingFirstObservedMS:      pendingFirstMS,
		PendingReservedCost:         pendingReserved,
		PendingBalance:              pendingBalance,
		PendingHostCost:             pendingHostCost,
		TerminalObserved:            terminalObserved,
		TerminalStatus:              terminalStatus,
		TerminalObservedMS:          terminalObservedMS,
		TerminalActualCost:          terminalActualCost,
		TerminalBalance:             terminalBalance,
		TerminalHostCost:            terminalHostCost,
		ExpectedSurplusRelease:      expectedRelease,
		ObservedBalanceRebound:      balanceRebound,
		ObservedHostCostDelta:       hostDelta,
		ReleaseReconciles:           releaseReconciles,
		Classification:              classification,
		Timeline:                    timeline,
		UnexplainedFinancialEffects: unexplained,
		Verdict:                     verdict,
		Notes:                       "PASS means the successful retry winner reached finished/timed_out within the bounded observation window and, when a pending reservation was observed, its reserve-to-actual release reconciled against balance and HostStats.Cost. It does not prove mainnet settlement latency or retry idempotency.",
	}
	writeJSONArtifact(t, root, "reconciliation.json", evidence)
	t.Logf("G-004P verdict=%s classification=%s pending=%v terminal=%v terminal_status=%s terminal_ms=%d release_reconciles=%v", verdict, classification, pendingObserved, terminalObserved, terminalStatus, terminalObservedMS, releaseReconciles)
	if verdict != "PASS" {
		t.Errorf("G-004P post-success reserve liveness FAIL: %v", unexplained)
	}
}

func containsString(values []string, target string) bool {
	for _, value := range values {
		if value == target {
			return true
		}
	}
	return false
}

func g004pEvidenceRoot(t *testing.T) string {
	t.Helper()
	root := strings.TrimSpace(os.Getenv("CGQA_EVIDENCE_DIR"))
	if root == "" {
		root = filepath.Join(t.TempDir(), "cgqa-g004p-liveness")
	}
	require.NoError(t, os.MkdirAll(root, 0o755))
	return root
}
