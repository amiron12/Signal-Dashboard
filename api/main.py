from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl

from core import storage
from core.config import load_config
from core.models import SignalEvent
from receivers.geo_readiness import GeoReadinessReceiver
from receivers.news_mentions import NewsMentionsReceiver
from receivers.seo_onpage import SeoOnpageReceiver


class CompanyUpdate(BaseModel):
    name: str
    url: HttpUrl

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _build_receivers(config: dict) -> list:
    lookback_days = config["receivers"]["news_mentions"]["lookback_days"]
    return [
        NewsMentionsReceiver(lookback_days=lookback_days),
        SeoOnpageReceiver(),
        GeoReadinessReceiver(),
    ]


@app.get("/company")
def get_company():
    return storage.get_company()


@app.post("/company")
def set_company(update: CompanyUpdate):
    return storage.set_company(update.name, str(update.url))


@app.get("/history", response_model=list[SignalEvent])
def get_history(company: str, receiver: str | None = None):
    return storage.get_history(company, receiver=receiver)


@app.post("/scan", response_model=list[SignalEvent])
def scan():
    config = load_config()
    tracked = storage.get_company()
    company = tracked["name"]
    url = tracked["url"]

    all_events = []
    for receiver in _build_receivers(config):
        events = receiver.collect(company, url)
        for event in events:
            storage.save_event(event)
        all_events.extend(events)

    return all_events
