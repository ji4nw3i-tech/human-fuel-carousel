"""Use Claude API to score stories and write the carousel (the Human Fuel brief)."""
from __future__ import annotations
import os
import json
import re
from pathlib import Path
import anthropic

from logger import story_keys

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

# Load country config
_cfg_path = Path(__file__).parent / "config.json"
with open(_cfg_path) as f:
    _CFG = json.load(f)

COUNTRY        = _CFG.get("country", "Malaysia")
ACCOUNT_HANDLE = _CFG.get("account_handle", "@YOUR_INSTAGRAM_HANDLE")
GOV_BODIES     = _CFG.get("government_bodies", "NAIO, MDEC")
HASHTAGS       = " ".join(_CFG.get("posting", {}).get("hashtags", ["#AINews"]))
BRAND_NAME     = _CFG.get("brand_name", "YOUR_BRAND_NAME")
AUDIENCE       = _CFG.get("audience", "local readers")

# Content pillars: rotate, never the same pillar twice in a row.
PILLARS = {
    1: "FOOD & HEALTH",
    2: "NATURAL FARMING",
    3: "FOOD SYSTEM FACTS",
    4: "GROW YOUR OWN",
    5: "WHY WE EXIST",
}

BRAND_BRIEF = f"""You create Instagram carousel posts for {BRAND_NAME} ({ACCOUNT_HANDLE}), a natural farm being built from bare land in {COUNTRY} by its founder.

MISSION
"Farmacy": food grown naturally can do more for health than relying on medicine later. We grow food that is good for people, regenerates the soil and supports the community, and still pays its way. We document everything honestly, including failures and real numbers.

AUDIENCE
{AUDIENCE}

CONTENT PILLARS
1. Food and health: what everyday Malaysian food does to the body, and simple better choices.
2. Natural farming explained: soil, composting, JADAM, chemical-free growing, in plain words.
3. Food system facts: where Malaysia's food comes from, imports, pesticides, freshness, food miles.
4. Grow your own: small practical steps for a home garden or balcony in a tropical climate.
5. Why {BRAND_NAME} exists: the idea of building a farm that serves health, soil and community.

DO NOT POST
Political content, attacks on brands or people, miracle diets, supplements, or anything that sells a product."""

ACCURACY_RULES = """ACCURACY RULES (most important)
- Only use facts from the supplied story. The story comes from an official or reputable source (DOSM, Ministry of Health Malaysia (MOH), WHO, FAO, MARDI, peer-reviewed studies, or established news outlets reporting them). Never add facts from memory.
- Every statistic must match the source exactly: same number, same year, same definition. Do not round, combine figures, or relabel categories (e.g. "non-communicable diseases" is not the same as "lifestyle diseases").
- Keep the full scope of compound facts. If the source says "fruit and vegetables", keep both; never narrow it to "just vegetables". If it says "data centres and cloud projects", never narrow it to "just data centres".
- If the story does not support a claim, leave the claim out.
- Never claim that any food cures, treats or prevents a disease. Say "supports", "is linked to" or "research suggests", as the source supports.
- Most studies find a link, not a cause. Unless the source shows cause, write "linked to" / "associated with" — never "causes", "changes", "makes" or "leads to", in the hook too.
- Say who was studied and how many when the source gives it (e.g. "46 children in the US"). Label animal or lab studies as such.
- Never tell readers to stop, skip or reduce medication. Medication changes happen with their doctor.
- Pesticides: say "linked to" and name who was studied; never say they cause a disease unless the source shows it.
- Never invent quotes, people, farm results or harvests. The farm has not harvested yet."""

SCORE_PROMPT = f"""{BRAND_BRIEF}

You are choosing tonight's story. Score each story 0-100 and assign its best pillar (1-5).
- 85-100: from a credible source (MOH, DOSM, WHO, FAO, MARDI, a peer-reviewed study, an established outlet), clearly fits a pillar, gives a {COUNTRY} parent something useful.
- 60-84: credible and on-pillar, but less local or less practical.
- 30-59: weak fit, thin evidence, or global with no local angle.
- 0-29: anything in DO NOT POST, a non-credible source, miracle claims, product promotion, politics, or attacks on brands or people.

Weighted factors: credibility (3x), pillar fit (3x), {COUNTRY} relevance (2x, {GOV_BODIES} and local food score high), practical value for a busy parent (2x).

Return ONLY a compact JSON array — no explanation outside the array, no markdown fences. Keep reason under 8 words.
[{{"index": 0, "score": 85, "pillar": 3, "reason": "DOSM import data, local"}}]

Stories:
{{stories}}"""

