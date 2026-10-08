from typing import Protocol

import httpx

from outthere.errors import AppError
from outthere.settings import Settings


class PlaceSearch(Protocol):
    def search(self, query: str) -> list[dict]: ...


class DisabledPlaces:
    def search(self, query: str) -> list[dict]:
        raise AppError("integration_disabled", "Place search is not configured", 503)


class GooglePlaces:
    """Optional Places API (New) adapter. Do not persist responses without reviewing terms."""

    def __init__(self, api_key: str, transport: httpx.BaseTransport | None = None):
        self.api_key = api_key
        self.transport = transport

    def search(self, query: str) -> list[dict]:
        fields = (
            "places.id,places.displayName,places.formattedAddress,"
            "places.location,places.googleMapsUri,places.attributions"
        )
        try:
            with httpx.Client(timeout=8, transport=self.transport) as client:
                response = client.post(
                    "https://places.googleapis.com/v1/places:searchText",
                    headers={"X-Goog-Api-Key": self.api_key, "X-Goog-FieldMask": fields},
                    json={"textQuery": query, "pageSize": 5},
                )
                response.raise_for_status()
                result = response.json()
                return [
                    {
                        "provider": "google",
                        "provider_id": place["id"],
                        "name": place.get("displayName", {}).get("text", ""),
                        "address": place.get("formattedAddress", ""),
                        "latitude": place.get("location", {}).get("latitude"),
                        "longitude": place.get("location", {}).get("longitude"),
                        "maps_url": place.get("googleMapsUri"),
                        "attributions": place.get("attributions", []),
                    }
                    for place in result.get("places", [])
                ]
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            raise AppError(
                "provider_unavailable", "Place search is temporarily unavailable", 502
            ) from exc


def make_places(settings: Settings) -> PlaceSearch:
    if settings.maps_provider == "google":
        key = settings.google_maps_api_key.get_secret_value()
        if not key:
            raise ValueError("Google Places requires OUTTHERE_GOOGLE_MAPS_API_KEY")
        return GooglePlaces(key)
    return DisabledPlaces()
