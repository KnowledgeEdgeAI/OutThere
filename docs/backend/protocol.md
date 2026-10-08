# WebSocket event protocol — target v2

**Design contract; not yet supported by the running v1 server.** One WSS connection per active device at `/v2/ws`. All application control travels here; signed HTTPS transfers carry files. [Architecture](design.md) · [Client](mobile.md)

## Frames

Reuse the existing command/query terminology; event-based does not require a historical event-sourcing database.

```json
{"v":2,"id":"request-uuid","type":"command","name":"plan.create","action_id":"stable-action-uuid","payload":{"plan_id":"client-generated-uuid","title":"Badminton","starts_at":"2026-10-10T12:00:00Z","ends_at":"2026-10-10T14:00:00Z","venue_timezone":"Asia/Kolkata","visibility":"public","currency":"INR","tags":["badminton"]}}
```

`id` correlates one attempt; `action_id` identifies one durable intent and remains unchanged on retry. Queries omit `action_id`. Durable mutations include `issued_at`, an immutable offset-aware creation time, and expected versions where appropriate. `issued_at` participates in the canonical request hash. Reject intents older than seven days or more than 60 seconds in the future, even after receipt cleanup. Expired intents require refreshing shared state and explicit review before generating a new action ID and timestamp; never silently renew a queued intent. Client-generated entity IDs allow offline dependencies. Server IDs are still validated for uniqueness and access; knowing an ID grants no rights.

```json
{"v":2,"type":"result","id":"request-uuid","data":{"plan_id":"client-generated-uuid","version":1}}
```

```json
{"v":2,"type":"error","id":"request-uuid","error":{"code":"version_conflict","message":"This plan changed","retryable":false,"details":{"current_version":4}}}
```

Results and events interleave. Error codes: `invalid_input`, `unauthenticated`, `forbidden`, `not_found`, `version_conflict`, `action_conflict`, `capacity_reached`, `expired`, `cursor_reset_required`, `rate_limited`, `provider_unavailable`, `unsupported_version`. Avoid existence leaks: inaccessible resources can return `not_found`. Rate limits include `retry_after_ms`. Transient errors retry with the same action ID; validation/conflicts require user review and a new intent.

Durable receipts bind authenticated user + action ID + canonical payload hash. Reuse with changed content fails. A duplicate committed action returns its original minimal result without executing twice. Unknown outcome/timeouts remain pending, never treated as failure. Queue dependencies wait for server acceptance; do not send an expense referencing a rejected plan.

## Authentication on the same socket

The first frame is a query/command from the auth allowlist within 10 seconds; no app subscriptions before authentication.

- `auth.login`: phone with country code, installation ID, platform, optional name for signup. Returns user, device, access/refresh tokens and expiries; authenticates this connection. Unverified mode performs no OTP challenge.
- `auth.resume`: access token + device ID; authenticates a reconnect, returns readiness and supported protocol capabilities.
- `auth.refresh`: refresh token + device ID + renewal operation ID; allowed on a connected or newly opened socket. Rotate tokens with a bounded idempotent retry record so a lost response does not strand the session.
- `auth.logout`: revoke current device session and close socket.
- `device.list`, `device.revoke`: manage own installations; revocation immediately prevents replay/delivery.
- Future `auth.otp.request` / `auth.otp.verify`: reserved contracts behind the auth provider; not implemented now.

Initial access/session defaults can reuse 15 minutes/30 days. Login and refresh enforce per-IP/account limits. Refresh tokens are hashed at rest; any short-lived replayable renewal result is encrypted. Do not place tokens in URLs or logs. Device IDs are assigned/bound by the server; an installation identifier alone is not authorization. A reinstalled/restored app gets a new device session.

## Event catalog

All entries below are WS names. `get/list/search` are paged queries; other names are commands unless described as transient.

