from __future__ import annotations

import unittest
from unittest import mock

from app import fetcher
from app.workers import FetchWorker

VALID_URL = ("https://data.lroc.im-ldi.com/lroc/view_lroc/"
             "LRO-L-LROC-3-CDR-V1.0/M190737496RC")


class FetchWorkerTest(unittest.TestCase):
    @mock.patch("app.fetcher.fetch_metadata")
    def test_success_emits_dict(self, fetch):
        fetch.return_value = {"product_id": "M190737496RE"}
        worker = FetchWorker(VALID_URL)
        received: dict = {}
        worker.succeeded.connect(received.update)
        worker.run()
        self.assertEqual(received, {"product_id": "M190737496RE"})
        fetch.assert_called_once_with(VALID_URL)

    @mock.patch("app.fetcher.fetch_metadata")
    def test_fetch_error_emits_message(self, fetch):
        fetch.side_effect = fetcher.FetchError("取得に失敗しました (HTTP 404)。")
        worker = FetchWorker(VALID_URL)
        messages: list[str] = []
        worker.failed.connect(messages.append)
        worker.run()
        self.assertEqual(messages, ["取得に失敗しました (HTTP 404)。"])

    def test_invalid_url_emits_message_without_network(self):
        worker = FetchWorker("https://example.com/lroc/view_lroc/DS")
        messages: list[str] = []
        worker.failed.connect(messages.append)
        worker.run()
        self.assertEqual(len(messages), 1)
        self.assertIn("URL", messages[0])

    def test_signals_do_not_shadow_qthread_builtins(self):
        self.assertTrue(hasattr(FetchWorker, "succeeded"))
        self.assertTrue(hasattr(FetchWorker, "failed"))
        self.assertNotIn("finished", FetchWorker.__dict__)
