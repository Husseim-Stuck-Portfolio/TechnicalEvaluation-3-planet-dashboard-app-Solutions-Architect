"""Adapter for the Planet Subscriptions API (Forest Carbon products).

Isolation boundary: the Streamlit app talks to this module only. All Planet
behaviour that cannot be verified offline (auth, rate limits, delivery
latency) lives behind this adapter and degrades to sample mode on failure.

Env vars (see .env.example):
    PLANET_API_KEY                   - never hard-coded, never shown in UI/logs
    PLANET_SUBSCRIPTIONS_URL         - default Subscriptions API endpoint
    PLANET_CANOPY_COVER_SOURCE_ID    - BYOC collection id (FCM Canopy Cover)
    PLANET_CANOPY_HEIGHT_SOURCE_ID   - BYOC collection id (FCM Canopy Height)
    PLANET_CARBON_SOURCE_ID          - BYOC collection id (FCM Aboveground Carbon)
"""
from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass

log = logging.getLogger(__name__)

DEFAULT_SUBSCRIPTIONS_URL = "https://api.planet.com/subscriptions/v1"
SOURCE_IDS = {
    "canopy_cover": "PLANET_CANOPY_COVER_SOURCE_ID",
    "canopy_height": "PLANET_CANOPY_HEIGHT_SOURCE_ID",
    "aboveground_carbon": "PLANET_CARBON_SOURCE_ID",
}


class PlanetAuthError(Exception):
    """401/403 - credentials missing or insufficient permissions."""


class PlanetRateLimitError(Exception):
    """429 - back off and retry later."""


class PlanetRequestError(Exception):
    """Any other non-success response from the Subscriptions API."""


@dataclass
class SubscriptionResult:
    subscription_id: str
    status: str
    delivered: bool


def api_key() -> str | None:
    key = os.getenv("PLANET_API_KEY")
    return key if key else None  # never logged, never rendered


def _headers() -> dict[str, str]:
    key = api_key()
    if not key:
        raise PlanetAuthError(
            "PLANET_API_KEY not set. Copy .env.example to .env and add your key, "
            "or run in sample-data mode."
        )
    return {"Authorization": f"api-key {key}", "Content-Type": "application/json"}


def _check_status(resp, action: str) -> None:
    code = resp.status_code
    if code in (401, 403):
        raise PlanetAuthError(f"{action}: HTTP {code} - check account access "
                              f"and Monitoring Credits for sandbox data.")
    if code == 429:
        raise PlanetRateLimitError(f"{action}: HTTP 429 - rate limited.")
    if code == 404:
        raise PlanetRequestError(f"{action}: HTTP 404 - unknown resource.")
    if code >= 500:
        raise PlanetRequestError(f"{action}: HTTP {code} - Planet server error.")
    if code >= 400:
        raise PlanetRequestError(f"{action}: HTTP {code} - {resp.text[:300]}")


def build_subscription_request(aoi_geojson: dict, start: str, end: str) -> dict:
    """Assemble a Subscriptions API request for the three FCM layers."""
    sources = []
    for env_var in SOURCE_IDS.values():
        collection = os.getenv(env_var)
        if collection:
            sources.append({
                "type": "catalog",
                "parameters": {
                    "geometry": aoi_geojson,
                    "start_time": start,
                    "end_time": end,
                    "rrule": "FREQ=MONTHLY;INTERVAL=3",  # quarterly cadence
                },
            })
    if not sources:
        raise PlanetRequestError("No Planet source IDs configured. Set the "
                                 "PLANET_*_SOURCE_ID env vars (see .env.example).")
    return {"name": "forestguard-eudr-demo", "source": {"type": "multi",
            "parameters": {"items": sources}}}


def create_subscription(session, request_body: dict,
                        base_url: str | None = None) -> str:
    url = (base_url or os.getenv("PLANET_SUBSCRIPT_URL",
           DEFAULT_SUBSCRIPTIONS_URL)).rstrip("/")
    resp = session.post(f"{url}/subscriptions", json=request_body,
                        headers=_headers(), timeout=30)
    _check_status(resp, "create subscription")
    return resp.json()["id"]


def poll_until_delivered(session, subscription_id: str,
                         base_url: str | None = None,
                         max_wait_s: int = 600,
                         initial_backoff_s: float = 5.0) -> SubscriptionResult:
    """Poll with exponential backoff; production would use webhooks instead."""
    url = (base_url or os.getenv("PLANET_SUBSCRIPT_URL",
           DEFAULT_SUBSCRIPTIONS_URL)).rstrip("/")
    waited, backoff = 0.0, initial_backoff_s
    while waited < max_wait_s:
        resp = session.get(f"{url}/subscriptions/{subscription_id}",
                           headers=_headers(), timeout=30)
        _check_status(resp, "poll subscription")
        status = resp.json().get("status", "unknown")
        if status in {"completed", "delivered"}:
            return SubscriptionResult(subscription_id, status, delivered=True)
        if status in {"failed", "cancelled"}:
            raise PlanetRequestError(f"subscription {subscription_id} -> {status}")
        time.sleep(backoff)
        waited += backoff
        backoff = min(backoff * 2, 60.0)
    raise TimeoutError(f"subscription {subscription_id} not delivered after "
                       f"{max_wait_s}s")