| Feature | Names and essential inputs |
| --- | --- |
| Profile | `profile.get`, `profile.update` (name, dp_media_id, version), `account.delete` |
| Devices | `device.list/revoke`, `device.push.register/unregister` (token, provider, platform, enabled_categories) |
| Circles | `circle.list/get/create/update`, `circle.invite`, `circle.invitation.accept/decline`, `circle.leave`, `circle.member.remove/role`, `circle.owner.transfer`, `circle.sleep/wake` |
| Plans | `plan.list/get/create/update/cancel`, `plan.invite`, `plan.join.request/approve/decline`, `plan.leave`, `plan.member.remove`, `plan.rsvp`, `plan.arrival.update`, `plan.share.create/revoke` |
| Routes | Ordered `stops` on plan create/update: stop_id, order, place_id or custom label, coordinates, arrival_at; immutable plan currency once expenses exist |
| Places | `places.search` (query, session_token, optional area), `places.details` (place_id, session_token); debounced queries, bounded results |
| Room | `room.get` (policy/members derived from parent; no historical chats), `message.send`, `message.reaction.add/remove`, `typing.update` (transient, room_id, active) |
| Delivery | `delivery.pull` (opaque page token), `delivery.ack` (event IDs), `delivery.media.ack` (event_id, media_id), `delivery.status` (own message IDs) |
| Albums | `album.list/get/create/update/delete`, `album.media.add/remove/hide`, `media.share.create/revoke` |
| Media | `media.prepare` (id, purpose, parent, mime, size, checksum), `media.complete` (id), `media.abort`, `media.read` (id, variant), `media.promote` (id, album_id) |
| Money | `expense.list/create/correct/void`, `balance.list`, `settlement.propose/confirm/reject/reverse`, `split.remind`; amount_minor, currency, shares/allocations and expected versions |
| Discovery | `open.list/create/update/close`, `discovery.plans` (tags, interval, area, radius), `overlap.list/respond` (hi/pass, version), `hello.extend`, `hello.plan.create` |
| Live and Board | `artifact.list/create/update/delete`, `artifact.respond` (poll vote/bring claim/pin acknowledgement), `artifact.pin/unpin`, `poll.close`, `plan.meeting.set`, `ripple.list/create/respond/convert/close`, `wrap.get` (read-only derived summary) |
| Safety | `block.create/delete/list`, `report.create`, `profile.pause/resume` |
| Sync | `sync.start`, `sync.page`, `sync.resume`, `sync.ack` |
| Transport | `ping`/`pong`; no business persistence |

Each event contract must define exact field types, limits and permissions in `contracts.py` before implementation. Common mutation inputs: entity ID, expected version, action ID; queries use opaque keyset page tokens and limit 1–100. Dates have offsets; server stores UTC plus IANA venue timezone. Public cards return safe summaries, not participant phones, chat, albums or money. Display settings, local contact permission and backup export are device actions, not server events. There are no `preferences.get/update` events. Do not include language, distance units, temperature units, time format, theme or device display timezone in auth, profile, push or sync payloads. Push registration sends only the token/provider/platform and enabled categories; unregister when push is disabled. Wire distances use metres; clients convert selected search radii to metres before submitting.

Message content is a discriminated payload: `text` (includes emoji), `link` (URL + optional text), `location` (lat/lng/label, one-time Hello share only); plan locations use the shared artifact contract below, `voice` (media_id + duration), `image/video` (media_ids + optional caption/album_id). Sender identity is server-derived. Reactions include target message ID and validated emoji. At most one occurrence of the same emoji per sender/message; removal is idempotent. File constraints are purpose-specific configured limits, enforced during prepare and verified after upload.

## Read projections instead of duplicate state

`plan.get` combines plan fields (including the current meeting artifact), current participants and authorized coordination cards; it does not read a separate Live table. `room.get` derives members from that room’s parent. `balance.list` aggregates authoritative expense/share/settlement records; there is no writable balance or second ledger. `wrap.get` computes a bounded summary from the current authorized sources, with paged album references; it does not create a Wrap record or trigger a background generation job.

There are no server Scrapbook bookmark commands. The client filters authorized album metadata using local favourites; a bookmark never grants access. Open-match time/distance/reasons are computed at read time, not copied into the overlap row. Recheck eligibility when responding, so an outdated card cannot create a Hello after an Open expired or access changed.

Ripple creation stores at most two typed slots in its record and the calculated deadline. Reply commands contain at most two unique selected slot IDs validated against that parent. Slots cannot change after send; start a new Ripple for a changed proposal.

## Shared Chat and Live contracts

