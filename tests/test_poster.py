import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from PIL import Image

BASE = "https://graph.instagram.com/v23.0"


def _ok(payload):
    response = Mock(status_code=200)
    response.json.return_value = payload
    return response


class PosterTests(unittest.TestCase):
    def setUp(self):
        self.original_token = os.environ.get("INSTAGRAM_ACCESS_TOKEN")
        os.environ["INSTAGRAM_ACCESS_TOKEN"] = "  test-token  "
        import poster
        self.poster = importlib.reload(poster)

    def tearDown(self):
        if self.original_token is None:
            os.environ.pop("INSTAGRAM_ACCESS_TOKEN", None)
        else:
            os.environ["INSTAGRAM_ACCESS_TOKEN"] = self.original_token

    def test_validate_account_accepts_expected_username(self):
        response = _ok({"user_id": "1784", "username": "examplecreator"})
        with patch.object(self.poster.requests, "get", return_value=response) as get:
            account = self.poster.validate_account("@examplecreator", BASE)
        self.assertEqual(account, {"user_id": "1784", "username": "examplecreator"})
        get.assert_called_once_with(
            f"{BASE}/me",
            params={"fields": "user_id,username,account_type", "access_token": "test-token"},
            timeout=30,
        )

    def test_validate_account_rejects_wrong_username(self):
        response = _ok({"user_id": "1784", "username": "wrongaccount"})
        with patch.object(self.poster.requests, "get", return_value=response):
            with self.assertRaisesRegex(RuntimeError, "not the expected Instagram account @examplecreator"):
                self.poster.validate_account("examplecreator", BASE)

    def test_api_error_does_not_expose_token(self):
        response = Mock(status_code=400, text='{"error":"bad token test-token"}')
        with patch.object(self.poster.requests, "get", return_value=response):
            with self.assertRaisesRegex(RuntimeError, r"Instagram authentication check failed \(HTTP 400\)") as error:
                self.poster.validate_account("examplecreator", BASE)
        self.assertNotIn("test-token", str(error.exception))

    def test_facebook_token_uses_graph_facebook_and_config_user_id(self):
        os.environ["INSTAGRAM_ACCESS_TOKEN"] = "EAAtest"
        self.assertEqual(self.poster.base_url_for({}), "https://graph.facebook.com/v23.0")
        response = _ok({"id": "1784", "username": "examplecreator"})
        with patch.object(self.poster.requests, "get", return_value=response) as get:
            account = self.poster.validate_account(
                "examplecreator", "https://graph.facebook.com/v23.0", user_id="1784")
        self.assertEqual(account["user_id"], "1784")
        self.assertEqual(get.call_args.args[0], "https://graph.facebook.com/v23.0/1784")

    def test_instagram_token_uses_graph_instagram(self):
        os.environ["INSTAGRAM_ACCESS_TOKEN"] = "IGAAtest"
        self.assertEqual(self.poster.base_url_for({}), BASE)

    def test_whitespace_token_fails_before_network(self):
        os.environ["INSTAGRAM_ACCESS_TOKEN"] = "   "
        with patch.object(self.poster.requests, "get") as get:
            with self.assertRaisesRegex(RuntimeError, "INSTAGRAM_ACCESS_TOKEN is missing or empty"):
                self.poster.validate_account("examplecreator", BASE)
        get.assert_not_called()

    def test_post_carousel_creates_children_then_carousel_then_publishes(self):
        posts = [_ok({"id": "c1"}), _ok({"id": "c2"}), _ok({"id": "carousel"}), _ok({"id": "media-9"})]
        with (
            patch.object(self.poster.requests, "post", side_effect=posts) as post,
            patch.object(self.poster.requests, "get", return_value=_ok({"status_code": "FINISHED"})),
        ):
            media_id = self.poster.post_carousel(BASE, "1784", "Caption", ["https://img/1.jpg", "https://img/2.jpg"])
        self.assertEqual(media_id, "media-9")
        calls = post.call_args_list
        self.assertEqual(calls[0].args[0], f"{BASE}/1784/media")
        self.assertEqual(calls[0].kwargs["data"]["image_url"], "https://img/1.jpg")
        self.assertEqual(calls[0].kwargs["data"]["is_carousel_item"], "true")
        self.assertEqual(calls[2].kwargs["data"]["media_type"], "CAROUSEL")
        self.assertEqual(calls[2].kwargs["data"]["children"], "c1,c2")
        self.assertEqual(calls[3].args[0], f"{BASE}/1784/media_publish")
        self.assertEqual(calls[3].kwargs["data"]["creation_id"], "carousel")

    def test_caption_limited_to_five_hashtags(self):
        posts = [_ok({"id": "c1"}), _ok({"id": "c2"}), _ok({"id": "carousel"}), _ok({"id": "m"})]
        caption = "News #A #B #C #D #E #F #G"
        with (
            patch.object(self.poster.requests, "post", side_effect=posts) as post,
            patch.object(self.poster.requests, "get", return_value=_ok({"status_code": "FINISHED"})),
        ):
            self.poster.post_carousel(BASE, "1784", caption, ["https://img/1.jpg", "https://img/2.jpg"])
        posted = post.call_args_list[2].kwargs["data"]["caption"]
        self.assertEqual(posted.count("#"), 5)
        self.assertNotIn("#F", posted)

    def test_carousel_needs_two_to_ten_images(self):
        with self.assertRaises(ValueError):
            self.poster.post_carousel(BASE, "1784", "Caption", ["https://img/1.jpg"])

    def test_wait_until_ready_polls_then_finishes(self):
        responses = [_ok({"status_code": "IN_PROGRESS"}), _ok({"status_code": "FINISHED"})]
        with (
            patch.object(self.poster.requests, "get", side_effect=responses),
            patch.object(self.poster.time, "sleep"),
        ):
            self.poster.wait_until_ready(BASE, "c1", timeout=30, poll_interval=1)

    def test_wait_until_ready_raises_on_error(self):
        with patch.object(self.poster.requests, "get", return_value=_ok({"status_code": "ERROR", "status": "bad image"})):
            with self.assertRaisesRegex(RuntimeError, "bad image"):
                self.poster.wait_until_ready(BASE, "c1", timeout=30, poll_interval=1)


class HostingTests(unittest.TestCase):
    def test_pngs_become_jpegs(self):
        import hosting
        with tempfile.TemporaryDirectory() as directory:
            png = Path(directory) / "slide_01.png"
            Image.new("RGBA", (10, 10), (0, 255, 0, 255)).save(png)
            jpgs = hosting.to_jpegs([str(png)], Path(directory) / "out")
            self.assertEqual(jpgs[0].suffix, ".jpg")
            self.assertEqual(Image.open(jpgs[0]).format, "JPEG")


if __name__ == "__main__":
    unittest.main()
