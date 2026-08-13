from pydantic import BaseModel
from datetime import datetime
from typing import Literal, Any

class SignalEvent(BaseModel):
    receiver: str                          # "seo_onpage", "geo_readiness", "news_mentions"
    company: str                           # e.g. "acme-corp"
    target_url: str                        # what was actually fetched
    timestamp: datetime
    status: Literal["ok", "error"]
    signals: dict[str, Any] = {}           # the actual measurements, receiver-specific
    error_message: str | None = None       # populated only if status == "error"