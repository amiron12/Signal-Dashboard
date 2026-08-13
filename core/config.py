import yaml
from pathlib import Path

def load_config(path: str = "config/config.yaml") -> dict:
    return yaml.safe_load(Path(path).read_text())