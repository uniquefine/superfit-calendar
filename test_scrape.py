"""
Phase 1 connectivity test.

Verifies that GitHub Actions runners can reach the Superfit studio pages
and the Webflow CDN that hosts the course plan PDFs.

Exit code: 0 if all studio pages returned 200, non-zero otherwise.
"""

import sys
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

STUDIOS = {
    "friedrichshain": "https://superfit.club/studios/friedrichshain",
    "mitte": "https://superfit.club/studios/mitte",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7",
}


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
    urls = []
    for tag in soup.find_all("a", href=True):
        href = tag["href"].strip()
        absolute = urljoin(base_url, href)
        if is_pdf_url(absolute):
            urls.append(absolute)
    return list(dict.fromkeys(urls))  # deduplicate, preserve order


def main() -> int:
    all_ok = True
    all_pdf_urls: list[str] = []

    for studio, url in STUDIOS.items():
        print(f"\n{'='*60}")
        print(f"Studio: {studio}")
        print(f"URL:    {url}")
        print(f"{'='*60}")

        try:
            resp = requests.get(url, headers=HEADERS, timeout=30)
            print(f"HTTP status: {resp.status_code}")
            print(f"Response snippet (first 500 chars):\n{resp.text[:500]!r}")

            if resp.status_code != 200:
                print(f"ERROR: Expected 200, got {resp.status_code}")
                all_ok = False
                continue

            pdf_urls = extract_pdf_urls(resp.text, url)
            print(f"\nDiscovered {len(pdf_urls)} PDF URL(s):")
            for pdf_url in pdf_urls:
                print(f"  {pdf_url}")
            all_pdf_urls.extend(pdf_urls)

        except Exception as exc:
            print(f"ERROR fetching {url}: {exc}")
            all_ok = False

    print(f"\n{'='*60}")
    print("CDN reachability checks")
    print(f"{'='*60}")

    for pdf_url in all_pdf_urls:
        try:
            head = requests.head(pdf_url, headers=HEADERS, timeout=30, allow_redirects=True)
            print(f"HEAD {pdf_url}")
            print(f"  -> {head.status_code}")
            if head.status_code not in (200, 206):
                print(f"  WARNING: unexpected status {head.status_code}")
        except Exception as exc:
            print(f"ERROR on HEAD {pdf_url}: {exc}")

    print(f"\n{'='*60}")
    print(f"Result: {'ALL OK' if all_ok else 'SOME FAILURES — see above'}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
