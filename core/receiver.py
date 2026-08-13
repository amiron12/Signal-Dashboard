from abc import ABC, abstractmethod
from .models import SignalEvent

class Receiver(ABC):
    name: str  # must be set by subclass, matches the config key

    @abstractmethod
    def collect(self, company: str, target_url: str) -> list[SignalEvent]:
        """Run one measurement pass. Must not raise — catch internally,
        return a SignalEvent with status='error' on failure."""
        ...