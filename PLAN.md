# PLAN

## Strategy

Build one thin vertical slice end-to-end first — `news_mentions` only, from
receiver through to a real dashboard in the browser — before widening to the
other receivers. This proves the architecture works with a real
receiver/storage/API/dashboard round trip before we multiply it by three.

Within this slice, prioritize a **manual trigger** (`POST /scan`) over the
scheduler. APScheduler cron wiring is deferred until the manual path is
proven — we don't want to wait on a 9am cron job to find out something's
broken.

## Architecture (unchanged)

```
Config (YAML) → Scheduler → Receivers → Storage (SQLite) → API (FastAPI) → Dashboard (React/Vite)
```

Every receiver implements `Receiver.collect(company, target_url) -> list[SignalEvent]`
and must never raise. Storage, API, and dashboard only ever deal in
`SignalEvent` — no receiver-specific code outside the receiver files and the
dashboard's per-card rendering.

## Status

### Done
- [x] `core/models.py` — `SignalEvent` (given)
- [x] `core/receiver.py` — `Receiver` ABC (given)
- [x] `core/config.py` — YAML loader (given)
- [x] `config/config.yaml` (given)
- [x] `core/__init__.py`, `receivers/__init__.py`, `requirements.txt`, `.gitignore`
- [x] `receivers/news_mentions.py` — real Google News RSS implementation,
      filters by `lookback_days`, emits `mention_count` + `mentions[]`
- [x] `core/storage.py` — SQLite `events` table, `save_event()`,
      `get_history(company, receiver=None, since=None)`
- [x] Verified: receiver → `SignalEvent` → `save_event` → `get_history`
      round-trips correctly

- [x] `api/main.py` — FastAPI app with `POST /scan`, `GET /history`,
      `GET /company`. CORS enabled for the Vite dev server.
- [x] `dashboard/` — minimal Vite + React (JS) app: shows current company,
      "Scan now" button, news_mentions snapshot card, recharts trend line
      once >1 run exists
- [x] Fixed `news_mentions.py` to fetch via `requests` (bundles its own CA
      bundle via certifi) instead of letting `feedparser` fetch directly via
      `urllib` (relies on the OS trust store) — makes the receiver work
      the same on any machine without manual cert setup
- [x] **Slice proven end-to-end**: "Scan now" in the browser produces a real
      mention count and headline list, confirmed working

- [x] `core/fetch.py` — shared fetch helper: `fetch(url)` (real User-Agent +
      small delay) and `fetch_page(url)` (adds a robots.txt check on top,
      for crawling a page on someone's site)
- [x] `receivers/seo_onpage.py` — signals: title present/length, meta
      description present/length, h1_count, alt_coverage_pct, jsonld_present,
      page_load_time_ms. Each signal is a small `soup -> dict` function
      listed in `CHECKS`, so adding a signal is a one-function, one-line
      change. Wired into `/scan` and a dashboard card
      (`SeoOnpageCard.jsx`) — proven end-to-end against a real site.
- [x] `news_mentions.py` refactored onto the same `core/fetch.py` helper for
      consistency (uses `fetch()`, not `fetch_page()` — Google News RSS is a
      documented feed endpoint, not a site crawl; see note below)

### Next (not yet decided which — user's call)
- [ ] `scheduler.py` — APScheduler cron wiring, reads `config.yaml`,
      registers a job per enabled receiver calling the same
      collect→save path `POST /scan` already uses
- [ ] `receivers/geo_readiness.py`
- [ ] Widen dashboard to render the geo_readiness card
- [ ] `POST /company` — update tracked company in config

## Notes / decisions
- Scheduler is explicitly deprioritized until the manual-trigger slice works
  — cron jobs are a bad way to debug a first integration.
- `POST /scan` and the future scheduler job will share the same
  collect→save logic so there's only one code path to get right.
- No LLM calls anywhere in the running system (hard requirement, unchanged).
- **Crawling etiquette is a standing project rule** (see CLAUDE.md): every
  outbound HTTP call goes through `core/fetch.py`. `fetch_page()` (adds a
  robots.txt check) is for crawling arbitrary pages on someone's site —
  `seo_onpage` and `geo_readiness` use this. `fetch()` (User-Agent + delay,
  no robots.txt check) is for hitting a documented feed/API endpoint —
  `news_mentions` uses this, since Google News' own robots.txt disallows
  `/rss/search` and a strict robots.txt check would break the feature
  entirely; the RSS search endpoint isn't a page being crawled.
