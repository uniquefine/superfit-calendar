"""
Daily scraper for Superfit course plan PDFs.

Behaviour
---------
- Fetches studio pages, discovers PDF links, downloads new ones.
- Tracks everything in manifest.json.
- Deletes PDFs that have disappeared from the studio page AND were first seen
  more than RETENTION_DAYS ago.
- Exit code 0  → nothing changed (caller skips git commit).
- Exit code 1  → files were added or removed (caller should commit).
"""

import hashlib
import json
import logging
import sys
import time
import traceback
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

STUDIOS: dict[str, str] = {
    "friedrichshain": "https://superfit.club/studios/friedrichshain",
    "mitte": "https://superfit.club/studios/mitte",
}

MANIFEST_PATH = Path("manifest.json")
PDF_DIR = Path("pdfs")
RETENTION_DAYS = 180

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7",
}

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def fetch_with_retry(
    url: str,
    method: str = "GET",
    retries: int = 3,
    stream: bool = False,
) -> requests.Response:
    """Fetch *url* with exponential back-off.  Raises on final failure."""
    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            resp = requests.request(
                method,
                url,
                headers=HEADERS,
                timeout=60,
                stream=stream,
                allow_redirects=True,
            )
            resp.raise_for_status()
            return resp
        except Exception as exc:
            last_exc = exc
            wait = 2 ** attempt  # 1 s, 2 s, 4 s
            log.warning("Attempt %d/%d failed for %s: %s — retrying in %ds",
                        attempt + 1, retries, url, exc, wait)
            if attempt < retries - 1:
                time.sleep(wait)
    raise RuntimeError(f"All {retries} attempts failed for {url}") from last_exc


def is_pdf_url(href: str) -> bool:
    if not href:
        return False
    parsed = urlparse(href)
    return (
        parsed.path.lower().endswith(".pdf")
        or "cdn.prod.website-files.com" in parsed.netloc
    )


def extract_pdf_urls(html: str, base_url: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    urls: list[str] = []
    for tag in soup.find_all("a", href=True):
        href = tag["href"].strip()
        absolute = urljoin(base_url, href)
        if is_pdf_url(absolute):
            urls.append(absolute)
    return list(dict.fromkeys(urls))  # deduplicate, preserve order


def filename_from_url(url: str) -> str:
    name = Path(urlparse(url).path).name
    if not name or not name.lower().endswith(".pdf"):
        # Fallback: use a short hash of the full URL
        name = hashlib.sha1(url.encode()).hexdigest()[:12] + ".pdf"
    return name


def load_manifest() -> dict:
    if MANIFEST_PATH.exists():
        return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return {}


def save_manifest(manifest: dict) -> None:
    MANIFEST_PATH.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def download_pdf(url: str, dest: Path) -> None:
    """Stream-download *url* to *dest*."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    resp = fetch_with_retry(url, method="GET", stream=True)
    with dest.open("wb") as fh:
        for chunk in resp.iter_content(chunk_size=65536):
            fh.write(chunk)
    log.info("Downloaded %s → %s (%d bytes)", url, dest, dest.stat().st_size)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def process_studio(studio: str, page_url: str, manifest: dict) -> bool:
    """Process one studio.  Returns True if manifest/files changed."""
    changed = False

    log.info("--- %s ---", studio.upper())

    # 1. Fetch page and discover PDFs
    try:
        resp = fetch_with_retry(page_url)
    except Exception:
        log.error("Failed to fetch studio page %s:\n%s", page_url, traceback.format_exc())
        return False  # skip this studio; leave manifest untouched

    discovered_urls: list[str] = extract_pdf_urls(resp.text, page_url)
    log.info("Discovered %d PDF URL(s) on page", len(discovered_urls))
    for u in discovered_urls:
        log.info("  %s", u)

    discovered_set = set(discovered_urls)

    # 2. Handle newly discovered PDFs
    for pdf_url in discovered_urls:
        filename = filename_from_url(pdf_url)
        key = f"{studio}/{filename}"
        dest = PDF_DIR / studio / filename

        if key not in manifest:
            log.info("ADDED   %s", key)
            try:
                download_pdf(pdf_url, dest)
                manifest[key] = {
                    "first_seen": date.today().isoformat(),
                    "source_url": pdf_url,
                    "studio": studio,
                }
                changed = True
            except Exception:
                log.error("Failed to download %s:\n%s", pdf_url, traceback.format_exc())
                # Do not add to manifest; will retry on next run
        else:
            log.info("SKIPPED %s (already in manifest)", key)

    # 3. Handle PDFs that are no longer on the page
    cutoff = date.today() - timedelta(days=RETENTION_DAYS)
    keys_for_studio = [k for k, v in manifest.items() if v.get("studio") == studio]

    for key in keys_for_studio:
        entry = manifest[key]
        source_url = entry["source_url"]
        first_seen = datetime.fromisoformat(entry["first_seen"]).date()

        if source_url in discovered_set:
            log.info("KEPT    %s (still listed on page)", key)
            continue

        if first_seen > cutoff:
            log.info(
                "KEPT    %s (not on page but first_seen=%s is within retention window)",
                key,
                first_seen,
            )
            continue

        # Gone from page and old enough → delete
        log.info("REMOVED %s (not on page, first_seen=%s > %d days ago)", key, first_seen, RETENTION_DAYS)
        local_path = PDF_DIR / key
        if local_path.exists():
            local_path.unlink()
            log.info("Deleted local file %s", local_path)
        else:
            log.warning("Local file %s not found (already missing)", local_path)
        del manifest[key]
        changed = True

    return changed


def main() -> int:
    manifest = load_manifest()
    changed = False

    for studio, page_url in STUDIOS.items():
        try:
            studio_changed = process_studio(studio, page_url, manifest)
            changed = changed or studio_changed
        except Exception:
            log.error("Unhandled exception for studio %s:\n%s", studio, traceback.format_exc())

    save_manifest(manifest)

    if changed:
        log.info("Changes detected — exiting with code 1")
        return 1
    else:
        log.info("No changes detected — exiting with code 0")
        return 0


if __name__ == "__main__":
    sys.exit(main())
