use std::panic::{catch_unwind, AssertUnwindSafe};

use soroban_sdk::testutils::{Address as _, Ledger as _, MockAuth, MockAuthInvoke};
use soroban_sdk::{Address, Env, IntoVal, Symbol, Vec as SorobanVec};
use streampay_contracts::{StreamInfo, StreamPayContract, StreamPayContractClient};

const STREAM_KEY: &str = "stream";
type EconomicState = (i128, i128, u64, u64, bool, u64);
type OrderedBatchResult = (EconomicState, EconomicState, i128, i128);
type MixedBatchResult = (
    EconomicState,
    EconomicState,
    EconomicState,
    i128,
    i128,
    i128,
);

fn at(env: &Env, timestamp: u64) {
    env.ledger().with_mut(|ledger| ledger.timestamp = timestamp);
}

fn contract(env: &Env) -> (Address, StreamPayContractClient<'_>) {
    env.mock_all_auths();
    let contract_id = env.register(StreamPayContract, ());
    let client = StreamPayContractClient::new(env, &contract_id);
    (contract_id, client)
}

fn create_started(
    env: &Env,
    client: &StreamPayContractClient<'_>,
    start: u64,
    rate: i128,
    balance: i128,
    end_time: u64,
) -> u32 {
    at(env, start);
    let payer = Address::generate(env);
    let recipient = Address::generate(env);
    let id = client.create_stream(&payer, &recipient, &rate, &balance, &end_time);
    client.start_stream(&id);
    id
}

fn info(client: &StreamPayContractClient<'_>, id: u32) -> StreamInfo {
    client.get_stream_info(&id)
}

fn assert_stream_fields_eq(left: &StreamInfo, right: &StreamInfo) {
    assert_eq!(left.payer, right.payer);
    assert_eq!(left.recipient, right.recipient);
    assert_eq!(left.rate_per_second, right.rate_per_second);
    assert_eq!(left.balance, right.balance);
    assert_eq!(left.start_time, right.start_time);
    assert_eq!(left.end_time, right.end_time);
    assert_eq!(left.is_active, right.is_active);
    assert_eq!(left.paused_at, right.paused_at);
}

fn economic_state(value: &StreamInfo) -> EconomicState {
    (
        value.rate_per_second,
        value.balance,
        value.start_time,
        value.end_time,
        value.is_active,
        value.paused_at,
    )
}

fn ids(env: &Env, values: &[u32]) -> SorobanVec<u32> {
    let mut result = SorobanVec::new(env);
    for value in values {
        result.push_back(*value);
    }
    result
}

fn assert_rejected_stream_fields_unchanged<F>(
    client: &StreamPayContractClient<'_>,
    stream_id: u32,
    operation: F,
) where
    F: FnOnce(),
{
    let before = info(client, stream_id);
    let result = catch_unwind(AssertUnwindSafe(operation));
    assert!(result.is_err(), "operation unexpectedly succeeded");
    let after = info(client, stream_id);
    assert_stream_fields_eq(&before, &after);
}

#[test]
fn h1_nonzero_start_boundary_matrix_for_all_value_paths() {
    for observed_at in [109_u64, 110, 111, u64::MAX] {
        let expected = (observed_at.min(110) - 100) as i128 * 2;

        for action in ["settle", "pause", "cancel", "stop"] {
            let env = Env::default();
            let (_, client) = contract(&env);
            let id = create_started(&env, &client, 100, 2, 100, 110);
            at(&env, observed_at);

            let returned = match action {
                "settle" => client.settle_stream(&id),
                "pause" => {
                    client.pause_stream(&id);
                    0
                }
                "cancel" => {
                    client.cancel_stream(&id);
                    0
                }
                "stop" => {
                    client.stop_stream(&id);
                    0
                }
                _ => unreachable!(),
            };
            let after = info(&client, id);

            if action == "settle" {
                assert_eq!(returned, expected);
            }
            assert_eq!(100 - after.balance, expected, "{action} at {observed_at}");
            assert_eq!(after.start_time, observed_at.min(110));

            if action == "settle" && observed_at < 110 {
                assert!(after.is_active);
                assert_eq!(after.end_time, 110);
                assert_eq!(after.paused_at, 0);
            } else if action == "pause" && observed_at < 110 {
                assert!(after.is_active);
                assert_eq!(after.end_time, 110);
                assert_eq!(after.paused_at, observed_at);
            } else {
                assert!(!after.is_active);
                assert_eq!(
                    after.end_time,
                    if observed_at < 110 { observed_at } else { 110 }
                );
                assert_eq!(after.paused_at, 0);
            }
        }
    }
}

