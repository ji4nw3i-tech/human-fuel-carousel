"""
Main pipeline orchestrator:
  scraper → selector → image_gen → builder → hosting → Instagram API → logger
"""
import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import os

from dotenv import dotenv_values

# Keys come from the environment, then .env, then any *human-fuel*.txt file in
# iCloud Drive (created from an iPhone). Blank lines in .env do not hide them.
_ICLOUD = Path.home() / "Library/Mobile Documents/com~apple~CloudDocs"
_icloud_key_files = sorted(
    (p for p in (_ICLOUD.glob("*.txt") if _ICLOUD.exists() else []) if "human-fuel" in p.name.lower()),
    key=lambda p: p.stat().st_mtime, reverse=True,  # newest file wins
)
for _env_file in (".env", *_icloud_key_files):
    for _key, _value in dotenv_values(_env_file).items():
        if (_value or "").strip() and not os.environ.get(_key, "").strip():
            os.environ[_key] = _value.strip()

import builder
import cashflowos
import config_check
import hosting
import image_gen
import logger
import poster
import scraper
import selector


def check_visual_quality(image_sources: list[str], dry_run: bool) -> int:
    """Block live publication when too many slides lack photographic backgrounds."""
    gradient_count = image_sources.count("gradient")
    if gradient_count:
        print(f"[pipeline] Visual quality warning: {gradient_count}/10 slides use gradients")
    if not dry_run and gradient_count > 2:
        raise RuntimeError(
            "Visual quality gate blocked publication: "
            f"{gradient_count}/10 slides have no photographic background. "
            "Configure PIXABAY_API_KEY (or PEXELS_API_KEY), then run a dry run first."
        )
    return gradient_count


def _half_year_periods(text: str) -> set[tuple[int, str]]:
    """Extract half-year references such as 1H2026, H1 2026, or 2H-2025."""
    periods = set()
    pattern = r"\b(?:(1|2)H|H(1|2))[-\s]?(20\d{2})\b"
    for first, second, year in re.findall(pattern, text, re.I):
        periods.add((int(first or second), year))
    return periods


def validate_carousel_facts(story: dict, carousel: dict) -> None:
    """Block deterministic date-period conflicts before rendering or posting."""
    source_text = " ".join(str(story.get(key, "")) for key in ("headline", "summary"))
    source_periods = _half_year_periods(source_text)
    if not source_periods:
        return
    carousel_periods = _half_year_periods(json.dumps(carousel, ensure_ascii=False))
    conflicts = carousel_periods - source_periods
    if conflicts:
        raise ValueError(
            "Carousel period conflicts with source headline: "
            f"source={sorted(source_periods)}, carousel={sorted(carousel_periods)}"
        )


