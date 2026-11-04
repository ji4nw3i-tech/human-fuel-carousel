"""Track posted stories in posted_urls.json to avoid duplicates."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path

_LOG_FILE = Path(__file__).parent / "posted_urls.json"


def _load() -> dict:
    if not _LOG_FILE.exists():
        return {"urls": [], "posts": []}
    try:
        return json.loads(_LOG_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"urls": [], "posts": []}


def story_keys(story: dict) -> set:
    """Every way to recognise a story again: Google News link, real article link, headline.
    Google News gives the same article a new link, so the link alone is not enough."""
    keys = {story.get("url", ""), story.get("article_url", "")}
    if story.get("headline"):
        keys.add("headline:" + " ".join(story["headline"].lower().split()))
    return {k for k in keys if k}


def get_posted_urls() -> set:
    return set(_load().get("urls", []))


def get_used_img_urls() -> set:
    """Return all Pexels/og:image URLs used in past posts — to avoid reuse."""
    return set(_load().get("img_urls", []))


def get_last_post_time() -> datetime | None:
    """Return UTC datetime of the most recent post, or None if no posts yet."""
    posts = _load().get("posts", [])
    if not posts:
        return None
    try:
        return datetime.fromisoformat(posts[-1]["posted_at"])
    except Exception:
        return None


def hours_since_last_post() -> float:
    """Return hours elapsed since the last post. Returns 999 if never posted."""
    last = get_last_post_time()
    if last is None:
        return 999.0
    delta = datetime.now(timezone.utc) - last
    return delta.total_seconds() / 3600


def mark_proposed(story: dict, new_img_urls: set | None = None):
    """Reserve a story and its photos while it waits for approval, so the next run
    does not pick them again. The post itself is logged by log_posted()."""
    data = _load()
    data.setdefault("urls", [])
    data.setdefault("img_urls", [])
    for key in sorted(story_keys(story)):
        if key not in data["urls"]:
            data["urls"].append(key)
    for u in (new_img_urls or set()):
        if u not in data["img_urls"]:
            data["img_urls"].append(u)
    _LOG_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def last_pillar() -> int | None:
    """The content pillar of the most recent post, so tonight's can be different."""
    posts = _load().get("posts", [])
    return posts[-1].get("pillar") if posts else None


def was_posted(run_id: str) -> bool:
    return any(p.get("run_id") == run_id for p in _load().get("posts", []))


def log_posted(story: dict, ig_post_id: str, carousel: dict, new_img_urls: set | None = None):
    data = _load()
    data.setdefault("urls", [])
    data.setdefault("posts", [])
    data.setdefault("img_urls", [])

    for key in sorted(story_keys(story)):
        if key not in data["urls"]:
            data["urls"].append(key)

    for u in (new_img_urls or set()):
        if u not in data["img_urls"]:
            data["img_urls"].append(u)

    data["posts"].append({
        "url": story["url"],
        "headline": story["headline"][:80],
        "ig_post_id": ig_post_id,
        "run_id": story.get("run_id", ""),
        "pillar": carousel.get("pillar"),
        "posted_at": datetime.now(timezone.utc).isoformat(),
    })

    _LOG_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"[logger] Logged: {story['headline'][:60]}")


if __name__ == "__main__":
    print(f"[logger] {len(get_posted_urls())} stories posted")
    print(f"[logger] Hours since last post: {hours_since_last_post():.1f}h")
