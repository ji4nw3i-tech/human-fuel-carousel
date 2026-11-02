"""Use Claude API to score stories and write 10-slide carousel content."""
import os
import json
import re
from pathlib import Path
import anthropic

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

# Load country config
_cfg_path = Path(__file__).parent / "config.json"
with open(_cfg_path) as f:
    _CFG = json.load(f)

COUNTRY        = _CFG.get("country", "Malaysia")
ACCOUNT_HANDLE = _CFG.get("account_handle", "@YOUR_INSTAGRAM_HANDLE")
COMMUNITY_NAME = _CFG.get("community_name", "YOUR_BRAND_NAME")
COMMUNITY_URL  = _CFG.get("community_url", "YOUR_COMMUNITY_URL")
COMMENT_KEYWORD = _CFG.get("comment_keyword", "YOUR_COMMENT_KEYWORD")
CURRENCY       = _CFG.get("currency", "Ringgit (RM)")
GOV_BODIES     = _CFG.get("government_bodies", "NAIO, MDEC")
LANDMARKS      = _CFG.get("local_landmarks", "KLCC, Putrajaya")
LOCAL_CONTEXT  = _CFG.get("local_context", "local founders and businesses")
FLAG_EMOJI     = _CFG.get("flag_emoji", "🇲🇾")
HASHTAGS       = " ".join(_CFG.get("posting", {}).get("hashtags", ["#AINews"]))

BRAND_NAME     = _CFG.get("brand_name", COMMUNITY_NAME)
TOPIC          = _CFG.get("topic", "plant-based eating and natural farming")
AUDIENCE       = _CFG.get("audience", LOCAL_CONTEXT)

HEALTH_RULES = f"""Health and safety rules (non-negotiable):
- Never claim a food, diet, or practice cures, treats, or reverses a disease. Say "linked to", "may help", "in this study".
- Report study results with their limits: who was studied, how many, how long. Animal or lab studies must be labelled as such.
- Never tell readers to stop or change medication. Anyone on medication, pregnant, or with a condition should be told to check with their doctor.
- No fear-mongering about farmers, specific brands, or ethnic cuisines. Criticise practices, not people.
- No weight-loss shaming or extreme fasting advice."""

SCORE_PROMPT = f"""You are the social media editor for {ACCOUNT_HANDLE} ({BRAND_NAME}) — a {COUNTRY} Instagram account about {TOPIC}.
The audience: {AUDIENCE}.

Score each story 0-100 for Instagram carousel potential. Use this rubric:
- 90-100: Big, credible news — new major study, policy change, food-safety finding, {COUNTRY}-specific story people will share
- 70-89: Useful and fresh — a clear practical takeaway for eating, growing food, or health habits
- 50-69: Interesting — can be turned into a practical lesson for {COUNTRY} readers
- 30-49: Low priority — product promotion, celebrity diet gossip, thin evidence
- 0-29: Skip — off-topic, miracle-cure claims, anti-science, already covered

Weighted scoring factors:
1. Relevance to {TOPIC} (3x weight). Stories that only mention food in passing score low.
2. {COUNTRY} relevance (2x): 10 = about {COUNTRY} ({GOV_BODIES}, local farms, local food), 5 = global with an obvious local angle, 2 = no local hook.
3. Credibility (2x): peer-reviewed study, health authority, or reputable outlet scores high. Supplement ads and miracle claims score 0.
4. Practical value (2x): can a reader change one thing in their kitchen, garden, or routine this week?
5. Community signals (1x): Reddit score 500+ = 10, 200+ = 8, 60+ = 5. No signals = 3.

Also assign the best hook angle (1-8) for each story:
1=Against The Grain, 2=Controversial, 3=Trending, 4=Celebrity, 5=Small Change Big Difference, 6=Well Known Little Understood, 7=Uncommon/Weird, 8=Numbers

Return ONLY a compact JSON array — no explanation outside the array, no markdown fences. Keep reason under 8 words.
[{{"index": 0, "score": 85, "category": "local", "angle": 5, "reason": "new fibre study, easy habit"}}]

Stories (with community signals):
{{stories}}"""

