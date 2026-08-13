from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core import storage
from core.config import load_config
from core.models import SignalEvent
from receivers.news_mentions import NewsMentionsReceiver
from receivers.seo_onpage import SeoOnpageReceiver

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
    ]


@app.get("/company")
def get_company():
    config = load_config()
    return config["company"]


@app.get("/history", response_model=list[SignalEvent])
def get_history(company: str, receiver: str | None = None):
    return storage.get_history(company, receiver=receiver)


@app.post("/scan", response_model=list[SignalEvent])
def scan():
    config = load_config()
    company = config["company"]["name"]
    url = config["company"]["url"]

    all_events = []
    for receiver in _build_receivers(config):
        events = receiver.collect(company, url)
        for event in events:
            storage.save_event(event)
        all_events.extend(events)

    return all_events
