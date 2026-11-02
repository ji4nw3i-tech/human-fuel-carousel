"""Give each slide a public JPEG URL so Instagram can download it.

Instagram's API only accepts JPEGs fetched from a public URL. This converts the
PNG slides to JPEG, commits them to published/<run_id>/ in this (public) GitHub
repository, pushes, and returns raw.githubusercontent.com URLs pinned to that commit.
"""

import os
import re
import subprocess
import time
from pathlib import Path

from PIL import Image

PUBLISH_DIR = Path("published")


def to_jpegs(png_paths: list[str], out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    jpgs = []
    for png in png_paths:
        jpg = out_dir / (Path(png).stem + ".jpg")
        Image.open(png).convert("RGB").save(jpg, "JPEG", quality=92)
        jpgs.append(jpg)
    return jpgs


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True).stdout.strip()


def _repo_slug() -> str:
    """owner/repo from GITHUB_REPOSITORY (Actions) or the origin remote (local)."""
    slug = os.environ.get("GITHUB_REPOSITORY", "").strip()
    if slug:
        return slug
    remote = _git("remote", "get-url", "origin")
    match = re.search(r"github\.com[:/](.+?)(?:\.git)?$", remote)
    if not match:
        raise RuntimeError(f"origin is not a GitHub remote: {remote}")
    return match.group(1)


def _push_with_retry(branch: str, attempts: int = 3) -> None:
    for i in range(1, attempts + 1):
        try:
            _git("pull", "--rebase", "origin", branch)
            _git("push", "origin", f"HEAD:{branch}")
            return
        except subprocess.CalledProcessError as e:
            subprocess.run(["git", "rebase", "--abort"], capture_output=True)
            if i == attempts:
                raise RuntimeError(f"Could not push slides to GitHub: {e.stderr or e}") from e
            print(f"[hosting] Push attempt {i} failed, retrying in 10s...")
            time.sleep(10)


def publish(png_paths: list[str], run_id: str) -> list[str]:
    """Commit JPEG copies of the slides and return their public URLs."""
    jpgs = to_jpegs(png_paths, PUBLISH_DIR / run_id)
    branch = os.environ.get("GITHUB_REF_NAME", "").strip() or _git("rev-parse", "--abbrev-ref", "HEAD")

    if os.environ.get("GITHUB_ACTIONS"):
        _git("config", "user.name", "github-actions[bot]")
        _git("config", "user.email", "github-actions[bot]@users.noreply.github.com")
    _git("add", "-f", *[str(p) for p in jpgs])
    _git("commit", "-m", f"chore: slides for {run_id} [skip ci]")
    _push_with_retry(branch)

    sha = _git("rev-parse", "HEAD")
    slug = _repo_slug()
    urls = [f"https://raw.githubusercontent.com/{slug}/{sha}/{p.as_posix()}" for p in jpgs]
    print(f"[hosting] {len(urls)} slides public at {urls[0].rsplit('/', 1)[0]}/")
    return urls
