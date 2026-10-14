"""Where API credentials come from - never from source code, never displayed, never logged.

Order: environment variable, then Streamlit secrets (``.streamlit/secrets.toml`` or the hosting platform's secret store).
The sidebar text field (type=password) is the last resort and lives only in the browser session.
"""
from __future__ import annotations

import os
from pathlib import Path

import streamlit as st

from . import config as C


def _has_secrets_file() -> bool:
    """Touching ``st.secrets`` without a secrets file makes some Streamlit versions print a (path-revealing) error in the UI."""
    candidates = (Path.home() / ".streamlit" / "secrets.toml", C.ROOT / ".streamlit" / "secrets.toml", Path.cwd() / ".streamlit" / "secrets.toml")
    return any(p.exists() for p in candidates) or bool(os.environ.get("STREAMLIT_SECRETS_FILE"))


def get_secret(name: str) -> str:
    val = os.environ.get(name, "")
    if val:
        return val.strip()
    if not _has_secrets_file():
        return ""
    try:                                   # st.secrets raises when no secrets file exists
        return str(st.secrets.get(name, "")).strip()
    except Exception:  # noqa: BLE001
        return ""


def cdse_credentials() -> tuple[str, str]:
    return get_secret("CDSE_CLIENT_ID"), get_secret("CDSE_CLIENT_SECRET")