All coordination commands require current plan participation and `plan_id`. Durable commands use `action_id`; updates use `expected_version`. Server roles enforce the creator/host rules in the overview.

| Command | Essential payload and result |
| --- | --- |
| `artifact.create` | `artifact_id`, `plan_id`, `kind`, typed data. Poll: question, 2–6 stable options, default-start or explicit deadline. Location: place reference/custom point or personal point with capture time. Returns canonical artifact/version; creates a chat reference through a transactional job. |
| `artifact.pin` | `plan_id`, existing `artifact_id` OR `source_message_id` plus new artifact ID; exactly one source. Message promotion validates unexpired text/link and saves reviewed content. Expired source returns `expired`; client offers a standalone note. |
| `artifact.unpin/update/delete` | Artifact ID/version; unpin changes visibility, delete removes saved content with a tombstone. Updates preserve kind and parent. |
| `artifact.respond` | Artifact ID; discriminated vote (`option_id`), bring claim (`item_id`) or acknowledgement (`artifact_version`). Poll votes and meeting acknowledgements have one response per user; own response version prevents stale multi-device overwrites. Bring claims use distinct artifact/item rows, allowing several items per person; release requires owner or host/co-host and expected claim version. Poll votes lock parent/check deadline but do not require a global tally version. |
| `poll.close` | Artifact ID/version. Creator/host only; worker uses same state transition. Returns saved counts and winner/tied/no_votes/cancelled state; pins the result once. |
| `plan.meeting.set` | Plan version, location artifact ID/version. Host/co-host only; must be a nonexpired same-plan place. Personal points require explicit host confirmation to save as a shared meeting place. Returns updated Live state. |
| `artifact.list` / `plan.get` | Current authorized cards / Live state, including meeting reference; hydrate unexpired personal points separately, without recording coordinates in snapshots or sync payloads. |
| `ripple.create` | Ripple ID, idea, audience circle/user IDs, optional place hint, up to two timezone-aware slots, reply window. Returns resolved recipient count and server deadline. |
| `ripple.respond` | Ripple ID, own response version, choice, selected slot IDs and optional note; validates recipient and deadline. |
| `ripple.convert` | Ripple ID/version and reviewed plan fields/invitees; sender only. Returns the unique converted plan ID. Invitations never become attendance automatically. |

`artifact.changed` is a temporary chat reference (`plan_id`, `artifact_id`, `version`, change kind), never a second saved copy. Persistent sync is authoritative for the artifact and its permitted response projections. Poll projections contain aggregate counts and the viewer’s own vote only; never synchronize other users’ ballot rows. Bring claims and explicit meeting acknowledgements retain the participant visibility described in the overview. Deduplicate reference cards by artifact ID; hydrate missing or newer versions before showing actions. `ripple.list` returns full replies only to the sender; recipients get aggregate counts and their own response. Ripple rows and responses also participate in metadata sync with those projections.

## Persistent metadata sync

1. `sync.start` registers a consistent snapshot at feed cursor C and visibility epoch E. Create a bounded materialized projection under a repeatable-read transaction, then release the transaction; do not hold it across mobile requests.
2. Return `snapshot_id`, C, E and pages. `sync.page` continues using a stable page token. Pages include authorized profiles, circles, plans/stops/participants, artifacts, opens/overlaps, expenses/settlements, albums/media references. Public discovery results are a separate short-lived query cache.
3. Client stages snapshot pages and atomically replaces its server-data projection after the final page, saving C/E. Preserve local chat and unsent intent separately.
4. `sync.resume` starts replay after C. Changes committed during snapshot creation/loading are replayed. If snapshot expired or visibility changed, restart instead of publishing partial/stale state.
5. Steady-state changes hydrate current authorized entities, not historical snapshots. Apply upserts/removals and advance cursor in one local transaction. Ignore lower entity versions. `sync.ack` communicates only after persistence; update cursor/epoch on the device row.

```json
{"v":2,"type":"event","name":"sync.batch","payload":{"epoch":3,"from_cursor":120,"cursor":125,"changes":[{"seq":125,"entity":"plan","entity_id":"uuid","operation":"upsert","version":4,"data":{}}],"has_more":false}}
```

