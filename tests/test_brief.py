import os
import unittest
from unittest.mock import patch

os.environ.setdefault("ANTHROPIC_API_KEY", "test")
import selector  # noqa: E402

STORY = {
    "headline": "NCDs claim 96,000 lives yearly",
    "summary": "",
    "raw_text": "One in six adults has diabetes; 1 in 3 has high blood pressure. RM25 million collected in 2024.",
    "published_at": "2026-11-02",
    "source": "The Vibes",
}


def carousel(**overrides):
    base = {
        "cover_headline": "**96,000** Malaysians\nA Year — What Can\nFamilies Do?",
        "slides": [{"num": n, "headline": "1 in 3 adults has high blood pressure", "insight": "Short."}
                   for n in range(2, 7)],
        "sources": ["Ministry of Health Malaysia, 2026 (reported by The Vibes)"],
        "caption": "Hook\n\nSources: MOH 2026\n\n#thehumanfuel #farmacy #naturalfarming #eatrealfood #malaysia",
    }
    base.update(overrides)
    return base


class BriefRuleTests(unittest.TestCase):
    def test_valid_carousel_passes(self):
        selector._check_carousel(STORY, carousel())

    def test_spelled_out_source_number_counts(self):
        slides = carousel()["slides"]
        slides[0] = {"num": 2, "headline": "1 in 6 adults has diabetes", "insight": ""}
        selector._check_carousel(STORY, carousel(slides=slides))

    def test_number_not_in_source_is_blocked(self):
        bad = carousel(cover_headline="97,000 Malaysians A Year")
        with self.assertRaisesRegex(ValueError, "97000"):
            selector._check_carousel(STORY, bad)

    def test_long_hook_is_blocked(self):
        with self.assertRaisesRegex(ValueError, "12 words"):
            selector._check_carousel(STORY, carousel(cover_headline=" ".join(["word"] * 13)))

    def test_long_slide_is_blocked(self):
        slides = carousel()["slides"]
        slides[0] = {"num": 2, "headline": " ".join(["word"] * 25), "insight": " ".join(["word"] * 6)}
        with self.assertRaisesRegex(ValueError, "30 words"):
            selector._check_carousel(STORY, carousel(slides=slides))

    def test_cure_claim_is_blocked(self):
        slides = carousel()["slides"]
        slides[1] = {"num": 3, "headline": "This vegetable cures diabetes", "insight": ""}
        with self.assertRaisesRegex(ValueError, "cure"):
            selector._check_carousel(STORY, carousel(slides=slides))

    def test_missing_sources_is_blocked(self):
        with self.assertRaisesRegex(ValueError, "sources"):
            selector._check_carousel(STORY, carousel(sources=[]))

    def test_rotation_skips_last_pillar(self):
        stories = [
            {"url": "a", "headline": "A", "source": "s", "category": "c", "score": 90, "pillar": 1},
            {"url": "b", "headline": "B", "source": "s", "category": "c", "score": 80, "pillar": 3},
        ]
        with patch.object(selector, "score_stories", return_value=stories), \
             patch.object(selector, "write_carousel", side_effect=lambda s: {"pillar": s["pillar"]}):
            picked = selector.run(stories, set(), last_pillar=1)
        self.assertEqual(picked[0][0]["url"], "b")


if __name__ == "__main__":
    unittest.main()
