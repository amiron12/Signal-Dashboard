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

---

## Tech stack

**Backend (Python 3.10+)**

| Piece | What it's for |
| --- | --- |
| FastAPI + uvicorn | HTTP API the dashboard talks to |
| pydantic | `SignalEvent` — the one data shape everything moves in |
| requests | every outbound HTTP call |
| beautifulsoup4 | HTML/XML parsing in the receivers |
| feedparser | Google News RSS |
| APScheduler | cron scheduling for unattended runs |
| PyYAML | reads `config/config.yaml` |
| sqlite3 (stdlib) | storage, single `signals.db` file |

**Frontend**

| Piece | What it's for |
| --- | --- |
| React 18 | UI |
| Vite 5 | dev server + build |
| recharts | the trend line chart |

No ORM, no state library, no build step on the Python side. Deliberately.

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

## How it all works

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

The only receiver-specific code outside a receiver file is the dashboard card
that renders it. Adding a receiver touches nothing in storage or the API.

### One run

1. Something calls `run_receiver(receiver)` ([core/runner.py](core/runner.py)) —
   either `POST /scan` or the scheduler.
2. It reads the currently tracked company **on every run** from the `settings`
   table, so editing the company in the dashboard takes effect on the next
   scheduled run with no restart.
3. `receiver.collect(name, url)` returns a list of `SignalEvent`. It never
   raises — a failure comes back as `status="error"` with a message.
4. Each event is appended to the `events` table. Nothing is ever updated or
   deleted; history is the point.

`POST /scan` and the scheduler share this exact path, so a receiver disabled in
`config.yaml` is skipped by both.

### Reading it back

`GET /history?company=X&receiver=Y` returns every event, oldest first. The
dashboard loads all three receivers' histories once, then:

- **cards** render `history[history.length - 1]` — the latest run
- **trend chart** renders the whole series, client-side switching between
  receivers with no refetch

### Missing data is never faked

A signal that's `null` or absent entirely — check failed, site genuinely has
nothing, or the run predates the check existing — renders as `unknown` and stays
uncolored. A red cube always means "we looked and it was bad", never "we never
looked". The trend chart drops those points rather than plotting them as zero.
`Cube.jsx`'s `scored()` / `binary()` helpers enforce this, which is why every
cube goes through one of them.

### Outbound HTTP etiquette

Every request in the project goes through [core/fetch.py](core/fetch.py) —
receivers never call `requests` directly:

- `fetch(url)` — real User-Agent, 0.5s delay before the request, 10s timeout.
  Returns `(response, elapsed_ms)`. For documented feed/API endpoints (Google
  News RSS, the Wikipedia API) and for `robots.txt` itself.
- `fetch_page(url)` — same, plus a **robots.txt check first**. For crawling a
  page on someone's site. Raises `PermissionError` if disallowed.

---

## The receivers

### `seo_onpage`

Fetches the company homepage once, parses it, runs a list of small checks over
the same soup:

`title_present` / `title_length`, `meta_description_present` /
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
   `templates` and **samples 10 pages** (`SAMPLE_PER_BUCKET`) — the first N
   sorted URLs per bucket, so they're the *same* pages every run. That's
   deliberate: this dashboard plots signals over time, and a fresh random sample
   each scan would make the line move on sampling noise rather than on anything
   the site actually did.
3. Fetches each sampled page once and, off the same soup, counts JSON-LD
   `@type`s that answer engines consume (`FAQPage`, `HowTo`, `Article`) and
   headings that read as questions.

Signals: `llms_txt_present`, `sitemap_url_count`, `sitemap_files_read`,
`sitemap_scan_truncated`, `pages_updated_last_30d`, `faq_headings_sampled`,
`answer_schema_pages`, `wikipedia_entry_exists`.

Its three sub-checks each make their own requests, so they fail independently: a
flaky sitemap drops that group of signals — which the dashboard shows as
`unknown` — instead of discarding the ones that worked.

### `news_mentions`

Hits Google News RSS for the company name, filters entries to the last
`lookback_days`, emits `mention_count` and a `mentions[]` list of
headline/link/published.

---

## Adding a receiver

1. Write `receivers/your_thing.py`:

   ```python
   class YourThingReceiver(Receiver):
       name = "your_thing"          # must match the config.yaml key

       def collect(self, company: str, target_url: str) -> list[SignalEvent]:
           try:
               response, elapsed_ms = fetch_page(target_url)
               ...
               return [SignalEvent(receiver=self.name, company=company,
                                   target_url=target_url,
                                   timestamp=datetime.now(timezone.utc),
                                   status="ok", signals={...})]
           except Exception as e:
               return [SignalEvent(..., status="error", error_message=str(e))]
   ```

   Two rules: `collect` **must not raise**, and every outbound call goes through
   `fetch()` / `fetch_page()`.

2. Add it to `config/config.yaml` under `receivers:` with `enabled` and
   `schedule`.
