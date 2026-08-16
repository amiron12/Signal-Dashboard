import json
import warnings
from datetime import datetime, timezone
from urllib.parse import quote, urlparse

import requests
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

from core.fetch import fetch, fetch_page
from core.models import SignalEvent
from core.receiver import Receiver

FAQ_PHRASES = ("faq", "frequently asked questions")

# Sites split their sitemap across children (monday.com has 6, and some of
# those are themselves indexes). We follow indexes wherever they nest, but
# stop after this many files so a site with hundreds of child sitemaps can't
# turn one scan into hundreds of requests. When we do stop early,
# sitemap_scan_truncated says so rather than silently undercounting.
MAX_SITEMAPS_READ = 10

# The sampling frame: the page types answer engines actually quote from.
# Marketing pages rarely get cited; docs, FAQs and blog posts do. These
# buckets exist to pick which pages get fetched below — nothing counts them.
#
# A marker must match a whole path SEGMENT, not appear anywhere in the path.
# Substring matching put a blog post called "help-steer-teams-through-the-
# covid-19-crisis" in docs_support, which is indefensible.
CONTENT_TYPES = {
    "docs_support": ("docs", "support", "help", "hc"),
    "blog": ("blog",),
    "faq": ("faq", "faqs"),
    "templates": ("templates",),
}

# The markup answer engines actually consume. FAQPage never travels alone —
# it comes with Question/Answer — but these three are what we report on.
ANSWER_ENGINE_TYPES = ("FAQPage", "HowTo", "Article")

# How many pages to sample per content bucket, 10 in total. The homepage is
# deliberately absent: check_schema_types already measures it, and sampling
# it again would cost a second fetch of the same page.
#
# Picks are the first N sorted URLs in each bucket, so they are the SAME
# pages on every run. That's the point — this dashboard plots signals over
# time, and a fresh random sample each scan would make the line move on
# sampling noise rather than on anything the site did.
SAMPLE_PER_BUCKET = {
    "blog": 4,
    "faq": 2,
    "docs_support": 2,
    "templates": 2,
}

# We read sitemap.xml with html.parser (it finds <lastmod> fine) rather than
# taking on an lxml dependency just for one tag. This silences bs4's warning
# about that choice.
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)


def _site_root(target_url: str) -> str:
    parsed = urlparse(target_url)
    return f"{parsed.scheme}://{parsed.netloc}"


def check_schema_types(soup: BeautifulSoup, company: str, target_url: str) -> dict:
    """Which JSON-LD @type values a page declares (FAQPage, Article, ...).
    Types are what an answer engine keys off, so we collect the values rather
    than just presence like seo_onpage's jsonld_present.

    No longer a check in its own right: run against the homepage it only ever
    reported Organization/WebSite/SoftwareApplication, none of which an answer
    engine can quote. It's now the per-page helper behind
    `answer_schema_pages`, applied to the sampled content pages instead."""
    types = set()
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            data = json.loads(script.string or "")
        except (json.JSONDecodeError, TypeError):
            continue  # one malformed block shouldn't lose the others
        types.update(_collect_types(data))
    return {"schema_types_found": sorted(types)}


def _collect_types(data) -> list[str]:
    """@type can sit at any depth — inside @graph, inside a nested entity."""
    found = []
    if isinstance(data, dict):
        value = data.get("@type")
        if isinstance(value, str):
            found.append(value)
        elif isinstance(value, list):
            found.extend(v for v in value if isinstance(v, str))
        for nested in data.values():
            found.extend(_collect_types(nested))
    elif isinstance(data, list):
        for item in data:
            found.extend(_collect_types(item))
    return found


def check_faq_headings(soup: BeautifulSoup, company: str, target_url: str) -> dict:
    """Headings that read as questions — the shape answer engines quote from.

    Like check_schema_types, this is a per-page helper rather than a check of
    its own: the homepage is the one page that never carries Q&A, so run
    there it reported 0 for a site whose /trustcenter/faqs has nine
    questions. It runs across the sampled content pages instead."""
    count = 0
    for heading in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
        text = heading.get_text(strip=True).lower()
        if text.endswith("?") or any(phrase in text for phrase in FAQ_PHRASES):
            count += 1
    return {"faq_heading_count": count}


def check_llms_txt(soup: BeautifulSoup, company: str, target_url: str) -> dict:
    """/llms.txt is the emerging convention for telling LLMs what a site is."""
    try:
        fetch_page(f"{_site_root(target_url)}/llms.txt")
        return {"llms_txt_present": True}
    except requests.HTTPError:
        return {"llms_txt_present": False}  # a 404 is the answer, not a failure


def _sitemaps_from_robots(site_root: str) -> list[str]:
    """The Sitemap: lines in robots.txt. Guessing /sitemap.xml is wrong on
    plenty of sites — monday.com's robots.txt points at sitemap_index.xml,
    and the guessed path is only 1 of its 6 sitemaps."""
    try:
        # robots.txt itself, not a page being crawled, so fetch() not fetch_page().
        response, _elapsed_ms = fetch(f"{site_root}/robots.txt")
    except requests.HTTPError:
        return []
    return [
        line.split(":", 1)[1].strip()
        for line in response.text.splitlines()
        if line.lower().startswith("sitemap:")
    ]


