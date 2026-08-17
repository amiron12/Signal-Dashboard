from datetime import datetime, timezone
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from core.fetch import fetch, fetch_page
from core.models import SignalEvent
from core.receiver import Receiver


def check_title(soup: BeautifulSoup) -> dict:
    title = soup.find("title")
    text = title.get_text(strip=True) if title else ""
    return {
        "title_present": bool(text),
        "title_length": len(text),
    }


def check_meta_description(soup: BeautifulSoup) -> dict:
    meta = soup.find("meta", attrs={"name": "description"})
    content = meta.get("content", "").strip() if meta else ""
    return {
        "meta_description_present": bool(content),
        "meta_description_length": len(content),
    }


def check_h1(soup: BeautifulSoup) -> dict:
    return {"h1_count": len(soup.find_all("h1"))}


def check_alt_coverage(soup: BeautifulSoup) -> dict:
    images = soup.find_all("img")
    if not images:
        return {"alt_coverage_pct": 100.0}
    with_alt = sum(1 for img in images if img.get("alt", "").strip())
    return {"alt_coverage_pct": round(with_alt / len(images) * 100, 1)}


def check_jsonld(soup: BeautifulSoup) -> dict:
    jsonld_scripts = soup.find_all("script", attrs={"type": "application/ld+json"})
    return {"jsonld_present": len(jsonld_scripts) > 0}


def check_robots_txt(target_url: str) -> dict:
    """Whether the site publishes a /robots.txt at all. Takes the URL rather
    than the soup — it's the one check here that makes its own request, which
    is why it isn't in CHECKS below.

    fetch() and not fetch_page(): robots.txt is the crawl rules themselves,
    not a page being crawled, so checking robots.txt before reading it would
    be circular. Same call the sitemap walk in geo_readiness makes."""
    parsed = urlparse(target_url)
    try:
        fetch(f"{parsed.scheme}://{parsed.netloc}/robots.txt")
        return {"robots_txt_present": True}
    except requests.HTTPError:
        return {"robots_txt_present": False}  # a 404 is the answer, not a failure


# Add a new signal by writing a function above (soup -> partial signals dict)
# and appending it here.
CHECKS = [
    check_title,
    check_meta_description,
    check_h1,
    check_alt_coverage,
    check_jsonld,
]


class SeoOnpageReceiver(Receiver):
    name = "seo_onpage"

    def collect(self, company: str, target_url: str) -> list[SignalEvent]:
        try:
            response, elapsed_ms = fetch_page(target_url)
            soup = BeautifulSoup(response.content, "html.parser")

            signals = {"page_load_time_ms": round(elapsed_ms, 1)}
            for check in CHECKS:
                signals.update(check(soup))
            signals.update(check_robots_txt(target_url))

            return [
                SignalEvent(
                    receiver=self.name,
                    company=company,
                    target_url=target_url,
                    timestamp=datetime.now(timezone.utc),
                    status="ok",
                    signals=signals,
                )
            ]
        except Exception as e:
            return [
                SignalEvent(
                    receiver=self.name,
                    company=company,
                    target_url=target_url,
                    timestamp=datetime.now(timezone.utc),
                    status="error",
                    error_message=str(e),
                )
            ]
