# Working agreement for this project

- The user makes all core decisions — architecture, scope, what gets built
  next, what a piece should do. Do not assume what should be delivered;
  propose options or ask instead of picking for them.
- Keep code very simple. No over-engineering: no speculative abstractions,
  no config/flags for hypothetical future needs, no cleverness. This is a
  take-home assignment the user needs to explain and modify live on a call.
- Build incrementally and get review before widening scope (see PLAN.md for
  current sequencing — one working vertical slice before adding receivers).
- Every outbound HTTP request in this project must respect the basics: a
  real User-Agent, a small delay between requests, and (when crawling a
  page on someone's site, not hitting a documented feed/API endpoint) a
  robots.txt check first. Use `core/fetch.py`'s `fetch()` (User-Agent +
  delay) or `fetch_page()` (adds robots.txt check) rather than calling
  `requests` directly — every receiver's outbound calls should go through
  one of these two.
