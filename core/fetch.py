import time
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import requests

USER_AGENT = "SignalDashboardBot/1.0 (+https://example.com/bot)"
REQUEST_DELAY_SECONDS = 0.5
REQUEST_TIMEOUT_SECONDS = 10


def fetch_page(url: str) -> tuple[requests.Response, float]:
    """Fetch url with a real User-Agent, respecting robots.txt.
    Returns (response, elapsed_ms). Raises if fetch fails or is disallowed."""
    _check_robots_allowed(url)
    time.sleep(REQUEST_DELAY_SECONDS)

    start = time.perf_counter()
    response = requests.get(
        url, headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT_SECONDS
    )
    elapsed_ms = (time.perf_counter() - start) * 1000

    response.raise_for_status()
    return response, elapsed_ms


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
