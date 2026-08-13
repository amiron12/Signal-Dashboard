from datetime import datetime, timedelta, timezone
from time import mktime
from urllib.parse import quote

import feedparser
import requests

from core.models import SignalEvent
from core.receiver import Receiver


class NewsMentionsReceiver(Receiver):
    name = "news_mentions"

    def __init__(self, lookback_days: int = 7):
        self.lookback_days = lookback_days

    def collect(self, company: str, target_url: str) -> list[SignalEvent]:
        feed_url = f"https://news.google.com/rss/search?q={quote(company)}"

        try:
            response = requests.get(feed_url, timeout=10)
            response.raise_for_status()
            parsed = feedparser.parse(response.content)
            if parsed.bozo and not parsed.entries:
                raise parsed.bozo_exception or RuntimeError("feed parse failed")

            cutoff = datetime.now(timezone.utc) - timedelta(days=self.lookback_days)
            mentions = []

            for entry in parsed.entries:
                if not getattr(entry, "published_parsed", None):
                    continue
                published = datetime.fromtimestamp(
                    mktime(entry.published_parsed), tz=timezone.utc
                )
                if published < cutoff:
                    continue
                mentions.append(
                    {
                        "headline": entry.get("title", ""),
                        "link": entry.get("link", ""),
                        "published": published.isoformat(),
                    }
                )

            return [
                SignalEvent(
                    receiver=self.name,
                    company=company,
                    target_url=feed_url,
                    timestamp=datetime.now(timezone.utc),
                    status="ok",
                    signals={
                        "mention_count": len(mentions),
                        "mentions": mentions,
                    },
                )
            ]
        except Exception as e:
            return [
                SignalEvent(
                    receiver=self.name,
                    company=company,
                    target_url=feed_url,
                    timestamp=datetime.now(timezone.utc),
                    status="error",
                    error_message=str(e),
                )
            ]
