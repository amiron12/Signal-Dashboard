"""The one collect -> save code path, shared by POST /scan and the scheduler.

Which receivers exist and whether each one runs at all is decided here, from
config.yaml's `enabled` flags, so both callers agree.
"""

from . import storage
from .models import SignalEvent
from .receiver import Receiver
from receivers.geo_readiness import GeoReadinessReceiver
from receivers.news_mentions import NewsMentionsReceiver
from receivers.seo_onpage import SeoOnpageReceiver


def build_receivers(config: dict) -> list[Receiver]:
    """One instance per receiver marked `enabled: true` in config.yaml."""
    settings = config["receivers"]
    receivers = [
        NewsMentionsReceiver(lookback_days=settings["news_mentions"]["lookback_days"]),
        SeoOnpageReceiver(),
        GeoReadinessReceiver(),
    ]
    return [r for r in receivers if settings[r.name]["enabled"]]


def run_receiver(receiver: Receiver) -> list[SignalEvent]:
    """Run one receiver against the currently tracked company and store what
    it produced. Reads the company on every run, so editing it in the
    dashboard takes effect on the next scheduled run without a restart."""
    company = storage.get_company()
    events = receiver.collect(company["name"], company["url"])
    for event in events:
        storage.save_event(event)
    return events