#[test]
fn h1_delayed_start_rejection_and_unlimited_nonzero_start() {
    let env = Env::default();
    let (_, client) = contract(&env);
    at(&env, 100);
    let payer = Address::generate(&env);
    let recipient = Address::generate(&env);
    let delayed = client.create_stream(&payer, &recipient, &7, &100, &110);
    let created = info(&client, delayed);
    assert!(!created.is_active);
    assert_eq!(created.start_time, 0);
    at(&env, 109);
    client.start_stream(&delayed);
    let started = info(&client, delayed);
    assert!(started.is_active);
    assert_eq!(started.start_time, 109);
    at(&env, 110);
    assert_eq!(client.settle_stream(&delayed), 7);
    let delayed_after = info(&client, delayed);
    assert_eq!(delayed_after.balance, 93);
    assert_eq!(delayed_after.start_time, 110);
    assert!(!delayed_after.is_active);

    let env = Env::default();
    let (_, client) = contract(&env);
    at(&env, 100);
    let payer = Address::generate(&env);
    let recipient = Address::generate(&env);
    let rejected = client.create_stream(&payer, &recipient, &7, &100, &110);
    let before = info(&client, rejected);
    at(&env, 110);
    assert_rejected_stream_fields_unchanged(&client, rejected, || client.start_stream(&rejected));
    assert_stream_fields_eq(&before, &info(&client, rejected));

    let env = Env::default();
    let (_, client) = contract(&env);
    let unlimited = create_started(&env, &client, 100, 3, 1_000, 0);
    at(&env, 109);
    assert_eq!(client.settle_stream(&unlimited), 27);
    let unlimited_after = info(&client, unlimited);
    assert_eq!(unlimited_after.balance, 973);
    assert_eq!(unlimited_after.start_time, 109);
    assert!(unlimited_after.is_active);
}

/// H2 diagnostic RED: the data representation uses zero as both a valid
/// ledger timestamp and the "not paused" sentinel. This is a representation
/// boundary witness; production severity depends on whether timestamp zero is
/// reachable on the deployed network.
#[test]
fn h2_pause_at_timestamp_zero_must_actually_freeze_accrual() {
    let env = Env::default();
    let (_, client) = contract(&env);
    let id = create_started(&env, &client, 0, 1, 10, 10);

    client.pause_stream(&id);
    let after_pause = info(&client, id);
    assert_eq!(
        after_pause.paused_at, 0,
        "timestamp-zero pause collides with the not-paused sentinel"
    );
    at(&env, 2);
    let paid_while_intended_paused = client.settle_stream(&id);
    let resume = catch_unwind(AssertUnwindSafe(|| client.resume_stream(&id)));
    at(&env, 3);
    let paid_after_intended_resume = client.settle_stream(&id);

    eprintln!(
        "timestamp-zero pause: marker={}, paid_while_paused={}, resume_ok={}, paid_after_resume={}",
        after_pause.paused_at,
        paid_while_intended_paused,
        resume.is_ok(),
        paid_after_intended_resume
    );
    assert!(after_pause.is_active);
    assert_eq!(
        paid_while_intended_paused, 0,
        "a pause at timestamp zero must freeze [0,2]"
    );
    assert!(resume.is_ok(), "the paused stream must be resumable at t=2");
    assert_eq!(paid_after_intended_resume, 1, "only resumed [2,3] accrues");
}

/// Audit-only H2-family boundary: early terminalization normally persists a
/// nonzero end marker that prevents start_stream from reviving the stream.
/// At timestamp zero, both bounded and unlimited cancel/stop terminal states
/// instead collide with the unlimited `end_time == 0` sentinel. Deployed
/// Stellar timestamp-zero reachability is treated as NOT_APPLICABLE.
#[test]
fn h2_cancel_and_stop_at_zero_must_not_resurrect_as_unlimited() {
    fn terminal_then_restart(
        action: &str,
        configured_end: u64,
    ) -> (EconomicState, bool, EconomicState) {
        let env = Env::default();
        let (_, client) = contract(&env);
        let id = create_started(&env, &client, 0, 1, 10, configured_end);

        match action {
            "cancel" => client.cancel_stream(&id),
            "stop" => client.stop_stream(&id),
            _ => unreachable!(),
        }
        let terminal = economic_state(&info(&client, id));

        at(&env, 1);
        let restart_succeeded = catch_unwind(AssertUnwindSafe(|| client.start_stream(&id))).is_ok();
        let after_restart_attempt = economic_state(&info(&client, id));
        (terminal, restart_succeeded, after_restart_attempt)
    }

    let bounded_cancel = terminal_then_restart("cancel", 10);
    let bounded_stop = terminal_then_restart("stop", 10);
    let unlimited_cancel = terminal_then_restart("cancel", 0);
    let unlimited_stop = terminal_then_restart("stop", 0);

    for (terminal, _, _) in [
        bounded_cancel,
        bounded_stop,
        unlimited_cancel,
        unlimited_stop,
    ] {
        assert_eq!(terminal, (1, 10, 0, 0, false, 0));
    }

    let all_remain_terminal = [
        bounded_cancel,
        bounded_stop,
        unlimited_cancel,
        unlimited_stop,
    ]
    .iter()
    .all(|(terminal, restarted, after)| !restarted && after == terminal);
    assert!(
        all_remain_terminal,
        "cancel/stop terminality must reject restart instead of reviving an unlimited stream"
    );
}

fn inject_legacy_paused(
    env: &Env,
    contract_id: &Address,
    client: &StreamPayContractClient<'_>,
    id: u32,
    paused_at: u64,
    old_balance: i128,
) {
    let mut legacy = info(client, id);
    legacy.start_time = 100;
    legacy.balance = old_balance;
    legacy.is_active = true;
    legacy.paused_at = paused_at;
    env.as_contract(contract_id, || {
        env.storage()
            .persistent()
            .set(&(Symbol::new(env, STREAM_KEY), id), &legacy);
    });
}