WRITE_PROMPT = f"""{BRAND_BRIEF}

{ACCURACY_RULES}

TONE
Hopeful, practical, warm and honest. Name a problem, then always give something the reader can do. No fear-mongering, shock headlines, or blame. Simple English that a busy parent reads in seconds.

Write the carousel for the story below, under pillar {{pillar}} ({{pillar_name}}).

STRUCTURE (8 slides; you write slides 1-6, slides 7-8 are added automatically)
- Slide 1 (cover_headline): the hook. A surprising fact or question from the story, MAX 12 words. No clickbait. Use \\n for line breaks (2-3 lines).
- Slides 2-5: one idea per slide. headline MAX 12 words, insight MAX 14 words (30 words per slide is the hard limit).
- Slide 6: one simple action the reader can do this week (label "TRY THIS WEEK"). Same word limits.
- Count the words. Short wins: a busy parent reads each slide in seconds.
- Slide 7 (automatic): "Follow {ACCOUNT_HANDLE} as we build a natural farm in {COUNTRY}, step by step."
- Slide 8 (automatic): Sources — built from your "sources" list.
- Use **double asterisks** around the single most striking number in one headline.
- labels: 1-3 words, uppercase.

SOURCES
- "sources": one entry per source, naming the organisation or study behind every number AND the year, plus the outlet that reported it. Example: "Ministry of Health Malaysia, 2026 (reported by The Vibes)". Only sources named in the story.

CAPTION
Line 1 repeats the hook (one line, no \\n inside it). Then 2-4 short lines that add context, ending with a question to invite comments. If the post mentions a disease or medication, add the line "Not medical advice." Then one line starting "Sources: " listing the sources. Then exactly these hashtags on the last line: {HASHTAGS}

IMAGES
- image prompts: 2-3 plain nouns a stock photo site would match, most important word first. Prefer real-looking Malaysian food, markets and farms: "wet market vegetables", "nasi lemak", "paddy field", "vegetable farm", "glass water". When a slide is about a drink, show that drink.
- Never people, hands, knives, faces, laboratories, pills, hospitals, or junk food. Never anything that could pass as our own farm's harvest.

Return valid JSON only:
{{
  "pillar": {{pillar}},
  "cover_headline": "Most of Malaysia's Vegetables\\nTravel Before They Reach\\nYour Plate. Why?",
  "cover_image_prompt": "wet market vegetables",
  "slides": [
    {{"num": 2, "label": "WHAT THEY FOUND", "headline": "...", "insight": "...", "image_prompt": "vegetable farm"}},
    {{"num": 3, "label": "WHY IT MATTERS", "headline": "...", "insight": "...", "image_prompt": "paddy field"}},
    {{"num": 4, "label": "THE NUMBER", "headline": "...", "insight": "...", "image_prompt": "fresh vegetables"}},
    {{"num": 5, "label": "IN MALAYSIA", "headline": "...", "insight": "...", "image_prompt": "leafy greens"}},
    {{"num": 6, "label": "TRY THIS WEEK", "headline": "...", "insight": "...", "image_prompt": "glass water"}}
  ],
  "sources": ["Organisation or study, year (reported by Outlet)"],
  "caption": "Hook line\\n\\nContext line.\\nContext line ending with a question?\\n\\nSources: Organisation, year (Outlet)\\n\\n{HASHTAGS}"
}}

If the story text is thin, write only what the headline and summary say. Never refuse or explain — return JSON.

Story:
Headline: {{headline}}
Source outlet: {{source}}
Published: {{published_at}}
Summary: {{summary}}
Full text: {{raw_text}}"""


_WORD_NUMBERS = {w: str(i) for i, w in enumerate(
    "zero one two three four five six seven eight nine ten eleven twelve".split())}


def _numbers(text: str) -> set[str]:
    """Numbers as digits, without thousands separators: '96,000' -> '96000', 'six' -> '6'."""
    text = re.sub(r"\b(" + "|".join(_WORD_NUMBERS) + r")\b", lambda m: _WORD_NUMBERS[m.group(1).lower()], text, flags=re.I)
    return {n.replace(",", "").rstrip(".") for n in re.findall(r"\d[\d,]*(?:\.\d+)?", text)}


def unsupported_numbers(story: dict, carousel: dict) -> set[str]:
    """Numbers in the carousel or caption that do not appear in the source story."""
    source = " ".join(str(story.get(k, "")) for k in ("headline", "summary", "raw_text", "published_at", "source"))
    written = " ".join(
        [carousel.get("cover_headline", ""), carousel.get("caption", ""), " ".join(carousel.get("sources", []))]
        + [f"{s.get('headline', '')} {s.get('insight', '')}" for s in carousel.get("slides", [])]
    )
    written = re.sub(r"#\w+", "", written)  # hashtags are not facts
    return _numbers(written) - _numbers(source)


def _check_carousel(story: dict, carousel: dict) -> None:
    """Hard rules from the brief. Raise so the next story is tried instead."""
    slides = carousel.get("slides", [])
    if len(slides) != 5:
        raise ValueError(f"expected 5 inner slides, got {len(slides)}")
    if len(carousel.get("cover_headline", "").split()) > 12:
        raise ValueError("hook is longer than 12 words")
    for s in slides:
        if len(f"{s.get('headline', '')} {s.get('insight', '')}".replace("**", "").split()) > 30:
            raise ValueError(f"slide {s.get('num')} is longer than 30 words")
    if not carousel.get("sources"):
        raise ValueError("no sources listed")
    if re.search(r"\b(cures?|cured|treats?)\b", json.dumps(carousel).lower()):
        raise ValueError("cure/treat claim")
    missing = unsupported_numbers(story, carousel)
    if missing:
        raise ValueError(f"numbers not found in the source: {sorted(missing)}")


