# Signal Dashboard

Tracks a company's public digital footprint over time. Small "receivers" go out
and measure things — on-page SEO, answer-engine (GEO) readiness, news mentions —
each run is stored as a timestamped event, and a React dashboard renders the
latest run as a wall of signal cubes plus a trend chart over history.

```
config/config.yaml → runner → receivers → SQLite → FastAPI → React dashboard
                       ↑
              POST /scan  or  cron scheduler
```

**Backend** (Python 3.10+): FastAPI + uvicorn, pydantic (`SignalEvent`),
requests, beautifulsoup4, feedparser (Google News RSS), APScheduler (cron),
PyYAML, stdlib sqlite3 — one `signals.db` file.
**Frontend**: React 18, Vite 5, recharts.

No ORM, no state library, no build step on the Python side. Deliberately.

---

## Running it

**Backend**

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn api.main:app --reload
```

Serves on `http://localhost:8000`. `signals.db` and its tables are created
automatically on first use. Interactive API docs at `/docs`.

**Dashboard** — in a second terminal:

```bash
cd dashboard
npm install
npm run dev
```

Open `http://localhost:5173`, set the company in the nav bar, then hit **Scan
now**. It runs every enabled receiver synchronously — `geo_readiness` alone can
fetch ~25 URLs with a 0.5s delay between each, so give it up to a minute on a
large site. The cards fill in; click the chart icon on a cube to see that
signal's trend over past runs.

**Scheduler** — optional, only for unattended runs. Its own process alongside
the API:

```bash
python -m core.scheduler
```

One cron job per enabled receiver, logged, writing to the same `signals.db`, so
scheduled results show up in the dashboard on its next refresh. `Scan now`
covers manual use without it.

### API

| Method | Path | Does |
| --- | --- | --- |
| `GET` | `/company` | currently tracked company |
| `POST` | `/company` | set it — `{"name": ..., "url": ...}` |
| `GET` | `/history?company=X&receiver=Y` | all events, oldest first (`receiver` optional) |
| `POST` | `/scan` | run every enabled receiver now, returns the new events |

```bash
curl -X POST localhost:8000/scan | python3 -m json.tool
```

---

## Layout

```
config/config.yaml       company + which receivers run, on what cron
core/
  models.py              SignalEvent — the contract between all layers
  receiver.py            Receiver ABC — collect(company, url) -> [SignalEvent]
  config.py              YAML loader
  fetch.py               the only place that makes HTTP requests
  storage.py             SQLite: save_event / get_history / get|set_company
  runner.py              build_receivers() + run_receiver() — the shared path
  scheduler.py           APScheduler process, cron-driven
receivers/
  seo_onpage.py          on-page SEO of the company homepage
  geo_readiness.py       answer-engine readiness across sampled site pages
  news_mentions.py       Google News RSS mentions
api/main.py              FastAPI: /company, /history, /scan
dashboard/src/           React app (one card component per receiver)
signals.db               created on first run, gitignored
```

---

## How it works

### The one data shape

Everything — storage, API, dashboard — only ever deals in `SignalEvent`
([core/models.py](core/models.py)):

```python
class SignalEvent(BaseModel):
    receiver: str          # "seo_onpage" | "geo_readiness" | "news_mentions"
    company: str
    target_url: str        # what was actually fetched
    timestamp: datetime
    status: Literal["ok", "error"]
    signals: dict[str, Any] = {}   # the measurements, receiver-specific
    error_message: str | None = None
```

### One run

1. `POST /scan` or the scheduler calls `run_receiver()`
   ([core/runner.py](core/runner.py)).
2. It reads the tracked company from the `settings` table **on every run**, so
   editing it in the dashboard takes effect on the next scheduled run with no
   restart.
3. `receiver.collect(name, url)` returns a list of `SignalEvent`. It never
   raises — a failure comes back as `status="error"` with a message.
4. Each event is appended to the `events` table. Nothing is ever updated or
   deleted.

Both callers share this exact path, so a receiver disabled in `config.yaml` is
skipped by both.

### Reading it back

`GET /history` returns every event, oldest first. The dashboard loads all three
receivers' histories once, then:

- **cards** render the latest run
- **trend chart** starts hidden. Six signals carry a chart icon in the corner of
  their cube; clicking one opens that signal's whole series, clicking it again
  closes it. The histories are already loaded, so switching needs no refetch.

### Missing data is never faked

A signal that's `null` or absent entirely — check failed, site genuinely has
nothing, or the run predates the check existing — renders as `unknown` and stays
uncolored. A red cube always means "we looked and it was bad", never "we never
looked". The trend chart drops those points rather than plotting them as zero.
`Cube.jsx`'s `scored()` / `binary()` helpers enforce this, which is why every
cube goes through one of them.