#[test]
fn h3_legacy_paused_before_exact_and_after_end_are_classified() {
    // Old pause before end: [100,105] was already deducted; current settlement
    // prevents replay and terminalizes when later observed after end.
    let env = Env::default();
    let (contract_id, client) = contract(&env);
    let before_end = create_started(&env, &client, 100, 1, 20, 110);
    inject_legacy_paused(&env, &contract_id, &client, before_end, 105, 15);
    at(&env, 120);
    assert_eq!(client.settle_stream(&before_end), 0);
    let before_after = info(&client, before_end);
    assert_eq!(before_after.balance, 15);
    assert_eq!(before_after.start_time, 105);
    assert_eq!(before_after.end_time, 110);
    assert!(!before_after.is_active);
    assert_eq!(before_after.paused_at, 0);

    // Old pause exactly at end: the whole eligible [100,110] interval was paid.
    let env = Env::default();
    let (contract_id, client) = contract(&env);
    let exact_end = create_started(&env, &client, 100, 1, 20, 110);
    inject_legacy_paused(&env, &contract_id, &client, exact_end, 110, 10);
    at(&env, 120);
    let amounts = client.batch_settle(&ids(&env, &[exact_end]));
    assert_eq!(amounts.get(0).unwrap(), 0);
    let exact_after = info(&client, exact_end);
    assert_eq!(exact_after.balance, 10);
    assert_eq!(exact_after.start_time, 110);
    assert_eq!(exact_after.end_time, 110);
    assert!(!exact_after.is_active);
    assert_eq!(exact_after.paused_at, 0);

    // Old pause after end deducted 12 although only 10 was eligible. The new
    // cursor prevents another charge but cannot infer/refund the historical
    // over-deduction from this state alone.
    let env = Env::default();
    let (contract_id, client) = contract(&env);
    let after_end = create_started(&env, &client, 100, 1, 20, 110);
    inject_legacy_paused(&env, &contract_id, &client, after_end, 112, 8);
    at(&env, 120);
    client.cancel_stream(&after_end);
    let after_after = info(&client, after_end);
    let observed_accounted = 20 - after_after.balance;
    let maximum_eligible = 10_i128;
    assert_eq!(after_after.balance, 8);
    assert_eq!(after_after.start_time, 110);
    assert_eq!(after_after.end_time, 110);
    assert_eq!(observed_accounted, 12);
    assert!(observed_accounted > maximum_eligible);
    assert!(!after_after.is_active);
    assert_eq!(after_after.paused_at, 0);

    // stop_stream shares the terminalization path. Exercise all three legacy
    // shapes independently: it prevents future replay for each, while the
    // already-overdeducted after-end shape remains unrecoverable.
    for (paused_at, old_balance, expected_start, old_accounted) in [
        (105_u64, 15_i128, 105_u64, 5_i128),
        (110, 10, 110, 10),
        (112, 8, 110, 12),
    ] {
        let env = Env::default();
        let (contract_id, client) = contract(&env);
        let id = create_started(&env, &client, 100, 1, 20, 110);
        inject_legacy_paused(&env, &contract_id, &client, id, paused_at, old_balance);
        at(&env, 120);
        client.stop_stream(&id);
        let stopped = info(&client, id);

        assert_eq!(
            economic_state(&stopped),
            (1, old_balance, expected_start, 110, false, 0)
        );
        assert_eq!(20 - stopped.balance, old_accounted);
        if paused_at <= 110 {
            assert!(old_accounted <= maximum_eligible);
        } else {
            assert!(old_accounted > maximum_eligible);
        }
    }
}

fn geometry_settle_terminal(use_cancel: bool, settle_first: bool) -> (EconomicState, i128) {
    let env = Env::default();
    let (_, client) = contract(&env);
    let id = create_started(&env, &client, 100, 2, 100, 110);
    at(&env, 103);
    let returned = if settle_first {
        let amount = client.settle_stream(&id);
        if use_cancel {
            client.cancel_stream(&id);
        } else {
            client.stop_stream(&id);
        }
        amount
    } else {
        if use_cancel {
            client.cancel_stream(&id);
        } else {
            client.stop_stream(&id);
        }
        client.settle_stream(&id)
    };
    (economic_state(&info(&client, id)), returned)
}

fn geometry_pause_settle(pause_first: bool) -> (EconomicState, i128) {
    let env = Env::default();
    let (_, client) = contract(&env);
    let id = create_started(&env, &client, 100, 2, 100, 110);
    at(&env, 103);
    let returned = if pause_first {
        client.pause_stream(&id);
        client.settle_stream(&id)
    } else {
        let amount = client.settle_stream(&id);
        client.pause_stream(&id);
        amount
    };
    (economic_state(&info(&client, id)), returned)
}

fn geometry_pause_terminal(use_cancel: bool, pause_first: bool) -> (EconomicState, bool) {
    let env = Env::default();
    let (_, client) = contract(&env);
    let id = create_started(&env, &client, 100, 2, 100, 110);
    at(&env, 103);
    let second_rejected = if pause_first {
        client.pause_stream(&id);
        if use_cancel {
            client.cancel_stream(&id);
        } else {
            client.stop_stream(&id);
        }
        false
    } else {
        if use_cancel {
            client.cancel_stream(&id);
        } else {
            client.stop_stream(&id);
        }
        catch_unwind(AssertUnwindSafe(|| client.pause_stream(&id))).is_err()
    };
    (economic_state(&info(&client, id)), second_rejected)
}