def score_stories(stories: list[dict]) -> list[dict]:
    """Score all stories and return sorted list."""
    stories_text = "\n".join(
        f"[{i}] {s['headline']} | {s['source']} | {s['category']}" for i, s in enumerate(stories)
    )
    resp = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=8000,
        messages=[{"role": "user", "content": SCORE_PROMPT.replace("{stories}", stories_text)}]
    )
    text = re.sub(r"```(?:json)?\s*", "", resp.content[0].text.strip()).strip()
    start = text.find("[")
    end = text.rfind("]") + 1
    if start == -1 or end == 0:
        print(f"[selector] Score parse failed — raw response:\n{text[:300]}")
        for s in stories:
            s.setdefault("score", 50)
            s.setdefault("pillar", 1)
        return stories

    for s in json.loads(text[start:end]):
        idx = s["index"]
        if idx < len(stories):
            stories[idx]["score"] = s["score"]
            stories[idx]["score_reason"] = s.get("reason", "")
            stories[idx]["pillar"] = s.get("pillar", 1) if s.get("pillar") in PILLARS else 1
    return sorted(stories, key=lambda x: x.get("score", 0), reverse=True)


def write_carousel(story: dict) -> dict:
    """Write the carousel for a story, then enforce the brief's hard rules."""
    pillar = story.get("pillar", 1)
    prompt = (WRITE_PROMPT
        .replace("{pillar}", str(pillar))
        .replace("{pillar_name}", PILLARS[pillar])
        .replace("{headline}", story["headline"])
        .replace("{source}", story.get("source", ""))
        .replace("{published_at}", str(story.get("published_at", "")))
        .replace("{summary}", story.get("summary", ""))
        .replace("{raw_text}", story.get("raw_text", "")[:3000])
    )
    messages = [{"role": "user", "content": prompt}]
    for attempt in (1, 2):   # one chance to fix a draft that breaks the rules
        resp = client.messages.create(model="claude-sonnet-4-6", max_tokens=4000, messages=messages)
        text = re.sub(r"```(?:json)?\s*", "", resp.content[0].text.strip()).strip()
        start = text.find("{")
        end = text.rfind("}") + 1
        if start == -1 or end == 0:
            raise ValueError(f"[selector] write_carousel parse failed:\n{text[:300]}")
        carousel = json.loads(text[start:end])
        carousel["pillar"] = pillar
        carousel["cover_badge"] = PILLARS[pillar]
        carousel["cover_subheadline"] = ""
        try:
            _check_carousel(story, carousel)
            return carousel
        except ValueError as e:
            if attempt == 2:
                raise
            print(f"[selector] Draft broke a rule ({e}) — asking for a fix")
            messages += [
                {"role": "assistant", "content": text},
                {"role": "user", "content": f"This breaks a rule: {e}. Fix it (shorten, or remove anything the source does not say) and return the full JSON only."},
            ]


_BLOCKLIST = [
    "us politics", "trump", "election", "by-election", "congress", "senate bill",
    "nfl", "nba", "premier league", "cricket",
    "miracle", "cures cancer", "detox", "weight loss pill", "supplement",
    "ozempic", "wegovy", "discount code", "promo", "giveaway", "sponsored",
]


def run(stories: list[dict], posted_urls: set, last_pillar: int | None = None) -> list[tuple[dict, dict]]:
    """Pick the best story on a different pillar from the last post and write it.

    Tries the next story when writing fails or breaks the brief's rules.
    Returns [(story, carousel)], or [] if nothing passes.
    """
    fresh = [s for s in stories if not (story_keys(s) & posted_urls)]
    print(f"[selector] {len(fresh)} fresh stories to score (removed {len(stories)-len(fresh)} already posted)")

    before = len(fresh)
    fresh = [s for s in fresh if not any(kw in s.get("headline", "").lower() for kw in _BLOCKLIST)]
    if len(fresh) < before:
        print(f"[selector] Blocked {before - len(fresh)} stories on the do-not-post list")

    scored = [s for s in score_stories(fresh) if s.get("score", 0) >= 50]
    rotated = [s for s in scored if s.get("pillar") != last_pillar]
    if last_pillar:
        print(f"[selector] Last post was pillar {last_pillar} ({PILLARS.get(last_pillar)}) — skipping it tonight")

    for story in rotated[:5]:
        print(f"[selector] Writing: {story['headline'][:60]}... "
              f"(score {story.get('score')}, pillar {story.get('pillar')} {PILLARS[story['pillar']]})")
        try:
            return [(story, write_carousel(story))]
        except Exception as e:
            print(f"[selector] Rejected: {e}")
    return []


if __name__ == "__main__":
    import scraper
    for story, carousel in run(scraper.run(), set()):
        print(f"\n=== {story['headline']} ===")
        print(f"Cover: {carousel.get('cover_headline')}")
        print(f"Caption preview: {carousel.get('caption','')[:100]}")
