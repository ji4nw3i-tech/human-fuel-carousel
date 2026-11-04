import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import cashflowos
import logger
import pipeline


class CashflowOSTests(unittest.TestCase):
    def setUp(self):
        self.saved = {k: os.environ.get(k) for k in ("CASHFLOWOS_URL", "CONTENT_SECRET")}

    def tearDown(self):
        for k, v in self.saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_disabled_without_url_or_secret(self):
        os.environ["CASHFLOWOS_URL"] = "https://app.example"
        os.environ.pop("CONTENT_SECRET", None)
        self.assertFalse(cashflowos.enabled())

    def test_propose_sends_secret_header_and_brand(self):
        os.environ["CASHFLOWOS_URL"] = "https://app.example/"
        os.environ["CONTENT_SECRET"] = "s3cret"
        ok = Mock(status_code=200)
        ok.json.return_value = {"action_id": 7}
        with patch.object(cashflowos.requests, "post", return_value=ok) as post:
            cashflowos.propose("20261104_1237_global_topic", {"headline": "H", "url": "u"}, "Cap", ["a", "b"])
        self.assertEqual(post.call_args.args[0], "https://app.example/api/content/propose")
        self.assertEqual(post.call_args.kwargs["headers"], {"x-content-secret": "s3cret"})
        body = post.call_args.kwargs["json"]
        self.assertEqual(body["brand"], "human-fuel")
        self.assertEqual(body["image_urls"], ["a", "b"])

    def test_report_never_raises(self):
        os.environ["CASHFLOWOS_URL"] = "https://app.example"
        os.environ["CONTENT_SECRET"] = "s3cret"
        with patch.object(cashflowos.requests, "post", side_effect=OSError("down")):
            cashflowos.report("failed", error="boom")


class PublishTests(unittest.TestCase):
    def test_rejects_bad_run_id(self):
        with self.assertRaises(ValueError):
            pipeline.publish("../../etc")

    def test_skips_already_posted_run(self):
        with tempfile.TemporaryDirectory() as d:
            log = Path(d) / "posted_urls.json"
            log.write_text(json.dumps({"posts": [{"run_id": "20261104_1237_global_topic"}]}))
            with patch.object(logger, "_LOG_FILE", log), patch.object(pipeline.poster, "run") as post:
                pipeline.publish("20261104_1237_global_topic")
            post.assert_not_called()

    def test_mark_proposed_reserves_story(self):
        with tempfile.TemporaryDirectory() as d:
            log = Path(d) / "posted_urls.json"
            with patch.object(logger, "_LOG_FILE", log):
                logger.mark_proposed({"url": "https://x"}, {"https://img"})
                self.assertIn("https://x", logger.get_posted_urls())
                self.assertIn("https://img", logger.get_used_img_urls())
                self.assertFalse(logger.was_posted("20261104_1237_global_topic"))


if __name__ == "__main__":
    unittest.main()
