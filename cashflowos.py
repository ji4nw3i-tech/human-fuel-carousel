"""Hand each carousel to CashflowOS (Jarvis on Telegram) for approval, and report back.

  propose() — after the slides are built and hosted, Jarvis sends the preview with
              ✅ Approve / ❌ Reject. Approve dispatches this repo's workflow with
              publish_run_id, which runs `pipeline.py --publish <run_id>`.
  report()  — tells you on Telegram when a carousel is posted, skipped or failed.

Needs CASHFLOWOS_URL (e.g. https://your-app.vercel.app) and CONTENT_SECRET (the same
value set in Vercel). Without them, approvals are off and the bot posts on its own.
"""

import os

import requests

BRAND = "human-fuel"   # must match a brand in CashflowOS lib/content.ts
TIMEOUT = 30


def _url() -> str:
    return os.environ.get("CASHFLOWOS_URL", "").strip().rstrip("/")


def _secret() -> str:
    return os.environ.get("CONTENT_SECRET", "").strip()


def enabled() -> bool:
    return bool(_url() and _secret())


def _post(path: str, body: dict) -> dict:
    response = requests.post(
        f"{_url()}{path}",
        json={"brand": BRAND, **body},
        headers={"x-content-secret": _secret()},
        timeout=TIMEOUT,
    )
    if not 200 <= response.status_code < 300:
        raise RuntimeError(f"CashflowOS {path} failed (HTTP {response.status_code}): {response.text[:300]}")
    return response.json()


def propose(run_id: str, story: dict, caption: str, image_urls: list[str]) -> None:
    result = _post("/api/content/propose", {
        "run_id": run_id,
        "headline": story.get("headline", ""),
        "source": story.get("source", ""),
        "source_url": story.get("article_url") or story.get("url", ""),
        "caption": caption,
        "image_urls": image_urls,
    })
    print(f"[cashflowos] Sent for approval on Telegram (action {result.get('action_id', '?')})")


def report(status: str, run_id: str = "", headline: str = "", permalink: str = "", error: str = "") -> None:
    """Best effort: a failed report must never hide the real outcome."""
    if not enabled():
        return
    try:
        _post("/api/content/report", {
            "status": status, "run_id": run_id, "headline": headline,
            "permalink": permalink, "error": error[:500],
        })
    except Exception as e:
        print(f"[cashflowos] Could not send the {status} update: {e}")
