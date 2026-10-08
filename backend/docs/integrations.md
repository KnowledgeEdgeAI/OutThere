# Optional integrations

The app starts with no external services. Keep provider choices at the boundary.

## Places and maps

`PlaceSearch` is the interface; `GooglePlaces` is an optional implementation. It returns a short list of names, coordinates, provider IDs, links, and attributions. It does not render maps or cache results.

To enable it, copy `.env.example` to `.env`, set `OUTTHERE_MAPS_PROVIDER=google` and a server key in `OUTTHERE_GOOGLE_MAPS_API_KEY`. Configure Places API (New), billing, API restrictions and appropriate server restrictions first. Browser maps will need their own restricted browser key when we build the frontend.

`places.search` accepts `{"query":"badminton near Indiranagar"}`. The adapter uses an explicit field mask and an eight-second timeout. Preserve Google and third-party attributions in the UI; review storage/display terms before saving provider content to plans or another index.

References: [Text Search](https://developers.google.com/maps/documentation/places/web-service/text-search), [key restrictions](https://developers.google.com/maps/api-security-best-practices), [Places policies](https://developers.google.com/maps/documentation/places/web-service/policies).

## Meilisearch, when we own a venue catalog

Useful for **venue text search plus distance filtering**. It is an optional, rebuildable index; the relational database remains authoritative. There is no running search service or indexing worker yet.

The [settings template](../integrations/meilisearch-settings.example.json) supports documents shaped like:

```json
{"id":"venue-uuid","name":"Community court","city":"Bengaluru","tags":["badminton"],"_geo":{"lat":12.97,"lng":77.59}}
```

An example query is `{"q":"court","filter":"_geoRadius(12.97,77.59,5000)"}`. A future worker can upsert approved venue records after database commits. Keep Meilisearch credentials server-side and restrict indexed content to data we are allowed to store. Do not copy Google results into this index by default.

See [Meilisearch geo search](https://www.meilisearch.com/docs/capabilities/geo_search/getting_started).

## People matching

`discovery.py` currently checks coarse distance, mutual radius, overlapping time, common interests, and a caller-supplied block decision. It is a pure function, tested without a service or spatial extension.

Before exposing matching, add expiring availability records, server-side block lookups, anonymity thresholds, delayed/jittered delivery, and mutual consent. Never return searchable people or precise locations from the venue index. A spatial database index can narrow candidates when measured load requires it.

## Files, OTA and analytics — later

Add object storage for attachments and signed update bundles. Keep ownership, metadata, and release manifests in the relational database. OTA needs client-runtime compatibility checks, rollout controls, signature verification and rollback; there is no update endpoint yet.

Export approved analytical data asynchronously into object storage only when reporting needs it. A lakehouse can organize those exports later. It should not be the store serving live chat, sessions, or RSVPs.
