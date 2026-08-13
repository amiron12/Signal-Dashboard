from datetime import datetime, timezone

from bs4 import BeautifulSoup

from core.fetch import fetch_page
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