3. Add it to the list in `build_receivers()` ([core/runner.py](core/runner.py)).
4. Add a card component in `dashboard/src/` and wire it into
   [App.jsx](dashboard/src/App.jsx)'s `RECEIVERS` array and grid.

### Adding a signal to an existing receiver

- **`seo_onpage`** — write a `soup -> dict` function and append it to `CHECKS`.
  One function, one line.
- **`geo_readiness`** — write a `(company, target_url) -> dict` function and
  append it to `CHECKS`. If it throws, its keys are simply absent from the
  event, which the dashboard reads as `unknown`.
- Then add a `Cube` for it in the matching dashboard card, via `scored()` or
  `binary()` so the missing case is handled.

---

## Configuration

### `config/config.yaml`

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

Nothing here needs a restart — edit the file, save it, and the next runs use
the new values:

- `enabled` is read **per `/scan` call**, so toggling it takes effect on the
  next scan with no API restart.
- The scheduler **re-reads this file every minute**, so an edited `schedule`,
  `enabled` flag, or receiver option (like `lookback_days`) applies within a
  minute: the receiver is rescheduled, dropped, or added in place. Receivers
  you didn't touch keep the run they already had pending.
- If the file is mid-save or has a typo (a bad cron string, a missing key),
  the scheduler logs the error and keeps running on the last good config,
  then picks up the fix on the next reload.

### Changing the tracked company

`config.yaml`'s `company:` block only seeds the database the first time
`get_company()` runs. After that the company lives in the `settings` table and
is edited in the dashboard nav bar (name + URL, then **Save**) or via the API:

```bash
curl -X POST localhost:8000/company \
  -H 'Content-Type: application/json' \
  -d '{"name": "Acme", "url": "https://acme.com"}'
```

To go back to the YAML value, delete `signals.db` (which also drops all history)
or POST the value you want.

### Other knobs

| Setting | Where | Default |
| --- | --- | --- |
| `USER_AGENT`, `REQUEST_DELAY_SECONDS`, `REQUEST_TIMEOUT_SECONDS` | [core/fetch.py](core/fetch.py) | 0.5s delay, 10s timeout |
| `MAX_SITEMAPS_READ` — cap on sitemap files per scan | [receivers/geo_readiness.py](receivers/geo_readiness.py) | 10 |
| `SAMPLE_PER_BUCKET` — pages sampled per content type | [receivers/geo_readiness.py](receivers/geo_readiness.py) | 10 total |
| `CONTENT_TYPES` — path segments that define each bucket | [receivers/geo_readiness.py](receivers/geo_readiness.py) | — |
| `MISFIRE_GRACE_SECONDS` — how late a missed cron run may still fire | [core/scheduler.py](core/scheduler.py) | 3600 |
| `RELOAD_SECONDS` — how often the scheduler re-reads `config.yaml` | [core/scheduler.py](core/scheduler.py) | 60 |
| `DB_PATH` | [core/storage.py](core/storage.py) | `signals.db` |
| `API_BASE` — where the dashboard looks for the API | [dashboard/src/api.js](dashboard/src/api.js) | `http://localhost:8000` |
| CORS allowed origin | [api/main.py](api/main.py) | `http://localhost:5173` |

Changing the API port or the Vite port means changing the last two together.

---

## Running it

### 1. Backend

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn api.main:app --reload
```

Serves on `http://localhost:8000`. `signals.db` and its tables are created
automatically on first use. Interactive API docs at
`http://localhost:8000/docs`.

### 2. Dashboard

In a second terminal:

```bash
cd dashboard
npm install
npm run dev
```

Open `http://localhost:5173`. Set the company in the nav bar if you want a
different one, then hit **Scan now** — it runs every enabled receiver
synchronously and takes a few seconds (`geo_readiness` alone can fetch ~25 URLs
— up to 10 sitemaps plus 10 sampled pages — with a 0.5s delay between each, so
give it up to a minute on a large site). The cards
fill in; the trend chart appears once there's more than one run.

### 3. Scheduler (optional)

Only needed for unattended runs. Its own process, alongside the API:

```bash
python -m core.scheduler
```

It schedules one cron job per enabled receiver and logs each run. It writes to
the same `signals.db`, so scheduled results show up in the dashboard on its next
refresh. It re-reads `config/config.yaml` every minute, so you can change a
schedule while it runs and leave it running. The API and dashboard work fine
without it — `Scan now` covers manual use.

### API endpoints

| Method | Path | Does |
| --- | --- | --- |
| `GET` | `/company` | currently tracked company |
| `POST` | `/company` | set it — `{"name": ..., "url": ...}` |
| `GET` | `/history?company=X&receiver=Y` | all events, oldest first (`receiver` optional) |
| `POST` | `/scan` | run every enabled receiver now, returns the new events |

Scanning without the dashboard:

```bash
curl -X POST localhost:8000/scan | python3 -m json.tool
```
