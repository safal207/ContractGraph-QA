"""Probe self-tests, not substitutes for the workflow's real pinned subjects."""
import asyncio
import concurrent.futures as cf
import contextlib
import io
import sys
import unittest
from unittest.mock import patch

from tools import langgraph_ordering_barrier_probe as probe


class SyncOrdering:
    barrier = "_pending_write_futs"
    propagate = False

    def put_writes(self, task_id, writes):
        self.ordinary = self.submit(self.checkpointer_put_writes, self.config, writes, task_id)
        if self.barrier:
            if not hasattr(self, self.barrier):
                setattr(self, self.barrier, [])
            getattr(self, self.barrier).append(self.ordinary)

    def _checkpointer_put_after_previous(self, prev, config, *args):
        if self.barrier:
            pending = getattr(self, self.barrier)
            cf.wait(pending)
            if self.propagate:
                for future in pending:
                    future.result()
        self.checkpointer.put(config, *args)


class SyncFixed(SyncOrdering):
    propagate = True


class SyncUnordered(SyncOrdering):
    barrier = None


class AsyncOrdering(SyncOrdering):
    async def _checkpointer_put_after_previous(self, prev, config, *args):
        if self.barrier:
            await asyncio.gather(*getattr(self, self.barrier))
        await self.checkpointer.aput(config, *args)


class AsyncUnordered(AsyncOrdering):
    barrier = None


class SyncDirect(SyncUnordered):
    def _checkpointer_put_after_previous(self, prev, config, *args):
        self.ordinary.result()
        self.checkpointer.put(config, *args)


class AsyncDirect(AsyncUnordered):
    async def _checkpointer_put_after_previous(self, prev, config, *args):
        await self.ordinary
        await self.checkpointer.aput(config, *args)


class ProbeTests(unittest.TestCase):
    def test_unordered_is_red_per_case(self):
        result = probe._results(SyncUnordered, AsyncUnordered)
        self.assertEqual(result["verdict"], "RED")
        self.assertEqual(list(result["checks"].values()), [False, False])
        self.assertEqual(list(result["failure_propagation"]["checks"].values()), [False, False])
        for case in result["evidence"].values():
            self.assertFalse(case["saver_entries"][0]["ordinary_write_drained"])

    def test_wait_only_orders_but_does_not_propagate_failure(self):
        result = probe._results(SyncOrdering, AsyncOrdering)
        self.assertEqual(result["verdict"], "GREEN")
        self.assertEqual(list(result["failure_propagation"]["checks"].values()), [False, True])
        failed = result["failure_propagation"]["evidence"]["sync"]
        self.assertEqual(failed["submitted_future_count"], 1)
        self.assertTrue(failed["write_failed"])
        self.assertEqual(len(failed["saver_entries"]), 1)
        self.assertFalse(failed["original_write_error_propagated"])

    def test_result_correction_passes_both_axes(self):
        result = probe._results(SyncFixed, AsyncOrdering)
        self.assertEqual(result["verdict"], "GREEN")
        self.assertEqual(result["failure_propagation"]["verdict"], "GREEN")
        for case in result["failure_propagation"]["evidence"].values():
            self.assertEqual(case["saver_entries"], [])
            self.assertTrue(case["original_write_error_propagated"])

    def test_direct_await_and_result_need_no_registered_barrier(self):
        result = probe._results(SyncDirect, AsyncDirect)
        self.assertEqual(result["verdict"], "GREEN")
        self.assertEqual(result["failure_propagation"]["verdict"], "GREEN")
        self.assertFalse(result["diagnostics"]["ordinary_future_registered"])
        self.assertFalse(result["diagnostics"]["registered_in_same_sync_and_async_barrier"])

    def test_renamed_and_different_barriers_do_not_change_verdict(self):
        class SyncRenamed(SyncFixed):
            barrier = "_ordinary_futures"
        class AsyncRenamed(AsyncOrdering):
            barrier = "_other_pending_futures"
        result = probe._results(SyncRenamed, AsyncRenamed)
        self.assertEqual(result["verdict"], "GREEN")
        self.assertEqual(result["failure_propagation"]["verdict"], "GREEN")
        self.assertFalse(result["diagnostics"]["ordinary_future_registered"])

    def test_sync_inline_write_is_not_false_red(self):
        class Inline(SyncUnordered):
            def put_writes(self, task_id, writes):
                self.checkpointer_put_writes(self.config, writes, task_id)
        self.assertTrue(probe._sync_case(Inline)["passed"])
        self.assertTrue(probe._sync_case(Inline, fail=True)["passed"])

    def test_absent_saver_entry_is_not_vacuous_ordering_green(self):
        class NoPut(SyncDirect):
            def _checkpointer_put_after_previous(self, prev, config, *args):
                self.ordinary.result()
        self.assertFalse(probe._sync_case(NoPut)["passed"])

    def test_waiting_for_unrelated_future_is_not_green(self):
        class WrongWait(SyncUnordered):
            def _checkpointer_put_after_previous(self, prev, config, *args):
                other = cf.Future()
                other.set_result(None)
                cf.wait([other])
                self.checkpointer.put(config, *args)
        self.assertFalse(probe._sync_case(WrongWait)["passed"])

    def test_swallowing_original_failure_is_not_green(self):
        class Swallow(SyncDirect):
            def _checkpointer_put_after_previous(self, prev, config, *args):
                try:
                    self.ordinary.result()
                except probe.WriteFailure:
                    pass
        self.assertFalse(probe._sync_case(Swallow, fail=True)["passed"])

    def test_unexpected_exception_is_harness_error_not_red(self):
        class Broken(SyncUnordered):
            def _checkpointer_put_after_previous(self, *args):
                raise ValueError("unsupported fixture")
        with self.assertRaises(probe.HarnessError):
            probe._sync_case(Broken)

    def test_cli_enforces_each_case_not_just_aggregate_red(self):
        result = probe._results(SyncUnordered, AsyncOrdering)
        with patch.object(probe, "run_probe", return_value=result), \
                patch.object(sys, "argv", ["probe", "--expect", "red"]), \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(probe.main(), 1)

    def test_cli_harness_error_cannot_satisfy_expected_red(self):
        with patch.object(probe, "run_probe", side_effect=probe.HarnessError("watchdog")), \
                patch.object(sys, "argv", ["probe", "--expect", "red"]), \
                contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(probe.main(), 2)
        self.assertIn('"verdict": "ERROR"', output.getvalue())


if __name__ == "__main__":
    unittest.main()