WRITE_PROMPT = f"""You are the carousel writer for {ACCOUNT_HANDLE} ({BRAND_NAME}) — a {COUNTRY} Instagram account about {TOPIC}.
The audience: {AUDIENCE}. The voice: warm, practical, grounded — a knowledgeable friend who farms and coaches, not a guru.

Write a 10-slide Instagram carousel for this story.

{HEALTH_RULES}

## STEP 1: Pick the single best hook angle

1. AGAINST THE GRAIN — "Why [common belief about food/health] Is Wrong"
2. CONTROVERSIAL — "Is [popular food/trend] Actually Healthy?"
3. TRENDING / TIMELY — "What [new study/news] Means for Your Plate"
4. CELEBRITY / AUTHORITY — "What [named expert or body] Just Said About [topic]"
5. SMALL CHANGE, BIG DIFFERENCE — "One Swap That [specific result from the study]"
6. WELL KNOWN, LITTLE UNDERSTOOD — "Everyone Says Eat More Fibre. Few Know Why."
7. UNCOMMON / WEIRD — "The Weird Farming Trick [farmers] Are Using"
8. NUMBERS — "[X]% of Malaysians [surprising health or food fact]"

## STEP 2: Write the full carousel

Writing rules:
- Write like a friend explaining it over WhatsApp. Simple words. No jargon without explaining it.
- Preserve every date, number, sample size, organisation, and attribution exactly as supplied by the source. Never invent a fact, statistic, or quote.
- Preserve the full scope of compound facts. If the source says "fruit and vegetables", keep both; never narrow it to "just vegetables". If it says "data centres and cloud projects", never narrow it to "just data centres".
- Cover headline: Title Case. Include a specific number or name if the story has one. Max 10 words per line, 2-3 lines.
- Every slide headline must be a specific, conversational statement — not a generic label.
- Use **double asterisks** around the single most striking number or fact in one headline.
- insight: ONE sentence only. Max 12 words. Numbers preferred.
- Slide 3 MUST localise to {COUNTRY}: Malaysian food (nasi lemak, roti canai, teh tarik, kuih, sayur), local farms, pasar tani, or {GOV_BODIES}.
- Slide 8 must be a practical step someone can do this week in a Malaysian kitchen, garden, or routine.
- Slide 9 must name the hype, myth, or over-claim to be careful of.
- Caption: start with a 1-line hook, then 2-3 short lines, then "Swipe ➡️", then Comment {COMMENT_KEYWORD}. End with: "Not medical advice — talk to your doctor before big diet changes." Then only these hashtags: {HASHTAGS}
- Write EXACTLY 8 slides (num 2 through 9). Do NOT write a slide 10 — the CTA is generated automatically.
- cover_badge: Pick one — NEW STUDY, LOCAL, FARM TIP, MYTH BUSTED, FUEL NEWS.
- meme_text: Only for light, funny stories. Max 2 short lines. Empty string otherwise.
- image prompts: 2-3 plain nouns that a stock photo site would match, most important word first. GOOD: "lentils oats", "vegetable seedlings", "wet market vegetables", "cooking vegetables kitchen". BAD: long descriptions, adjectives like "overhead", "rustic", "warm light". Every slide must show food: vegetables, fruit, grains, legumes, herbs, plant-based dishes, or produce at a market or farm. Never people, faces, scientists, laboratories, pills, syringes, hospitals, desserts, or junk food.
- If the full text is empty or thin, write ONLY what the headline and summary say. Do not add general nutrition facts, numbers, or mechanisms from memory — keep slides about what this story reports and practical, safe habits.

Return valid JSON only:
{{
  "angle": 5,
  "angle_name": "SMALL CHANGE, BIG DIFFERENCE",
  "cover_formula": 5,
  "cover_headline": "One Extra Bowl of Beans a Day\\nWas Linked to Lower Blood Sugar\\nIn a 12-Week Study",
  "cover_subheadline": "Cheap, local, and already in your kitchen.",
  "cover_badge": "NEW STUDY",
  "meme_text": "",
  "caption": "Beans might be the cheapest health upgrade in your kitchen.\\n\\nA new study tracked what happened when people added one bowl a day.\\n\\nSwipe ➡️\\n\\nComment \\"{COMMENT_KEYWORD}\\" to join {COMMUNITY_NAME} {FLAG_EMOJI}\\n→ {COMMUNITY_URL}\\n\\nNot medical advice — talk to your doctor before big diet changes.\\n\\n{HASHTAGS}",
  "cover_image_prompt": "beans vegetables bowl",
  "slides": [
    {{
      "num": 2,
      "label": "WHAT HAPPENED",
      "headline": "Write a specific 8-10 word headline describing the actual news or finding",
      "insight": "One sentence, max 12 words. Who was studied, how many, how long.",
      "image_prompt": "fresh vegetables"
    }},
    {{
      "num": 3,
      "label": "{COUNTRY} ANGLE",
      "headline": "Write how this connects to Malaysian food, farms, or health",
      "insight": "One sentence, max 12 words. A local fact or everyday Malaysian example.",
      "image_prompt": "wet market vegetables"
    }},
    {{
      "num": 4,
      "label": "THE NUMBER",
      "headline": "Write the key stat as a surprising statement",
      "insight": "One sentence, max 12 words. The exact figure from the source.",
      "image_prompt": "legumes grains"
    }},
    {{
      "num": 5,
      "label": "MOST PEOPLE DON'T KNOW",
      "headline": "Write the counterintuitive truth this story reveals",
      "insight": "One sentence, max 12 words.",
      "image_prompt": "soil seedling"
    }},
    {{
      "num": 6,
      "label": "WHAT THE EXPERTS SAY",
      "headline": "Write what a named researcher, doctor, or body actually said",
      "insight": "One sentence, max 12 words. Only a quote or claim present in the source.",
      "image_prompt": "lentils beans"
    }},
    {{
      "num": 7,
      "label": "WHY IT WORKS",
      "headline": "Write the simple mechanism or reason behind the finding",
      "insight": "One sentence, max 12 words. Plain-language explanation.",
      "image_prompt": "leafy greens garden"
    }},
    {{
      "num": 8,
      "label": "TRY THIS WEEK",
      "headline": "Write one practical step for a Malaysian kitchen, garden, or routine",
      "insight": "One sentence, max 12 words. Specific and cheap to do.",
      "image_prompt": "cooking vegetables kitchen"
    }},
    {{
      "num": 9,
      "label": "BE CAREFUL OF",
      "headline": "Write the hype, myth, or over-claim people should not fall for",
      "insight": "One sentence, max 12 words.",
      "image_prompt": "fruits vegetables"
    }}
  ]
}}

IMPORTANT: You MUST return valid JSON no matter what. If article text is limited, use only facts present in the headline, summary, and supplied full text. Do not fill gaps from memory or invent specifics. Never refuse or explain — just write a conservative carousel and return JSON.

Story to write about:
Headline: {{headline}}
Summary: {{summary}}
Full text: {{raw_text}}
Category: {{category}}"""