### Known weak spot: one fetch is a sample, not a fact

Missing data is handled. **Unstable data is not.** Each scan fetches a page once
and stores the result as though it were the page's state — but plenty of sites
don't serve one consistent page. A/B tests, personalization and rotating content
all mean two scans minutes apart can legitimately disagree, with nothing wrong
on either end.

`monday.com`'s homepage is served in two variants, alternating roughly per
request:

| | Hero headline | `h1_count` | `alt_coverage_pct` |
| --- | --- | --- | --- |
| A | "People and agents **working as one team**" | 2 | 21.2 |
| B | "People and agents **working better, together**" | 3 | 23.0 |

A human visitor is pinned to one variant by a cookie (`x-webflow-ab-test`).
`fetch()` keeps no cookies, so every scan is re-rolled — which is also what a
search crawler sees, so the un-pinned reading is arguably the honest one. The
consequence is that a trend line over `h1_count` or `alt_coverage_pct` is
plotting coin flips, and a real change hides inside the noise: variant B's
`<title>` really did go from 28 to 53 characters, but only grouping the runs by
variant makes that visible.

The same class of problem shows up elsewhere, from different causes:

- `page_load_time_ms` is network timing, not a property of the site (321–2042ms
  observed on one unchanged URL).
- `pages_updated_last_30d` is anchored to `now`, so a byte-identical sitemap
  gives a different number tomorrow.
- `mention_count` tracks a Google News ranking that reorders continuously.
- `faq_headings_sampled` is a sum over sampled pages, and a sampled page that
  times out is skipped silently — no denominator is recorded, so a dip can mean
  "fewer questions" or "one fetch failed".

**Why it isn't fixed here.** Identifying *which* variant you got is not
generally solvable: the same variant varies by a few bytes per request (nonces,
request IDs), hashing the extracted signals can't separate "different variant"
from "site changed", and client-side tests are invisible without running
JavaScript. Detecting *instability* is solvable — fetch each page a few times
per scan and record which signals disagreed — but it triples the request count,
and on a genuine 50/50 split three samples still miss the disagreement about a
quarter of the time. Until something like it exists, read a jumpy line as "this
signal may not be stable" rather than as a change the site made.

### One place that makes requests

Receivers never call `requests` directly — everything goes through
[core/fetch.py](core/fetch.py):

- `fetch(url)` — real User-Agent, 0.5s delay, 10s timeout. Returns
  `(response, elapsed_ms)`. For documented feed/API endpoints and `robots.txt`
  itself.
- `fetch_page(url)` — same, plus a **robots.txt check first**. For crawling a
  page on someone's site. Raises `PermissionError` if disallowed.

---

## The receivers

### `seo_onpage`

Fetches the company homepage once and runs a list of small checks over the same
soup: `title_present` / `title_length`, `meta_description_present` /
`meta_description_length`, `h1_count`, `alt_coverage_pct`, `jsonld_present`,
`robots_txt_present`, `page_load_time_ms`.

### `geo_readiness`

Whether the site is set up for answer engines (ChatGPT, Perplexity, AI
Overviews) to quote it. More involved than the others:

1. Reads `Sitemap:` lines from `robots.txt` (guessing `/sitemap.xml` is wrong on
   plenty of sites), then walks the sitemaps, following nested indexes, stopping
   after `MAX_SITEMAPS_READ` (10) files. If it stops early,
   `sitemap_scan_truncated` says so and the dashboard prints a "lower bound"
   note rather than quietly undercounting.
2. Buckets the URLs by path segment into `blog` / `faq` / `docs_support` /
   `templates` and **samples 10 pages** — the first N sorted URLs per bucket, so
   they're the *same* pages every run. Deliberate: a fresh random sample each
   scan would make the trend line move on sampling noise rather than on anything
   the site actually did.
3. Fetches each sampled page once and, off the same soup, counts JSON-LD
   `@type`s that answer engines consume (`FAQPage`, `HowTo`, `Article`) and
   headings that read as questions.

Signals: `llms_txt_present`, `sitemap_url_count`, `sitemap_files_read`,
`sitemap_scan_truncated`, `pages_updated_last_30d`, `faq_headings_sampled`,
`answer_schema_pages`, `wikipedia_entry_exists`.

### `news_mentions`

Hits Google News RSS for the company name, filters entries to the last
`lookback_days`, emits `mention_count` and a `mentions[]` list of
headline/link/published.

---

## Extending it

**A new receiver** — write `receivers/your_thing.py`:

```python
class YourThingReceiver(Receiver):
    name = "your_thing"          # must match the config.yaml key

    def collect(self, company: str, target_url: str) -> list[SignalEvent]:
        try:
            response, elapsed_ms = fetch_page(target_url)
            ...
            return [SignalEvent(..., status="ok", signals={...})]
        except Exception as e:
            return [SignalEvent(..., status="error", error_message=str(e))]
```

