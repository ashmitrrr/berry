"""User settings: ~/.berry/config.json -- berry's first config file.

Same conventions as state.py's state.json: same directory, JSON on
disk, and defensive loading -- a missing or corrupt file just means
defaults, never an error. Today the only section is "ai", which stays
empty unless the user opts into the wake-time check-in (see ai.py).
"""

import json
from copy import deepcopy
from pathlib import Path

CONFIG_DIR = Path.home() / ".berry"
CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULT_OLLAMA_URL = "http://localhost:11434"

DEFAULT_CONFIG: dict = {
    "ai": {
        # "ollama", "anthropic", or "openai"; None keeps the check-in off
        "backend": None,
        # backend-specific default is used when None (see ai.py)
        "model": None,
        # only for the API backends; always user-supplied, never bundled
        "api_key": None,
        "ollama_url": DEFAULT_OLLAMA_URL,
    },
}


def merge_config(user: dict) -> dict:
    """Overlay a user config onto the defaults (one level deep).

    Unknown top-level keys are kept as-is so a config written by a
    newer berry doesn't lose data when read by an older one.
    """
    merged = deepcopy(DEFAULT_CONFIG)
    for key, value in user.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = {**merged[key], **value}
        else:
            merged[key] = value
    return merged


def load_config(path: Path | None = None) -> dict:
    """Read the config, tolerating a missing, corrupt, or unreadable file."""
    path = CONFIG_FILE if path is None else path
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        return deepcopy(DEFAULT_CONFIG)
    if not isinstance(data, dict):
        return deepcopy(DEFAULT_CONFIG)
    return merge_config(data)


def save_config(config: dict, path: Path | None = None) -> None:
    path = CONFIG_FILE if path is None else path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, indent=2))