#[test]
fn h4_stop_and_cancel_current_economics_match_for_active_and_paused_streams() {
    let (cancel_active, cancel_late_settle) = geometry_settle_terminal(true, false);
    let (stop_active, stop_late_settle) = geometry_settle_terminal(false, false);
    assert_eq!(cancel_active, stop_active);
    assert_eq!((cancel_late_settle, stop_late_settle), (0, 0));

    let (cancel_paused, _) = geometry_pause_terminal(true, true);
    let (stop_paused, _) = geometry_pause_terminal(false, true);
    assert_eq!(cancel_paused, stop_paused);
    assert_eq!(cancel_paused.1, 94, "both account the earned [100,103]");
    assert!(!cancel_paused.4);
    assert_eq!(cancel_paused.5, 0);
}

#[test]
fn h5_same_ledger_pairwise_geometry_preserves_value_and_exposes_history() {
    for use_cancel in [true, false] {
        let (settle_first, first_return) = geometry_settle_terminal(use_cancel, true);
        let (terminal_first, second_return) = geometry_settle_terminal(use_cancel, false);
        assert_eq!(settle_first, terminal_first);
        assert_eq!(first_return, 6);
        assert_eq!(second_return, 0);
        // Same state/value, different placement of the settlement witness:
        // HISTORY_DIVERGENT rather than a claim of identical causal history.
    }

    let (pause_first, after_pause_return) = geometry_pause_settle(true);
    let (settle_first, before_pause_return) = geometry_pause_settle(false);
    assert_eq!(pause_first, settle_first);
    assert_eq!(after_pause_return, 0);
    assert_eq!(before_pause_return, 6);

    for use_cancel in [true, false] {
        let (pause_first, no_rejection) = geometry_pause_terminal(use_cancel, true);
        let (terminal_first, rejected) = geometry_pause_terminal(use_cancel, false);
        assert_eq!(pause_first, terminal_first);
        assert!(!no_rejection);
        assert!(rejected);
        // Final economics are equal, but acceptance order is asymmetric.
    }

    // pause -> resume -> settle and settle -> pause -> resume converge, but
    // the permissionless settlement return records different causal history.
    let env = Env::default();
    let (_, client) = contract(&env);
    let first = create_started(&env, &client, 100, 2, 100, 110);
    at(&env, 103);
    client.pause_stream(&first);
    client.resume_stream(&first);
    let first_return = client.settle_stream(&first);
    let first_state = economic_state(&info(&client, first));

    let env = Env::default();
    let (_, client) = contract(&env);
    let second = create_started(&env, &client, 100, 2, 100, 110);
    at(&env, 103);
    let second_return = client.settle_stream(&second);
    client.pause_stream(&second);
    client.resume_stream(&second);
    let second_state = economic_state(&info(&client, second));
    assert_eq!(first_state, second_state);
    assert_eq!(first_return, 0);
    assert_eq!(second_return, 6);
}

#[test]
fn h5_pause_resume_nonzero_gap_matches_independent_action_history() {
    let env = Env::default();
    let (_, client) = contract(&env);
    let id = create_started(&env, &client, 100, 2, 100, 110);

    at(&env, 103);
    client.pause_stream(&id);
    let paused = info(&client, id);
    assert_eq!(economic_state(&paused), (2, 94, 103, 110, true, 103));
    let accounted_before_pause = 100 - paused.balance;
    assert_eq!(accounted_before_pause, 6, "active [100,103] earns 3 * 2");

    at(&env, 107);
    assert_eq!(client.settle_stream(&id), 0, "paused [103,107] earns zero");
    assert_stream_fields_eq(&paused, &info(&client, id));
    client.resume_stream(&id);
    assert_eq!(
        economic_state(&info(&client, id)),
        (2, 94, 107, 110, true, 0)
    );

    at(&env, 110);
    let accounted_after_resume = client.settle_stream(&id);
    assert_eq!(accounted_after_resume, 6, "resumed [107,110] earns 3 * 2");
    let terminal = info(&client, id);
    assert_eq!(economic_state(&terminal), (2, 88, 110, 110, false, 0));
    assert_eq!(
        accounted_before_pause + accounted_after_resume,
        12,
        "only the union [100,103] U [107,110] is chargeable"
    );
}

