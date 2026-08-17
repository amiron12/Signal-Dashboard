from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl

from core import storage
from core.config import load_config
from core.models import SignalEvent
from core.runner import build_receivers, run_receiver


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
    """Run every enabled receiver now. Same code path the scheduler uses, so
    a receiver turned off in config.yaml is skipped here too."""
    all_events = []
    for receiver in build_receivers(load_config()):
        all_events.extend(run_receiver(receiver))
    return all_events
