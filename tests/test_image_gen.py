import importlib
import os
import tempfile
import unittest
from unittest.mock import patch


class ImageGenerationFallbackTests(unittest.TestCase):
    def setUp(self):
        os.environ.pop("PEXELS_API_KEY", None)
        os.environ.pop("PIXABAY_API_KEY", None)
        import image_gen
        self.image_gen = importlib.reload(image_gen)

    def test_gemini_fallback_is_not_part_of_the_pipeline(self):
        self.assertFalse(hasattr(self.image_gen, "GEMINI_API_KEY"))
        self.assertFalse(hasattr(self.image_gen, "_generate_gemini_image"))

    def test_records_gradient_sources_when_pexels_fails(self):
        with tempfile.TemporaryDirectory() as output_dir:
            with (
                patch.object(self.image_gen, "_fetch_pexels", return_value=(None, "")),
                patch.object(self.image_gen, "_fetch_pixabay", return_value=(None, "")),
                patch.object(self.image_gen, "_gradient_fallback") as gradient,
            ):
                paths, urls, sources = self.image_gen.generate_slide_images({}, output_dir)

        self.assertEqual(len(paths), 10)
        self.assertEqual(urls, set())
        self.assertEqual(sources, ["gradient"] * 10)
        self.assertEqual(gradient.call_count, 10)

    def test_pixabay_used_when_pexels_has_no_key(self):
        with tempfile.TemporaryDirectory() as output_dir:
            with (
                patch.object(self.image_gen, "_fetch_pexels", return_value=(None, "")),
                patch.object(self.image_gen, "_fetch_pixabay",
                             side_effect=[(b"img", f"https://pixabay.example/{i}.jpg") for i in range(10)]),
                patch.object(self.image_gen, "_crop_and_resize"),
            ):
                paths, urls, sources = self.image_gen.generate_slide_images({}, output_dir)

        self.assertEqual(sources, ["pixabay"] * 10)
        self.assertEqual(len(urls), 10)


if __name__ == "__main__":
    unittest.main()