#[test]
fn h5_h6_batch_order_duplicates_empty_and_repeat_are_once_only() {
    fn ordered(reverse: bool) -> OrderedBatchResult {
        let env = Env::default();
        let (_, client) = contract(&env);
        let a = create_started(&env, &client, 100, 2, 100, 0);
        let b = create_started(&env, &client, 100, 3, 100, 0);
        at(&env, 104);
        let order = if reverse {
            ids(&env, &[b, a])
        } else {
            ids(&env, &[a, b])
        };
        let amounts = client.batch_settle(&order);
        let amount_a = if reverse {
            amounts.get(1).unwrap()
        } else {
            amounts.get(0).unwrap()
        };
        let amount_b = if reverse {
            amounts.get(0).unwrap()
        } else {
            amounts.get(1).unwrap()
        };
        (
            economic_state(&info(&client, a)),
            economic_state(&info(&client, b)),
            amount_a,
            amount_b,
        )
    }

    let forward = ordered(false);
    let reverse = ordered(true);
    assert_eq!(forward, reverse); // CLOSED per-id geometry.
    assert_eq!(forward.0, (2, 92, 104, 0, true, 0));
    assert_eq!(forward.1, (3, 88, 104, 0, true, 0));
    assert_eq!((forward.2, forward.3), (8, 12));

    let env = Env::default();
    let (_, client) = contract(&env);
    let a = create_started(&env, &client, 100, 2, 100, 0);
    at(&env, 104);
    let before_empty = info(&client, a);
    assert_eq!(client.batch_settle(&SorobanVec::new(&env)).len(), 0);
    assert_stream_fields_eq(&before_empty, &info(&client, a));
    let duplicate = client.batch_settle(&ids(&env, &[a, a]));
    assert_eq!(duplicate.get(0).unwrap(), 8);
    assert_eq!(duplicate.get(1).unwrap(), 0);
    let after_duplicate = info(&client, a);
    assert_eq!(economic_state(&after_duplicate), (2, 92, 104, 0, true, 0));
    let repeated = client.batch_settle(&ids(&env, &[a]));
    assert_eq!(repeated.get(0).unwrap(), 0);
    assert_stream_fields_eq(&after_duplicate, &info(&client, a));
    assert_eq!(client.settle_stream(&a), 0);
    assert_stream_fields_eq(&after_duplicate, &info(&client, a));

    // Settle -> batch and batch -> settle have equal totals/state, while the
    // returned amount is attached to a different call (HISTORY_DIVERGENT).
    let env = Env::default();
    let (_, client) = contract(&env);
    let first = create_started(&env, &client, 100, 2, 100, 0);
    at(&env, 104);
    let first_direct = client.settle_stream(&first);
    let first_batch = client.batch_settle(&ids(&env, &[first])).get(0).unwrap();
    let first_state = economic_state(&info(&client, first));

    let env = Env::default();
    let (_, client) = contract(&env);
    let second = create_started(&env, &client, 100, 2, 100, 0);
    at(&env, 104);
    let second_batch = client.batch_settle(&ids(&env, &[second])).get(0).unwrap();
    let second_direct = client.settle_stream(&second);
    let second_state = economic_state(&info(&client, second));
    assert_eq!(first_state, second_state);
    assert_eq!(first_state, (2, 92, 104, 0, true, 0));
    assert_eq!((first_direct, first_batch), (8, 0));
    assert_eq!((second_direct, second_batch), (0, 8));
}

#[test]
fn h6_batch_active_paused_ended_and_reverse_order() {
    fn run(reverse: bool) -> MixedBatchResult {
        let env = Env::default();
        let (_, client) = contract(&env);
        let active = create_started(&env, &client, 100, 1, 100, 0);
        let paused = create_started(&env, &client, 100, 1, 100, 0);
        let ended = create_started(&env, &client, 100, 1, 100, 103);
        at(&env, 102);
        client.pause_stream(&paused);
        at(&env, 104);
        let order = if reverse {
            ids(&env, &[ended, paused, active])
        } else {
            ids(&env, &[active, paused, ended])
        };
        let amounts = client.batch_settle(&order);
        let (active_amount, paused_amount, ended_amount) = if reverse {
            (
                amounts.get(2).unwrap(),
                amounts.get(1).unwrap(),
                amounts.get(0).unwrap(),
            )
        } else {
            (
                amounts.get(0).unwrap(),
                amounts.get(1).unwrap(),
                amounts.get(2).unwrap(),
            )
        };
        (
            economic_state(&info(&client, active)),
            economic_state(&info(&client, paused)),
            economic_state(&info(&client, ended)),
            active_amount,
            paused_amount,
            ended_amount,
        )
    }

    let forward = run(false);
    let reverse = run(true);
    assert_eq!(forward, reverse);
    assert_eq!((forward.3, forward.4, forward.5), (4, 0, 3));
    assert_eq!(forward.0, (1, 96, 104, 0, true, 0));
    assert_eq!(forward.1, (1, 98, 102, 0, true, 102));
    assert_eq!(forward.2, (1, 97, 103, 103, false, 0));
}

#[test]
fn h6_rejected_batches_roll_back_all_stream_fields() {
    let env = Env::default();
    let (_, client) = contract(&env);
    let first = create_started(&env, &client, 100, 2, 100, 0);
    let second = create_started(&env, &client, 100, 3, 100, 0);
    at(&env, 104);
    let first_before = info(&client, first);
    let second_before = info(&client, second);
    let attempted = ids(&env, &[first, 999_999, second]);
    let missing = catch_unwind(AssertUnwindSafe(|| client.batch_settle(&attempted)));
    assert!(missing.is_err());
    assert_stream_fields_eq(&first_before, &info(&client, first));
    assert_stream_fields_eq(&second_before, &info(&client, second));
}