User sequence allocation is serialized in commit order, not merely generated IDs. `from_cursor` identifies the expected predecessor; numbers can skip access-filtered entries. A gap/reset restarts sync. Feed retention has a low-water mark; old cursors return `cursor_reset_required`. Device cursors are independent.

Removals use tombstones. Authorization changes bump visibility epoch and send `sync.access_revoked`; the client immediately purges affected entities, signed URLs, cached files and pending forbidden actions, then reboots the projection. Recheck access during page/delivery reads. Disconnected local copies cannot be instantly remotely erased; revalidation happens at reconnect.

## Temporary delivery

Separate delivery IDs and per-room sequence from persistent sync cursors:

```json
{"v":2,"type":"event","name":"delivery.batch","payload":{"items":[{"event_id":"uuid","room_id":"uuid","room_seq":18,"kind":"message.created","message_id":"uuid","sender_id":"uuid","created_at":"2026-10-06T12:00:00Z","expires_at":"2026-10-13T12:00:00Z","content":{"kind":"text","text":"See you there"}}],"next_page":null}}
```

`delivery.pull` returns unacknowledged events for this device; live delivery uses the same representation. `delivery.ack` follows the local transaction. Missing sequence numbers may mean expiry, so sequence is ordering, not proof of complete historic chat. Replies contain only IDs/state, never retained bodies. Device acknowledgement removes its pending target, not other devices' targets. Delete payload after all targets acknowledge or TTL. Keep the body-free terminal summary on the existing message acceptance receipt for 30 days; cleanup records it before pruning targets. `delivery.status` aggregates live target rows or returns this summary; after receipt retention return `unknown`.

Attachment acknowledgement is separate from message metadata. Chat-only object retention ends after all intended attachment targets confirm download or TTL; album references override expiry. An acknowledged text message may still have attachment bytes pending. Block/revocation cancels forbidden targets immediately. Typing events carry room, sender and expiry only, without replay.

## Connection lifecycle

Client owns one socket manager shared by screens. On foreground/network recovery: connect → authenticate → sync → pull pending deliveries → drain outbox. No need to block message receipt until every metadata page loads: store events awaiting room hydration. Ping at a configurable 25-second interval, timeout after two missed responses, exponential retry 1–30 seconds with jitter. Stop retry loops while offline/background; reconnect when active. Do not promise background WS availability.

Recommended starting bounds: 64 KiB frames, 100-row pages, 20 inflight requests/device, 4 connections/account, and capped send buffers. Tune per-account/IP request and upload quotas separately. Sessions are checked on events and heartbeats. Protocol version/capabilities prevent older clients sending unsupported commands. Log IDs and error codes, never private payloads.

## Implemented account slice — 7 October 2026

The running `/v2/ws` endpoint currently implements only `auth.login/resume/refresh/logout`, `profile.get/update`, `device.list/revoke` and `ping`. Authentication responses advertise those exact capabilities. Other catalog events remain target contracts and return `unsupported_version`. The v1 endpoint remains unchanged for v1 sessions; v2 device tokens cannot use it.

Exact input JSON Schemas come from `outthere.v2.contract_schemas()` and are checked into `backend/docs/v2-contracts.json`. Auth frames have strict payloads but do not use the generic action receipt. Profile updates and device revocations require `action_id` and `issued_at`; profile updates require `expected_version`. Responses use the v2 result/error envelope. Login returns a token pair, account/device IDs, own profile and capabilities. Resume returns IDs, own profile and capabilities. Refresh returns a token pair, IDs and capabilities. Profile reads/updates return `{id, name, phone, version, phone_verified_at:null}`. Device list returns `{items:[{id, platform, last_seen_at, revoked_at, current}]}`. Revoke returns `{device_id, revoked:true}`; logout returns `{signed_out:true}`. Ping returns integer Unix `server_time`. `profile.changed` events carry the current own profile; full product snapshot/cursor sync is not implemented by this slice.

The server requires explicit `OUTTHERE_AUTH_MODE=unverified_phone` and a configured Fernet `OUTTHERE_AUTH_RETRY_KEY`. Refresh retry ciphertext is bounded to five minutes by default and bound to the session, device and previous token hash. A revoked or superseded session cannot replay its renewal result. Phone sign-in canonicalizes possible E.164 numbers but proves no ownership.
