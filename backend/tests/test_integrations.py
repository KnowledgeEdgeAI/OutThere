from dataclasses import replace

import httpx
import pytest

from outthere.discovery import Availability, compatible, distance_m
from outthere.errors import AppError
from outthere.integrations.places import GooglePlaces


def test_geo_matching_is_symmetric_and_crosses_dateline():
    a = Availability("a", 0, 179.999, 500, 100, 200, frozenset({"chai"}))
    b = Availability("b", 0, -179.999, 500, 150, 300, frozenset({"chai"}))
    assert 220 < distance_m(a, b) < 225
    assert compatible(a, b) == compatible(b, a) is True
    assert not compatible(a, replace(b, radius_m=100))
    assert not compatible(a, replace(b, starts_at=200))
    assert not compatible(a, replace(b, vibes=frozenset({"run"})))
    assert not compatible(a, b, blocked=True)
    assert not compatible(a, replace(b, user_id="a"))
    with pytest.raises(ValueError):
        replace(a, latitude=float("nan"))


def test_google_places_preserves_attribution_and_hides_provider_errors():
    def provider(request):
        assert request.headers["x-goog-api-key"] == "test-key"
        assert "places.attributions" in request.headers["x-goog-fieldmask"]
        return httpx.Response(
            200,
            json={
                "places": [
                    {
                        "id": "place-id",
                        "displayName": {"text": "Court"},
                        "location": {"latitude": 12.9, "longitude": 77.6},
                        "attributions": [{"provider": "Example"}],
                    }
                ]
            },
        )

    places = GooglePlaces("test-key", httpx.MockTransport(provider)).search("court")
    assert places[0]["name"] == "Court"
    assert places[0]["attributions"] == [{"provider": "Example"}]
    with pytest.raises(AppError, match="temporarily unavailable"):
        GooglePlaces("secret", httpx.MockTransport(lambda _: httpx.Response(403))).search("court")