#[test]
fn h6_batch_bound_25_succeeds_and_26_rejects_without_mutation() {
    let env = Env::default();
    let (_, client) = contract(&env);
    let mut distinct = std::vec::Vec::new();
    for _ in 0..25 {
        distinct.push(create_started(&env, &client, 100, 1, 10, 0));
    }
    at(&env, 101);
    let twenty_five = ids(&env, &distinct);
    let amounts = client.batch_settle(&twenty_five);
    assert_eq!(amounts.len(), 25);
    for (index, id) in distinct.iter().enumerate() {
        assert_eq!(amounts.get(index as u32).unwrap(), 1);
        let after = info(&client, *id);
        assert_eq!(after.rate_per_second, 1);
        assert_eq!(after.balance, 9);
        assert_eq!(after.start_time, 101);
        assert_eq!(after.end_time, 0);
        assert!(after.is_active);
        assert_eq!(after.paused_at, 0);
    }

    at(&env, 102);
    let before: std::vec::Vec<StreamInfo> = distinct.iter().map(|id| info(&client, *id)).collect();
    let mut twenty_six_ids = distinct.clone();
    twenty_six_ids.push(distinct[0]);
    let twenty_six = ids(&env, &twenty_six_ids);
    let rejected = catch_unwind(AssertUnwindSafe(|| client.batch_settle(&twenty_six)));
    assert!(rejected.is_err());
    for (id, expected) in distinct.iter().zip(before.iter()) {
        assert_stream_fields_eq(expected, &info(&client, *id));
    }
}

#[test]
fn h7_balance_exhaustion_never_resurrects_value() {
    // Exhausted before end remains active but repeated operations cannot move
    // more than the initial balance, and an explicit stop terminalizes it.
    let env = Env::default();
    let (_, client) = contract(&env);
    let id = create_started(&env, &client, 100, 10, 15, 110);
    at(&env, 102);
    assert_eq!(client.settle_stream(&id), 15);
    assert_eq!(
        economic_state(&info(&client, id)),
        (10, 0, 102, 110, true, 0)
    );
    at(&env, 103);
    assert_eq!(client.settle_stream(&id), 0);
    assert_eq!(
        economic_state(&info(&client, id)),
        (10, 0, 103, 110, true, 0)
    );
    client.stop_stream(&id);
    assert_eq!(
        economic_state(&info(&client, id)),
        (10, 0, 103, 103, false, 0)
    );

    // An amount-zero batch at the configured end must still naturalize a
    // stream whose balance was exhausted earlier.
    let env = Env::default();
    let (_, client) = contract(&env);
    let id = create_started(&env, &client, 100, 10, 15, 110);
    at(&env, 102);
    assert_eq!(client.settle_stream(&id), 15);
    assert_eq!(
        economic_state(&info(&client, id)),
        (10, 0, 102, 110, true, 0)
    );
    at(&env, 110);
    assert_eq!(client.batch_settle(&ids(&env, &[id])).get(0).unwrap(), 0);
    assert_eq!(
        economic_state(&info(&client, id)),
        (10, 0, 110, 110, false, 0)
    );

    // Exact end.
    let env = Env::default();
    let (_, client) = contract(&env);
    let id = create_started(&env, &client, 100, 10, 20, 102);
    at(&env, 102);
    assert_eq!(client.settle_stream(&id), 20);
    assert_eq!(
        economic_state(&info(&client, id)),
        (10, 0, 102, 102, false, 0)
    );

    // Pause itself can exhaust the balance while leaving a resumable stream.
    let env = Env::default();
    let (_, client) = contract(&env);
    let id = create_started(&env, &client, 100, 10, 15, 110);
    at(&env, 102);
    client.pause_stream(&id);
    let exhausted_pause = info(&client, id);
    assert_eq!(
        economic_state(&exhausted_pause),
        (10, 0, 102, 110, true, 102)
    );
    assert_eq!(client.settle_stream(&id), 0);
    assert_stream_fields_eq(&exhausted_pause, &info(&client, id));
    at(&env, 105);
    client.resume_stream(&id);
    assert_eq!(
        economic_state(&info(&client, id)),
        (10, 0, 105, 110, true, 0)
    );
    at(&env, 107);
    assert_eq!(client.settle_stream(&id), 0);
    assert_eq!(
        economic_state(&info(&client, id)),
        (10, 0, 107, 110, true, 0)
    );
    at(&env, 110);
    assert_eq!(client.settle_stream(&id), 0);
    assert_eq!(
        economic_state(&info(&client, id)),
        (10, 0, 110, 110, false, 0)
    );

    // Pause, resume, then exhaust the remainder.
    let env = Env::default();
    let (_, client) = contract(&env);
    let id = create_started(&env, &client, 100, 10, 15, 110);
    at(&env, 101);
    client.pause_stream(&id);
    assert_eq!(info(&client, id).balance, 5);
    at(&env, 102);
    client.resume_stream(&id);
    at(&env, 103);
    assert_eq!(client.settle_stream(&id), 5);
    assert_eq!(
        economic_state(&info(&client, id)),
        (10, 0, 103, 110, true, 0)
    );

    // Batch, cancel and stop each cap at the remaining balance.
    for action in ["batch", "cancel", "stop"] {
        let env = Env::default();
        let (_, client) = contract(&env);
        let id = create_started(&env, &client, 100, 10, 15, 110);
        at(&env, 102);
        match action {
            "batch" => assert_eq!(client.batch_settle(&ids(&env, &[id])).get(0).unwrap(), 15),
            "cancel" => client.cancel_stream(&id),
            "stop" => client.stop_stream(&id),
            _ => unreachable!(),
        }
        let exhausted = info(&client, id);
        if action == "batch" {
            assert_eq!(economic_state(&exhausted), (10, 0, 102, 110, true, 0));
        } else {
            assert_eq!(economic_state(&exhausted), (10, 0, 102, 102, false, 0));
        }
        at(&env, 109);
        assert_eq!(client.settle_stream(&id), 0, "{action}");
        if action == "batch" {
            assert_eq!(
                economic_state(&info(&client, id)),
                (10, 0, 109, 110, true, 0)
            );
        } else {
            assert_stream_fields_eq(&exhausted, &info(&client, id));
        }
    }
}

