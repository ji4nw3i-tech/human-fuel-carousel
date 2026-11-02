import os
import unittest

import config_check


READY = {
    "account_handle": "@examplecreator",
    "community_name": "Example News",
    "community_url": "example.com/join",
    "comment_keyword": "NEWS",
    "instagram": {"username": "examplecreator"},
}

PLACEHOLDER = {
    **READY,
    "comment_keyword": "YOUR_COMMENT_KEYWORD",
    "instagram": {"username": "YOUR_INSTAGRAM_USERNAME"},
}


class ConfigCheckTests(unittest.TestCase):
    def test_placeholders_are_reported(self):
        fields = config_check.placeholder_fields(PLACEHOLDER)
        self.assertIn("instagram.username", fields)
        self.assertIn("comment_keyword", fields)

    def test_filled_config_is_ready(self):
        self.assertEqual(config_check.placeholder_fields(READY), [])

    def test_config_on_disk_is_ready(self):
        self.assertEqual(config_check.placeholder_fields(config_check.load_config()), [])

    def test_missing_instagram_block_blocks_posting(self):
        cfg = {k: v for k, v in READY.items() if k != "instagram"}
        self.assertIn("instagram.username", config_check.placeholder_fields(cfg))

    def test_scheduled_fresh_copy_skips_instead_of_failing(self):
        original = os.environ.get("GITHUB_EVENT_NAME")
        os.environ["GITHUB_EVENT_NAME"] = "schedule"
        try:
            self.assertEqual(config_check.guard_unconfigured(PLACEHOLDER), "skip")
            self.assertIsNone(config_check.guard_unconfigured(READY))
        finally:
            if original is None:
                os.environ.pop("GITHUB_EVENT_NAME", None)
            else:
                os.environ["GITHUB_EVENT_NAME"] = original

    def test_manual_run_fails_while_placeholders_remain(self):
        original = os.environ.pop("GITHUB_EVENT_NAME", None)
        try:
            self.assertEqual(config_check.guard_unconfigured(PLACEHOLDER), "fail")
        finally:
            if original is not None:
                os.environ["GITHUB_EVENT_NAME"] = original


if __name__ == "__main__":
    unittest.main()