def _read_sitemaps(site_root: str) -> tuple[list[str], list[datetime], int, bool]:
    """Walk the site's sitemaps, following indexes wherever they nest (a
    child sitemap is often itself an index). MAX_SITEMAPS_READ is what
    bounds the walk, not depth. Returns
    (page urls, lastmod dates, files read, stopped early)."""
    queue = _sitemaps_from_robots(site_root) or [f"{site_root}/sitemap.xml"]
    seen, urls, dates = set(), [], []

    while queue:
        if len(seen) >= MAX_SITEMAPS_READ:
            return urls, dates, len(seen), True

        sitemap_url = queue.pop(0)
        if sitemap_url in seen:
            continue
        seen.add(sitemap_url)

        try:
            response, _elapsed_ms = fetch_page(sitemap_url)
        except requests.HTTPError:
            continue  # a dead sitemap in the index shouldn't sink the rest

        sitemap = BeautifulSoup(response.content, "html.parser")
        dates.extend(_parse_lastmods(sitemap))

        entries = [tag.get_text(strip=True) for tag in sitemap.find_all("loc")]
        if sitemap.find("sitemapindex"):
            queue.extend(entries)  # an index lists sitemaps, not pages
        else:
            urls.extend(entries)

    return urls, dates, len(seen), False


def _parse_lastmods(sitemap: BeautifulSoup) -> list[datetime]:
    dates = []
    for tag in sitemap.find_all("lastmod"):
        try:
            parsed = datetime.fromisoformat(tag.get_text(strip=True))
        except ValueError:
            continue
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)  # date-only entries
        dates.append(parsed)
    return dates


def check_sitemap(soup: BeautifulSoup, company: str, target_url: str) -> dict:
    """Size and freshness of the indexable surface. `pages_updated_last_30d`
    is None when the sitemap carries no <lastmod> at all — that's
    monday.com's case."""
    urls, dates, files_read, truncated = _read_sitemaps(_site_root(target_url))

    now = datetime.now(timezone.utc)
    fresh = None
    if dates:
        fresh = sum(1 for d in dates if (now - d).days <= 30)

    return {
        "sitemap_url_count": len(urls),
        "sitemap_files_read": files_read,
        "sitemap_scan_truncated": truncated,
        "pages_updated_last_30d": fresh,
        # Sampling needs the URL list, so it rides along with the walk rather
        # than being its own check — a second check would mean a second walk.
        **_sampled_page_signals(urls),
    }


def _in_bucket(url: str, markers: tuple) -> bool:
    segments = [s for s in urlparse(url).path.lower().split("/") if s]
    return any(segment in markers for segment in segments)


def _sample_urls(urls: list[str]) -> list[str]:
    picks = []
    for bucket, count in SAMPLE_PER_BUCKET.items():
        matches = sorted(u for u in urls if _in_bucket(u, CONTENT_TYPES[bucket]))
        picks.extend(matches[:count])
    return list(dict.fromkeys(picks))  # a URL can match two buckets


def _sampled_page_signals(urls: list[str]) -> dict:
    """Does the company's answer-oriented content carry the markup answer
    engines read, and does it read as Q&A at all? The homepage almost never
    does — monday.com's FAQPage is on /w/faqs and its Article markup is on
    blog posts — so both questions are asked of the content pages instead.
    Each page is fetched once and both checks run off the same soup."""
    found = {schema_type: 0 for schema_type in ANSWER_ENGINE_TYPES}
    faq_headings = 0

    for url in _sample_urls(urls):
        try:
            response, _elapsed_ms = fetch_page(url)
        except Exception:
            continue  # one dead sampled page shouldn't sink the sample

        page = BeautifulSoup(response.content, "html.parser")
        types = set(check_schema_types(page, "", url)["schema_types_found"])
        for schema_type in ANSWER_ENGINE_TYPES:
            if schema_type in types:
                found[schema_type] += 1
        # Every question across the sample, not the number of pages carrying
        # them: one page with nine questions is nine answerable things.
        faq_headings += check_faq_headings(page, "", url)["faq_heading_count"]

    return {
        "faq_headings_sampled": faq_headings,
        # Per-type page counts. The wall reads these as present/absent, one
        # cube per type; the counts are what the sample actually saw.
        "answer_schema_pages": found,
    }


def check_wikipedia(soup: BeautifulSoup, company: str, target_url: str) -> dict:
    """Whether an article titled with the company name exists. MediaWiki
    normalizes the first letter, so "monday.com" finds "Monday.com" — but
    this is an exact-title check, so a company whose article sits under a
    different name (e.g. "Acme Corporation" for "Acme") reads as False."""
    api_url = (
        "https://en.wikipedia.org/w/api.php"
        f"?action=query&titles={quote(company)}&format=json&formatversion=2"
    )
    response, _elapsed_ms = fetch(api_url)  # documented API, not a page crawl
    pages = response.json()["query"]["pages"]
    return {"wikipedia_entry_exists": not pages[0].get("missing", False)}


# Add a signal by writing a function above and appending it here with the
# keys it produces. Every check takes the same arguments and ignores what it
# doesn't need; the keys are what gets nulled out if the check fails.
CHECKS = [
    (check_llms_txt, ["llms_txt_present"]),
    (
        check_sitemap,
        [
            "sitemap_url_count",
            "sitemap_files_read",
            "sitemap_scan_truncated",
            "pages_updated_last_30d",
            "faq_headings_sampled",
            "answer_schema_pages",
        ],
    ),
    (check_wikipedia, ["wikipedia_entry_exists"]),
]


class GeoReadinessReceiver(Receiver):
    name = "geo_readiness"

    def collect(self, company: str, target_url: str) -> list[SignalEvent]:
        try:
            response, _elapsed_ms = fetch_page(target_url)
            soup = BeautifulSoup(response.content, "html.parser")
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

        # Three of these checks make their own requests, so they fail
        # independently: a flaky sitemap nulls one signal rather than
        # discarding the four that worked.
        signals = {}
        for check, keys in CHECKS:
            try:
                signals.update(check(soup, company, target_url))
            except Exception:
                signals.update({key: None for key in keys})

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