def score_stories(stories: list[dict]) -> list[dict]:
    """Score all stories and return sorted list."""
    def _signal_str(s: dict) -> str:
        parts = []
        if s.get("hn_score", 0) >= 150:
            parts.append(f"HN:{s['hn_score']}pts")
        if s.get("reddit_score", 0) >= 60:
            parts.append(f"Reddit:{s['reddit_score']}↑")
        if s.get("gh_stars", 0) >= 100:
            parts.append(f"GH:{s['gh_stars']}★")
        return " | " + " ".join(parts) if parts else ""

    stories_text = "\n".join(
        f"[{i}] {s['headline']} | {s['source']} | {s['category']}{_signal_str(s)}"
        for i, s in enumerate(stories)
    )

    resp = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=8000,
        messages=[{"role": "user", "content": SCORE_PROMPT.replace("{stories}", stories_text)}]
    )
    text = resp.content[0].text.strip()
    # Strip markdown code fences if present
    text = re.sub(r"```(?:json)?\s*", "", text).strip()
    # Extract JSON array
    start = text.find("[")
    end = text.rfind("]") + 1
    if start == -1 or end == 0:
        print(f"[selector] Score parse failed — raw response:\n{text[:300]}")
        # Return stories with default score 50
        for s in stories:
            s.setdefault("score", 50)
            s.setdefault("suggested_angle", 3)
        return stories
    scores = json.loads(text[start:end])

    for s in scores:
        idx = s["index"]
        if idx < len(stories):
            stories[idx]["score"] = s["score"]
            stories[idx]["score_reason"] = s.get("reason", "")
            stories[idx]["suggested_angle"] = s.get("angle", 3)

    return sorted(stories, key=lambda x: x.get("score", 0), reverse=True)


