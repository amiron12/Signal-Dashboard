import time
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import requests

USER_AGENT = "SignalDashboardBot/1.0 (+https://example.com/bot)"
REQUEST_DELAY_SECONDS = 0.5
REQUEST_TIMEOUT_SECONDS = 10


def fetch(url: str) -> tuple[requests.Response, float]:
    """Fetch url with a real User-Agent and a small delay before the request.
    Returns (response, elapsed_ms). Raises if the request fails.

    Use this for hitting a documented feed/API endpoint (e.g. Google News
    RSS). Use fetch_page() instead when crawling a page on someone's site —
    it adds a robots.txt check on top of this."""
    time.sleep(REQUEST_DELAY_SECONDS)

    start = time.perf_counter()
    response = requests.get(
        url, headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT_SECONDS
    )
    elapsed_ms = (time.perf_counter() - start) * 1000

    response.raise_for_status()
    return response, elapsed_ms


def fetch_page(url: str) -> tuple[requests.Response, float]:
    """Fetch a page for crawling: same as fetch(), but checks robots.txt
    first. Raises if fetch fails or robots.txt disallows it."""
    _check_robots_allowed(url)
    return fetch(url)


def _check_robots_allowed(url: str) -> None:
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"

    parser = RobotFileParser()
    parser.set_url(robots_url)
    try:
        parser.read()
    except OSError:
        return  # robots.txt unreachable — don't block the scan over it

    if not parser.can_fetch(USER_AGENT, url):
        raise PermissionError(f"robots.txt disallows fetching {url}")
