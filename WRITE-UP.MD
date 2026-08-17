
### architecture

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

### Signals

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

**An actual LLM-based GEO check.** Ask a few models a category question
("best work management software") and record whether the company gets named
and which URL gets cited. Answers vary run to run, so it'd have to be asked
several times and stored as a rate rather than a yes/no. That's the whole
reason it isn't here — it's the most expensive signal in the project — but it
measures the real outcome instead of a proxy.

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

