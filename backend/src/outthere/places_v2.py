"""Google Autocomplete/Details session boundary; provider data is never persisted."""

from urllib.parse import quote
from uuid import UUID

import httpx
from pydantic import Field

from outthere.contracts import Input
from outthere.errors import AppError


class Area(Input):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    radius_m: int = Field(gt=0, le=50000)


class Search(Input):
    query: str = Field(min_length=2, max_length=160)
    session_token: UUID
    area: Area | None = None


class Details(Input):
    place_id: str = Field(min_length=1, max_length=240)
    session_token: UUID


CONTRACTS = {"places.search": ("query", Search), "places.details": ("query", Details)}


def handle(settings, name, data, transport=None):
    if settings.maps_provider != "google" or not settings.google_maps_api_key.get_secret_value():
        raise AppError("provider_unavailable", "Place search is not configured", 503)
    headers = {"X-Goog-Api-Key": settings.google_maps_api_key.get_secret_value()}
    try:
        with httpx.Client(timeout=8, transport=transport) as client:
            if name == "places.search":
                payload = {"input": data.query, "sessionToken": str(data.session_token)}
                if data.area:
                    payload["locationBias"] = {
                        "circle": {
                            "center": {
                                "latitude": data.area.latitude,
                                "longitude": data.area.longitude,
                            },
                            "radius": data.area.radius_m,
                        }
                    }
                headers["X-Goog-FieldMask"] = (
                    "suggestions.placePrediction.placeId,suggestions.placePrediction.text"
                )
                response = client.post(
                    "https://places.googleapis.com/v1/places:autocomplete",
                    headers=headers,
                    json=payload,
                )
            else:
                headers["X-Goog-FieldMask"] = (
                    "id,displayName,formattedAddress,location,googleMapsUri,attributions"
                )
                response = client.get(
                    f"https://places.googleapis.com/v1/places/{quote(data.place_id, safe='')}",
                    headers=headers,
                    params={"sessionToken": str(data.session_token)},
                )
            response.raise_for_status()
            result = response.json()
        if name == "places.search":
            return {
                "items": [
                    {
                        "place_id": s["placePrediction"]["placeId"],
                        "label": s["placePrediction"]["text"]["text"],
                    }
                    for s in result.get("suggestions", [])
                    if "placePrediction" in s
                ][:5]
            }
        return {
            "place_id": result["id"],
            "name": result.get("displayName", {}).get("text", ""),
            "address": result.get("formattedAddress", ""),
            "latitude": result.get("location", {}).get("latitude"),
            "longitude": result.get("location", {}).get("longitude"),
            "maps_url": result.get("googleMapsUri"),
            "attributions": result.get("attributions", []),
        }
    except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
        raise AppError("provider_unavailable", "Places temporarily unavailable", 503) from exc
