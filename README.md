# Signal Dashboard


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


---
