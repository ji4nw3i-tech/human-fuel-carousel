"""Post carousels to Instagram with the official Instagram API.

Works with both token kinds Meta issues:
- Instagram Login tokens (start with "IG") → graph.instagram.com, account found via /me
- Unified / Facebook Login tokens (start with "EAA") → graph.facebook.com, account = config user_id

Flow: one container per slide → a CAROUSEL container → wait until FINISHED → publish.
Instagram downloads each slide from a public JPEG URL (see hosting.py).
"""

import os
import re
import time
from typing import Optional

import requests

REQUEST_TIMEOUT = 30
DEFAULT_HOST = "graph.instagram.com"
DEFAULT_VERSION = "v23.0"


def _base_url(api_host: str = DEFAULT_HOST, api_version: str = DEFAULT_VERSION) -> str:
    return f"https://{api_host}/{api_version}"


def _token() -> str:
    """Read the token lazily so a missing or whitespace-only secret fails clearly."""
    token = os.environ.get("INSTAGRAM_ACCESS_TOKEN", "").strip()
    if not token:
        raise RuntimeError("INSTAGRAM_ACCESS_TOKEN is missing or empty")
    return token


def _response_error(response: requests.Response, action: str) -> RuntimeError:
    """Return a useful API error without exposing the token."""
    body = (getattr(response, "text", "") or "").strip().replace("\n", " ")
    token = os.environ.get("INSTAGRAM_ACCESS_TOKEN", "").strip()
    if token:
        body = body.replace(token, "***")
    if len(body) > 500:
        body = body[:500] + "…"
    detail = f": {body}" if body else ""
    return RuntimeError(f"Instagram {action} failed (HTTP {response.status_code}){detail}")


def _require_success(response: requests.Response, action: str) -> dict:
    if not 200 <= response.status_code < 300:
        raise _response_error(response, action)
    return response.json()


def _is_instagram_login_token() -> bool:
    return _token().startswith("IG")


def base_url_for(ig_cfg: dict) -> str:
    """Pick the API host that matches the token type."""
    version = ig_cfg.get("api_version", DEFAULT_VERSION)
    host = DEFAULT_HOST if _is_instagram_login_token() else "graph.facebook.com"
    return _base_url(host, version)


def validate_account(expected_username: Optional[str] = None, base_url: Optional[str] = None,
                     user_id: Optional[str] = None) -> dict:
    """Check the token works and reaches the expected Instagram account.

    Returns {"user_id": ..., "username": ...}.
    """
    base_url = base_url or _base_url()
    if "graph.instagram.com" in base_url:
        response = requests.get(
            f"{base_url}/me",
            params={"fields": "user_id,username,account_type", "access_token": _token()},
            timeout=REQUEST_TIMEOUT,
        )
        data = _require_success(response, "authentication check")
        found_id = str(data.get("user_id") or data.get("id") or "")
    else:
        if not user_id:
            raise RuntimeError("config.json instagram.user_id is required for this token type")
        response = requests.get(
            f"{base_url}/{user_id}",
            params={"fields": "id,username", "access_token": _token()},
            timeout=REQUEST_TIMEOUT,
        )
        data = _require_success(response, "authentication check")
        found_id = str(data.get("id") or "")
    username = str(data.get("username", "")).lstrip("@")
    if not found_id:
        raise RuntimeError("Instagram token check returned no account id")
    if expected_username and username.lower() != expected_username.lstrip("@").lower():
        raise RuntimeError(
            f"INSTAGRAM_ACCESS_TOKEN reaches @{username or 'unknown'}, "
            f"not the expected Instagram account @{expected_username.lstrip('@')}"
        )
    print(f"[poster] Instagram ready: @{username} (user {found_id})")
    return {"user_id": found_id, "username": username}


def _limit_instagram_hashtags(caption: str, limit: int = 5) -> str:
    """Keep only the first `limit` hashtags."""
    count = 0

    def keep_or_remove(match: re.Match) -> str:
        nonlocal count
        count += 1
        return match.group(0) if count <= limit else ""

    cleaned = re.sub(r"(?<!\w)#[\w]+", keep_or_remove, caption)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = re.sub(r"[ \t]+\n", "\n", cleaned)
    return cleaned.strip()


def _create_container(base_url: str, user_id: str, params: dict, action: str) -> str:
    response = requests.post(
        f"{base_url}/{user_id}/media",
        data={**params, "access_token": _token()},
        timeout=REQUEST_TIMEOUT,
    )
    container_id = _require_success(response, action).get("id")
    if not container_id:
        raise RuntimeError(f"Instagram {action} returned no container id")
    return str(container_id)


def wait_until_ready(base_url: str, container_id: str, timeout: int = 180, poll_interval: int = 5) -> None:
    """Wait until Instagram has downloaded and processed a container."""
    deadline = time.monotonic() + timeout
    while True:
        response = requests.get(
            f"{base_url}/{container_id}",
            params={"fields": "status_code,status", "access_token": _token()},
            timeout=REQUEST_TIMEOUT,
        )
        data = _require_success(response, "container status check")
        status = str(data.get("status_code", "")).upper()
        if status in ("FINISHED", "PUBLISHED"):
            return
        if status in ("ERROR", "EXPIRED"):
            raise RuntimeError(
                f"Instagram container {container_id} is {status}: {data.get('status', 'no detail')}"
            )
        if time.monotonic() >= deadline:
            raise TimeoutError(f"Instagram container {container_id} still {status or 'pending'} after {timeout}s")
        time.sleep(poll_interval)


def post_carousel(base_url: str, user_id: str, caption: str, image_urls: list[str]) -> str:
    """Create and publish a carousel. Returns the published Instagram media id."""
    if not 2 <= len(image_urls) <= 10:
        raise ValueError(f"Instagram carousels need 2-10 images, got {len(image_urls)}")

    children = []
    for i, url in enumerate(image_urls, start=1):
        child = _create_container(
            base_url, user_id,
            {"image_url": url, "is_carousel_item": "true"},
            f"slide {i} upload",
        )
        children.append(child)
        print(f"[poster] Slide {i}/{len(image_urls)} container {child}")
    for child in children:
        wait_until_ready(base_url, child)

    carousel_id = _create_container(
        base_url, user_id,
        {
            "media_type": "CAROUSEL",
            "children": ",".join(children),
            "caption": _limit_instagram_hashtags(caption),
        },
        "carousel creation",
    )
    wait_until_ready(base_url, carousel_id)

    response = requests.post(
        f"{base_url}/{user_id}/media_publish",
        data={"creation_id": carousel_id, "access_token": _token()},
        timeout=REQUEST_TIMEOUT,
    )
    media_id = _require_success(response, "publish").get("id")
    if not media_id:
        raise RuntimeError("Instagram accepted the publish request but returned no media id")
    print(f"[poster] Published! media_id={media_id}")
    return str(media_id)


def run(image_urls: list[str], caption: str, ig_cfg: dict) -> str:
    """Validate the account, then publish the carousel. Returns the media id."""
    base_url = base_url_for(ig_cfg)
    account = validate_account(ig_cfg.get("username"), base_url, ig_cfg.get("user_id"))
    print(f"[poster] Posting {len(image_urls)}-slide carousel to @{account['username']}...")
    return post_carousel(base_url, account["user_id"], caption, image_urls)


if __name__ == "__main__":
    # `python poster.py` checks the token without posting anything.
    import json
    import pipeline  # noqa: F401  (loads keys from .env and iCloud Drive)

    with open("config.json", encoding="utf-8") as f:
        ig = json.load(f)["instagram"]
    validate_account(ig.get("username"), base_url_for(ig), ig.get("user_id"))