def write_review_manifest(
    png_paths: list[str],
    story: dict,
    carousel: dict,
    image_sources: list[str],
    run_id: str,
) -> str:
    """Save the exact story, caption, and source list beside inspected slide PNGs."""
    if not png_paths:
        raise ValueError("Cannot write review manifest without slide PNGs")
    path = Path(png_paths[0]).parent / "review_manifest.json"
    path.write_text(
        json.dumps(
            {
                "run_id": run_id,
                "story": story,
                "carousel": carousel,
                "image_sources": image_sources,
                "slides": [Path(item).name for item in png_paths],
            },
            ensure_ascii=False,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )
    print(f"[pipeline] Review manifest: {path}")
    return str(path)


def run(dry_run: bool = False):
    with open("config.json", encoding="utf-8") as config_file:
        cfg = json.load(config_file)
    ig_cfg = cfg["instagram"]
    run_ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")

    # A fresh template must not spend API credits or post under placeholder brand values.
    action = config_check.guard_unconfigured(cfg)
    if action:
        print(config_check.friendly_message(config_check.placeholder_fields(cfg)))
        if action == "skip":
            print("[pipeline] Scheduled run skipped. Nothing was posted.")
            return
        sys.exit(1)

    # Fail before scraping, AI calls, and rendering if Instagram is unavailable.
    if not dry_run:
        print("\n── STEP 0: INSTAGRAM PREFLIGHT ──")
        poster.validate_account(ig_cfg.get("username"), poster.base_url_for(ig_cfg), ig_cfg.get("user_id"))

    print("\n── STEP 1: SCRAPE ──")
    stories = scraper.run()
    if not stories:
        print("[pipeline] No stories scraped — exiting.")
        if not dry_run:
            cashflowos.report("skipped", error="No stories found today")
        sys.exit(0)

    print("\n── STEP 2: DEDUP CHECK ──")
    posted_urls = logger.get_posted_urls()
    print(f"[pipeline] {len(posted_urls)} already-posted URLs loaded")

    hours_ago = logger.hours_since_last_post()
    print(f"[pipeline] Local log: last post was {hours_ago:.1f}h ago")
    if not dry_run and hours_ago < 7:
        print(f"[pipeline] Already posted {hours_ago:.1f}h ago — skipping to avoid double-post.")
        sys.exit(0)

    print("\n── STEP 3: SELECT + WRITE ──")
    pairs = selector.run(stories, posted_urls)
    if not pairs:
        print("[pipeline] No fresh stories to post — exiting.")
        if not dry_run:
            cashflowos.report("skipped", error="No fresh story worth posting today")
        sys.exit(0)

    story, carousel = pairs[0]
    print(f"\n[pipeline] Selected: {story['headline'][:70]}")
    validate_carousel_facts(story, carousel)

    print("\n── STEP 4: IMAGE GENERATION ──")
    img_dir = f"/tmp/carousel_imgs_{run_ts}"
    # Publisher photos are usually copyrighted; only reuse them if config allows it.
    og_url = story.get("og_image_url", "") if cfg.get("use_article_image", False) else ""
    used_img_urls = logger.get_used_img_urls()
    image_paths, new_img_urls, image_sources = image_gen.generate_slide_images(
        carousel,
        img_dir,
        og_image_url=og_url,
        used_img_urls=used_img_urls,
    )

    if not image_paths:
        raise RuntimeError("Image generation returned no slides")
    while len(image_paths) < 10:
        image_paths.append(image_paths[-1])
    image_paths = image_paths[:10]

    print("\n── STEP 5: BUILD CAROUSEL ──")
    run_id = f"{run_ts}_{story.get('category', 'story')}"
    png_paths = builder.run(carousel, image_paths, run_id)
    check_visual_quality(image_sources, dry_run)
    write_review_manifest(png_paths, story, carousel, image_sources, run_id)

    if dry_run:
        print(f"\n[pipeline] DRY RUN — skipping post. PNGs at: ~/Downloads/carousels/{run_id}/")
        return

    caption = carousel.get("caption", "")
    story["run_id"] = run_id
    story["instagram_username"] = ig_cfg.get("username", "")

    if cashflowos.enabled():
        print("\n── STEP 6: HOST SLIDES + SEND FOR APPROVAL ──")
        post_file = hosting.PUBLISH_DIR / run_id / "post.json"
        post_file.parent.mkdir(parents=True, exist_ok=True)
        post_file.write_text(json.dumps({
            "story": {k: v for k, v in story.items() if k != "raw_text"},
            "carousel": carousel,
            "caption": caption,
            "new_img_urls": sorted(new_img_urls),
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        image_urls = hosting.publish(png_paths, run_id, extra_files=[post_file])
        logger.mark_proposed(story, new_img_urls)
        cashflowos.propose(run_id, story, caption, image_urls)
        print(f"\n✓ READY — waiting for your approval on Telegram: {story['headline'][:60]}")
        return

    print("\n── STEP 6: HOST SLIDES ──")
    print("[pipeline] Approvals are off (no CASHFLOWOS_URL / CONTENT_SECRET) — posting directly.")
    image_urls = hosting.publish(png_paths, run_id)
    _post_and_log(story, carousel, caption, image_urls, ig_cfg, new_img_urls)


def _post_and_log(story: dict, carousel: dict, caption: str, image_urls: list[str],
                  ig_cfg: dict, new_img_urls) -> None:
    print("\n── POST TO INSTAGRAM ──")
    media_id = poster.run(image_urls, caption, ig_cfg)

    print("\n── LOG ──")
    logger.log_posted(story, media_id, carousel, new_img_urls=set(new_img_urls))
    link = poster.permalink(media_id, ig_cfg)
    cashflowos.report("posted", story.get("run_id", ""), story.get("headline", ""), permalink=link)

    print(f"\n✓ DONE — Posted: {story['headline'][:60]}")
    print(f"  Instagram media ID: {media_id}  {link}")


def publish(run_id: str) -> None:
    """Post a carousel you approved on Telegram (slides were hosted by an earlier run)."""
    if not re.fullmatch(r"\d{8}_\d{4}_[a-z_]+", run_id):
        raise ValueError(f"Not a carousel run id: {run_id!r}")
    with open("config.json", encoding="utf-8") as config_file:
        ig_cfg = json.load(config_file)["instagram"]
    if logger.was_posted(run_id):
        print(f"[pipeline] {run_id} is already posted — nothing to do.")
        return
    saved = json.loads((hosting.PUBLISH_DIR / run_id / "post.json").read_text(encoding="utf-8"))
    story = saved["story"]
    print(f"[pipeline] Publishing approved carousel: {story['headline'][:70]}")
    _post_and_log(story, saved["carousel"], saved["caption"], hosting.urls_for(run_id),
                  ig_cfg, saved.get("new_img_urls", []))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Build but don't post")
    parser.add_argument("--publish", metavar="RUN_ID", help="Post a carousel approved on Telegram")
    args = parser.parse_args()
    try:
        if args.publish:
            publish(args.publish)
        else:
            run(dry_run=args.dry_run)
    except Exception as e:
        if not args.dry_run:
            cashflowos.report("failed", args.publish or "", error=f"{type(e).__name__}: {e}")
        raise