fn wrong_actor_call_is_rejected(
    env: &Env,
    contract_id: &Address,
    client: &StreamPayContractClient<'_>,
    stream_id: u32,
    fn_name: &'static str,
) {
    let wrong = Address::generate(env);
    let invoke = MockAuthInvoke {
        contract: contract_id,
        fn_name,
        args: (stream_id,).into_val(env),
        sub_invokes: &[],
    };
    let auth = MockAuth {
        address: &wrong,
        invoke: &invoke,
    };
    let auths = [auth];
    let mocked = client.mock_auths(&auths);
    assert_rejected_stream_fields_unchanged(client, stream_id, || match fn_name {
        "pause_stream" => mocked.pause_stream(&stream_id),
        "resume_stream" => mocked.resume_stream(&stream_id),
        "cancel_stream" => mocked.cancel_stream(&stream_id),
        "stop_stream" => mocked.stop_stream(&stream_id),
        _ => unreachable!(),
    });
}

fn correct_payer_call_succeeds(
    env: &Env,
    contract_id: &Address,
    client: &StreamPayContractClient<'_>,
    stream_id: u32,
    fn_name: &'static str,
) {
    let payer = info(client, stream_id).payer;
    let invoke = MockAuthInvoke {
        contract: contract_id,
        fn_name,
        args: (stream_id,).into_val(env),
        sub_invokes: &[],
    };
    let auth = MockAuth {
        address: &payer,
        invoke: &invoke,
    };
    let auths = [auth];
    let mocked = client.mock_auths(&auths);
    match fn_name {
        "pause_stream" => mocked.pause_stream(&stream_id),
        "resume_stream" => mocked.resume_stream(&stream_id),
        "cancel_stream" => mocked.cancel_stream(&stream_id),
        "stop_stream" => mocked.stop_stream(&stream_id),
        _ => unreachable!(),
    }
}

#[test]
fn h8_explicit_correct_payer_mock_auth_succeeds_for_every_payer_only_path() {
    let env = Env::default();
    let (contract_id, client) = contract(&env);
    let id = create_started(&env, &client, 100, 1, 100, 110);
    at(&env, 101);
    correct_payer_call_succeeds(&env, &contract_id, &client, id, "pause_stream");
    let paused = info(&client, id);
    assert_eq!(paused.balance, 99);
    assert_eq!(paused.paused_at, 101);
    assert!(paused.is_active);

    at(&env, 102);
    correct_payer_call_succeeds(&env, &contract_id, &client, id, "resume_stream");
    let resumed = info(&client, id);
    assert_eq!(resumed.balance, 99);
    assert_eq!(resumed.start_time, 102);
    assert_eq!(resumed.paused_at, 0);
    assert!(resumed.is_active);

    for fn_name in ["cancel_stream", "stop_stream"] {
        let env = Env::default();
        let (contract_id, client) = contract(&env);
        let id = create_started(&env, &client, 100, 1, 100, 110);
        at(&env, 101);
        correct_payer_call_succeeds(&env, &contract_id, &client, id, fn_name);
        let terminal = info(&client, id);
        assert_eq!(terminal.balance, 99, "{fn_name}");
        assert_eq!(terminal.start_time, 101, "{fn_name}");
        assert_eq!(terminal.end_time, 101, "{fn_name}");
        assert_eq!(terminal.paused_at, 0, "{fn_name}");
        assert!(!terminal.is_active, "{fn_name}");
    }
}

#[test]
fn h8_wrong_actor_and_no_auth_leave_stream_fields_unchanged() {
    for fn_name in ["pause_stream", "cancel_stream", "stop_stream"] {
        let env = Env::default();
        let (contract_id, client) = contract(&env);
        let id = create_started(&env, &client, 100, 1, 100, 110);
        wrong_actor_call_is_rejected(&env, &contract_id, &client, id, fn_name);

        env.set_auths(&[]);
        assert_rejected_stream_fields_unchanged(&client, id, || match fn_name {
            "pause_stream" => client.pause_stream(&id),
            "cancel_stream" => client.cancel_stream(&id),
            "stop_stream" => client.stop_stream(&id),
            _ => unreachable!(),
        });
    }

    let env = Env::default();
    let (contract_id, client) = contract(&env);
    let id = create_started(&env, &client, 100, 1, 100, 110);
    at(&env, 101);
    client.pause_stream(&id);
    wrong_actor_call_is_rejected(&env, &contract_id, &client, id, "resume_stream");
    env.set_auths(&[]);
    assert_rejected_stream_fields_unchanged(&client, id, || client.resume_stream(&id));
}