Two rules: `collect` **must not raise**, and every outbound call goes through
`fetch()` / `fetch_page()`. Then add it to `config/config.yaml` under
`receivers:` with `enabled` and `schedule`, to `build_receivers()`
([core/runner.py](core/runner.py)), and as a card component wired into
[App.jsx](dashboard/src/App.jsx)'s `RECEIVERS` array and grid.

**A new signal on an existing receiver** — write a function and append it to
that receiver's `CHECKS` list: `soup -> dict` for `seo_onpage`,
`(company, target_url) -> dict` for `geo_readiness`. One function, one line. If
it throws, its keys are simply absent from the event, which the dashboard reads
as `unknown`. Then add a `Cube` for it in the matching card, via `scored()` or
`binary()` so the missing case is handled.

---

## Configuration

```yaml
company:
  name: "monday.com"          # seeds the DB on first run only — see below
  url: "https://monday.com"

receivers:
  seo_onpage:
    enabled: true             # false = skipped by both /scan and the scheduler
    schedule: "0 9 * * *"     # standard 5-field cron, used by the scheduler
  news_mentions:
    enabled: true
    schedule: "0 9 * * *"
    lookback_days: 7          # receiver-specific option
```

Nothing here needs a restart. `enabled` is read per `/scan` call, and the
scheduler re-reads the file every minute — an edited `schedule`, `enabled` flag
or receiver option applies within a minute, with the receiver rescheduled,
dropped or added in place and untouched receivers keeping the run they already
had pending. If the file is mid-save or has a typo, the scheduler logs it and
keeps running on the last good config.

**Changing the tracked company.** The `company:` block only seeds the database
the first time `get_company()` runs. After that the company lives in the
`settings` table and is edited in the dashboard nav bar, or via
`POST /company`. To go back to the YAML value, delete `signals.db` (which also
drops all history) or POST the value you want.

**Other knobs**

| Setting | Where | Default |
| --- | --- | --- |
| `USER_AGENT`, `REQUEST_DELAY_SECONDS`, `REQUEST_TIMEOUT_SECONDS` | [core/fetch.py](core/fetch.py) | 0.5s delay, 10s timeout |
| `MAX_SITEMAPS_READ` — sitemap files per scan | [receivers/geo_readiness.py](receivers/geo_readiness.py) | 10 |
| `SAMPLE_PER_BUCKET` — pages sampled per content type | [receivers/geo_readiness.py](receivers/geo_readiness.py) | 10 total |
| `CONTENT_TYPES` — path segments that define each bucket | [receivers/geo_readiness.py](receivers/geo_readiness.py) | — |
| `MISFIRE_GRACE_SECONDS` — how late a missed cron run may still fire | [core/scheduler.py](core/scheduler.py) | 3600 |
| `RELOAD_SECONDS` — how often the scheduler re-reads `config.yaml` | [core/scheduler.py](core/scheduler.py) | 60 |
| `DB_PATH` | [core/storage.py](core/storage.py) | `signals.db` |
| `API_BASE` — where the dashboard looks for the API | [dashboard/src/api.js](dashboard/src/api.js) | `http://localhost:8000` |
| CORS allowed origin | [api/main.py](api/main.py) | `http://localhost:5173` |

Changing the API port or the Vite port means changing the last two together.

---

## Write-up

### Receiver / pipeline architecture, and why

```
config.yaml → build_receivers() → receiver.collect() → SignalEvent → SQLite → FastAPI → React
                                                                        ↑
                                                          POST /scan  or  cron scheduler
```

A receiver is one class with one method:
`collect(company, target_url) -> list[SignalEvent]`. That's the entire
contract. Three decisions hold the rest of the system together:

**One data shape, and `signals` is opaque.** Every layer below a receiver
only ever handles `SignalEvent`, and its `signals` field is just a dict that
gets JSON-encoded into one column. Storage doesn't know what a signal is, the
API doesn't either, and neither needs a migration when a receiver starts
emitting a new one. The only receiver-aware code outside a receiver file is
the dashboard card that draws it. That's what makes "add a signal" a
one-function, one-line change instead of a change to five files.

**Append-only.** `save_event` only ever inserts; nothing is updated or
deleted. History *is* the product — a single reading of `alt_coverage_pct`
says almost nothing, the line over thirty of them says whether anyone is
maintaining the site. Snapshot and trend then come from the same table:
cards read the last event, the chart reads all of them.

