from __future__ import annotations

import os
import stat
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from contractgraph_qa.tsse_adapters import common


class TSSEInputLimitTest(unittest.TestCase):
    def test_read_is_bounded_using_the_opened_file_metadata(self) -> None:
        opened = mock.mock_open(read_data=b"data")
        metadata = SimpleNamespace(st_mode=stat.S_IFREG, st_size=4)
        with mock.patch("builtins.open", opened), mock.patch.object(
            common.os, "fstat", return_value=metadata
        ) as fstat:
            self.assertEqual(
                common._read_limited(Path("capture.json"), maximum=4, field="capture"),
                b"data",
            )
        self.assertEqual(opened.call_count, 1)
        fstat.assert_called_once_with(opened().fileno())
        opened().read.assert_called_once_with(5)

    def test_growth_past_the_limit_is_rejected_after_a_bounded_read(self) -> None:
        opened = mock.mock_open(read_data=b"extra")
        metadata = SimpleNamespace(st_mode=stat.S_IFREG, st_size=0)
        with mock.patch("builtins.open", opened), mock.patch.object(
            common.os, "fstat", return_value=metadata
        ):
            with self.assertRaisesRegex(common.ToolCaptureError, "4-byte input limit"):
                common._read_limited(Path("capture.json"), maximum=4, field="capture")
        opened().read.assert_called_once_with(5)

    def test_known_oversized_input_is_not_read(self) -> None:
        opened = mock.mock_open()
        metadata = SimpleNamespace(st_mode=stat.S_IFREG, st_size=5)
        with mock.patch("builtins.open", opened), mock.patch.object(
            common.os, "fstat", return_value=metadata
        ):
            with self.assertRaisesRegex(common.ToolCaptureError, "4-byte input limit"):
                common._read_limited(Path("capture.json"), maximum=4, field="capture")
        opened().read.assert_not_called()

    def test_nonregular_input_is_rejected_before_reading(self) -> None:
        opened = mock.mock_open()
        metadata = SimpleNamespace(st_mode=stat.S_IFIFO, st_size=0)
        with mock.patch("builtins.open", opened), mock.patch.object(
            common.os, "fstat", return_value=metadata
        ):
            with self.assertRaisesRegex(common.ToolCaptureError, "not a regular file"):
                common._read_limited(Path("capture.json"), maximum=4, field="capture")
        opened().read.assert_not_called()

    def test_opener_requests_nonblocking_mode_when_available(self) -> None:
        opened = mock.mock_open(read_data=b"data")
        metadata = SimpleNamespace(st_mode=stat.S_IFREG, st_size=4)
        nonblocking_flag = 0x100000
        with mock.patch("builtins.open", opened), mock.patch.object(
            common.os, "fstat", return_value=metadata
        ), mock.patch.object(common.os, "O_NONBLOCK", nonblocking_flag, create=True):
            common._read_limited(Path("capture.json"), maximum=4, field="capture")
            opener = opened.call_args.kwargs["opener"]
            with mock.patch.object(common.os, "open", return_value=7) as os_open:
                self.assertEqual(opener("capture.json", os.O_RDONLY), 7)
            os_open.assert_called_once_with(
                "capture.json", os.O_RDONLY | nonblocking_flag
            )


if __name__ == "__main__":
    unittest.main()