#[test]
fn h8_lifecycle_and_missing_failures_are_atomic_permissionless_settle_survives() {
    // Lifecycle controls for already-paused/not-paused rejection.
    let env = Env::default();
    let (_, client) = contract(&env);
    let active = create_started(&env, &client, 100, 1, 100, 110);
    assert_rejected_stream_fields_unchanged(&client, active, || client.resume_stream(&active));
    at(&env, 101);
    client.pause_stream(&active);
    assert_rejected_stream_fields_unchanged(&client, active, || client.pause_stream(&active));
    client.resume_stream(&active);

    // All payer-only paths reject a terminal stream without partial mutation.
    client.stop_stream(&active);
    for fn_name in ["pause", "resume", "cancel", "stop"] {
        assert_rejected_stream_fields_unchanged(&client, active, || match fn_name {
            "pause" => client.pause_stream(&active),
            "resume" => client.resume_stream(&active),
            "cancel" => client.cancel_stream(&active),
            "stop" => client.stop_stream(&active),
            _ => unreachable!(),
        });
    }

    // Missing-id failures do not mutate any persisted StreamInfo field of an
    // unrelated stream. Events and TTL are outside this fieldwise assertion.
    let sentinel = create_started(&env, &client, 102, 1, 100, 0);
    for fn_name in ["pause", "resume", "cancel", "stop"] {
        let before = info(&client, sentinel);
        let rejected = catch_unwind(AssertUnwindSafe(|| match fn_name {
            "pause" => client.pause_stream(&999_999),
            "resume" => client.resume_stream(&999_999),
            "cancel" => client.cancel_stream(&999_999),
            "stop" => client.stop_stream(&999_999),
            _ => unreachable!(),
        }));
        assert!(rejected.is_err());
        assert_stream_fields_eq(&before, &info(&client, sentinel));
    }

    // Settlement and batch settlement intentionally remain permissionless.
    at(&env, 104);
    env.set_auths(&[]);
    assert_eq!(client.settle_stream(&sentinel), 2);
    at(&env, 105);
    assert_eq!(
        client.batch_settle(&ids(&env, &[sentinel])).get(0).unwrap(),
        1
    );
}

#[test]
fn h9_extremes_and_metamorphic_equivalences() {
    // Small balance/high rate and i128 saturation preserve the balance cap.
    for rate in [10_i128, i128::MAX] {
        let env = Env::default();
        let (_, client) = contract(&env);
        let id = create_started(&env, &client, 100, rate, 15, 110);
        at(&env, 102);
        assert_eq!(client.settle_stream(&id), 15);
        assert_eq!(info(&client, id).balance, 0);
        assert_eq!(client.settle_stream(&id), 0);
    }

    // u64::MAX observation respects the absolute bounded end.
    let env = Env::default();
    let (_, client) = contract(&env);
    let id = create_started(&env, &client, 100, 3, 1_000, 110);
    at(&env, u64::MAX);
    assert_eq!(client.settle_stream(&id), 30);
    assert_eq!(info(&client, id).balance, 970);
    assert!(!info(&client, id).is_active);

    // A bounded stream and an unlimited stream have equivalent prefixes when
    // the observation is before the configured end.
    let env = Env::default();
    let (_, client) = contract(&env);
    let bounded = create_started(&env, &client, 100, 7, 1_000, 200);
    let unlimited = create_started(&env, &client, 100, 7, 1_000, 0);
    at(&env, 150);
    assert_eq!(client.settle_stream(&bounded), 350);
    assert_eq!(client.settle_stream(&unlimited), 350);
    assert_eq!(
        info(&client, bounded).balance,
        info(&client, unlimited).balance
    );

    // Split settlement and one-shot settlement account for the same union of
    // active time intervals; repeated calls in the same ledger add zero.
    let env = Env::default();
    let (_, client) = contract(&env);
    let split = create_started(&env, &client, 100, 7, 1_000, 200);
    at(&env, 120);
    let split_a = client.settle_stream(&split);
    assert_eq!(client.settle_stream(&split), 0);
    at(&env, 150);
    let split_b = client.settle_stream(&split);
    let split_state = economic_state(&info(&client, split));

    let env = Env::default();
    let (_, client) = contract(&env);
    let once = create_started(&env, &client, 100, 7, 1_000, 200);
    at(&env, 150);
    let once_amount = client.settle_stream(&once);
    let once_state = economic_state(&info(&client, once));
    assert_eq!(split_a + split_b, once_amount);
    assert_eq!(once_amount, 350);
    assert_eq!(split_state, once_state);
}

/// H10 passing witness: natural-end terminalization can leave retained value
/// that is neither restartable nor archivable under the current API. This is
/// recorded as an OUT_OF_SCOPE_WATCHPOINT, not as an issue #153 production-fix
/// requirement.
#[test]
fn h10_natural_end_retained_balance_is_an_out_of_scope_archive_watchpoint() {
    let env = Env::default();
    let (_, client) = contract(&env);
    let id = create_started(&env, &client, 100, 1, 100, 110);

    at(&env, 110);
    assert_eq!(client.settle_stream(&id), 10);
    let terminal = info(&client, id);
    assert_eq!(terminal.balance, 90);
    assert_eq!(terminal.start_time, 110);
    assert_eq!(terminal.end_time, 110);
    assert!(!terminal.is_active);
    assert_eq!(terminal.paused_at, 0);

    assert_eq!(client.settle_stream(&id), 0);
    assert_stream_fields_eq(&terminal, &info(&client, id));
    assert_rejected_stream_fields_unchanged(&client, id, || client.start_stream(&id));
    assert_rejected_stream_fields_unchanged(&client, id, || client.archive_stream(&id));
}