**One run path, and failures are contained.** `/scan` and the scheduler both
call `run_receiver()`, so a receiver disabled in `config.yaml` is skipped by
both and can't drift between them. Around that, failure is isolated at three
levels: `collect()` never raises (a dead site becomes `status="error"` on
that receiver, and the other two still run); inside `geo_readiness`, each
check is wrapped on its own, so a flaky sitemap drops its own signals rather
than the four that worked; inside the sampling loop, one dead page is
skipped rather than sinking the sample. Everything that drops out reads as
`unknown` on the wall, never as zero.

And every outbound request goes through `core/fetch.py`. One choke point
means the User-Agent, the delay and the robots.txt rule are properties of the
project rather than things each receiver has to remember.

The cost of keeping it this small: `/scan` is synchronous, so the HTTP
request blocks for as long as the crawl takes (up to a minute on a large
site), and SQLite means one writer. Both are fine for one company and three
receivers, and both are the first things to change if that stops being true.

### The signals, and why they're meaningful without an LLM

My first task of this project was deepening my knowledge on these topics,
I knew these terms but wanted to further understand how these signals really affect a company's exposure.
Once a page is scraped, gathering most of these signals is pretty simple, so I think the main point is how you use this data, not which of the signals to choose.

**On-page SEO** — `title_present` / `title_length`, `meta_description_present`
/ `meta_description_length`, `h1_count`, `alt_coverage_pct`, `jsonld_present`,
`robots_txt_present`, `page_load_time_ms`. These are the checks a search
engine's own documentation describes, and every one of them is a fact about
the HTML. There's no judgment involved in whether a `<title>` exists or
whether 21% of images carry alt text, which is exactly why it can be plotted:
if the line moves, someone changed the page.

**GEO readiness** — an answer engine can only quote a site it can find,
parse, and trust, so the receiver measures those preconditions rather than
the outcome:

- `llms_txt_present` — the emerging convention for telling an LLM what a site
  is. Publishing one is a deliberate act, so its presence is a real signal
  about intent.
- `sitemap_url_count`, `sitemap_files_read`, `pages_updated_last_30d` — how
  much indexable surface exists and whether it's alive. 
- `faq_headings_sampled` — headings phrased as questions. Answer engines
  quote answers to questions; content shaped as Q&A is the shape that gets
  quoted.
- `answer_schema_pages` — JSON-LD `@type`s that answer engines actually
  consume (`FAQPage`, `HowTo`, `Article`), counted on sampled content pages
  rather than the homepage, because that's where they live.
  there are more types that can be checked and can be usefull data, for now i sticked with these ones.
- `wikipedia_entry_exists` — cheap proxy for whether the company exists as an
  *entity* rather than just a website. Entity grounding is most of why a
  model will name a company unprompted.

**Off-site** — `mention_count` over a `lookback_days` window is the one
signal that isn't about the site at all. Press coverage is the raw material
both search ranking and model training pull from.


### What I'd add with more time

**An overall score.** I think the most valuable addition will be a scroing system that 
will actually give a proper indication on the website results. These signals are strong and have a big
impact over nothing at all, but generating a score will give the real value.

**Google Business Profile.** Review count, average rating, whether the
profile is claimed and filled in, how recently it was posted to. It's a big
chunk of how a company shows up in search, and it's a strong GEO signal too —
it's often what an answer engine repeats back about a business.

**Forums, not just news.** One Google News query is a narrow view. Reddit and
Hacker News are where people actually talk about a product, and they're
heavily represented in what LLMs were trained on. Worth keeping separate from
press coverage — a spike in each means a very different thing.



### Scraping, legal and rate-limit tradeoffs

**robots.txt is checked before every page crawl.** `fetch_page()` won't fetch
a disallowed URL. Two deliberate exceptions go through plain `fetch()`:
`robots.txt` itself (checking it before reading it is circular) and documented
API/feed endpoints — Google News RSS and the Wikipedia API — which are
published to be called, not crawled.

**Slow on purpose.** Identifiable User-Agent with a contact URL, 0.5s before
every request, 10s timeout, everything serial. A `geo_readiness` scan takes a
while because of this, which is the trade.

**`geo_readiness` looks at 10 pages, and 10 sitemap files.** That's the
biggest compromise in the project. Reading the whole site would give a real
number instead of a sample — monday.com has thousands of URLs and we judge its
answer-engine readiness off ten of them. But a full crawl is thousands of
requests into someone else's servers per scan, and a scan that takes hours.
So it's capped, and when the sitemap walk stops early
`sitemap_scan_truncated` is stored so the dashboard can say "at least this
many" instead of quietly reporting a smaller site than exists.

**We look like a bot, and we get the bot's version of the site.** Real UA, no
cookies, nothing persisted between scans, so a site running an A/B test
re-rolls us every time instead of pinning us like it would a visitor. That's
the honest thing to be — it's also what a search crawler sees — but it's why
some signals move between scans with nothing having changed. See
[the weak spot above](#known-weak-spot-one-fetch-is-a-sample-not-a-fact).