def write_carousel(story: dict) -> dict:
    """Write full 10-slide carousel content for a story."""
    prompt = (WRITE_PROMPT
        .replace("{headline}", story["headline"])
        .replace("{summary}", story.get("summary", ""))
        .replace("{raw_text}", story.get("raw_text", "")[:2000])
        .replace("{category}", story.get("category", "global_topic"))
    )

    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}]
    )
    text = resp.content[0].text.strip()
    # Strip markdown code fences
    text = re.sub(r"```(?:json)?\s*", "", text).strip()
    start = text.find("{")
    end = text.rfind("}") + 1
    if start == -1 or end == 0:
        raise ValueError(f"[selector] write_carousel parse failed:\n{text[:300]}")
    return json.loads(text[start:end])


def run(stories: list[dict], posted_urls: set) -> tuple[dict, dict]:
    """Select top stories and write carousels. Retries next story if write fails."""
    # Filter already posted
    fresh = [s for s in stories if s["url"] not in posted_urls]
    print(f"[selector] {len(fresh)} fresh stories to score (removed {len(stories)-len(fresh)} already posted)")

    # Block off-topic and miracle-cure content
    _blocklist = [
        "us politics", "trump", "congress", "senate bill",
        "nfl", "nba", "premier league", "cricket",
        "miracle cure", "cures cancer", "detox tea", "weight loss pill",
        "ozempic", "wegovy", "supplement deal", "discount code",
    ]
    before = len(fresh)
    fresh = [s for s in fresh if not any(kw in s.get("headline", "").lower() for kw in _blocklist)]
    if len(fresh) < before:
        print(f"[selector] Blocked {before - len(fresh)} irrelevant stories")

    scored = score_stories(fresh)

    # Pick best Malaysia local + best global as primary picks
    local = next((s for s in scored if s.get("category") == "malaysia_local"), None)
    global_ = next((s for s in scored if s.get("category") != "malaysia_local"), None)

    picks = [s for s in [local, global_] if s][:2]
    if not picks:
        picks = scored[:2]

    # Build a fallback pool — all scored stories not already in picks
    pick_urls = {s["url"] for s in picks}
    fallback_pool = [s for s in scored if s["url"] not in pick_urls]

    results = []
    for story in picks:
        print(f"[selector] Writing carousel for: {story['headline'][:60]}... (score: {story.get('score')})")
        try:
            carousel = write_carousel(story)
            results.append((story, carousel))
        except Exception as e:
            print(f"[selector] write_carousel failed: {e}")
            print(f"[selector] Trying next story from fallback pool...")
            # Try fallback stories one by one until one succeeds
            for fallback in fallback_pool:
                if fallback["url"] in {r[0]["url"] for r in results}:
                    continue
                print(f"[selector] Fallback: {fallback['headline'][:60]}...")
                try:
                    carousel = write_carousel(fallback)
                    results.append((fallback, carousel))
                    fallback_pool.remove(fallback)
                    break
                except Exception as e2:
                    print(f"[selector] Fallback also failed: {e2}")
                    continue

    return results


if __name__ == "__main__":
    import scraper
    stories = scraper.run()
    pairs = run(stories, set())
    for story, carousel in pairs:
        print(f"\n=== {story['headline']} ===")
        print(f"Cover: {carousel.get('cover_headline')}")
        print(f"Caption preview: {carousel.get('caption','')[:100]}")
