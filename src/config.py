from functools import lru_cache
from pathlib import Path

import yaml


@lru_cache(maxsize=1)
def load_config() -> dict:
    """Load the application config from disk once per process."""
    config_path = Path(__file__).resolve().parent.parent / "configs" / "config.yaml"
    with config_path.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file)
