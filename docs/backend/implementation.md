# Implementation sequence and acceptance checks

This is a design deliverable. The current mobile app is an in-memory UI preview. The current backend is an earlier v1 slice with invite login and permanently stored text chat. Do not relabel it as the completed system.

[Architecture](design.md) · [Protocol](protocol.md) · [Schema](schema.md) · [Client](mobile.md)

## Build in complete vertical slices

| Order | Deliverable | Completion evidence |
| --- | --- | --- |
| 1 | v2 contracts, phone sessions, per-device identity, local SQLite, shared socket | Signup/login/reconnect/logout on two devices; lost refresh result recovers; wrong/revoked device denied |
| 2 | Consistent metadata snapshot, replay, tombstones, outbox, profile/circles/plans/stops | Offline edit survives restart; duplicate actions do not duplicate rows; concurrent snapshot/write has no lost changes; access removal purges cache |
| 3 | Temporary chat and attachment lifecycle | Text/link/location/reaction/typing reach eligible devices; offline delivery replays once locally; per-device ack does not discard another copy; TTL cleanup removes bodies |
| 4 | Upload/storage, albums, thumbnails, profile picture, scrapbook | Metadata-only bootstrap; authorized downloads; untrusted uploads rejected; promotion-vs-cleanup race safe; hidden media removed |
| 5 | Splits and settlement confirmation | Equal/custom rounding; derived positions balance; stale edits rejected; retries cannot double-settle; mixed currencies stay separate |
| 6 | Google place search/map, public plans, Opens/overlaps/Hello | Real coordinates; provider errors handled; filters and ordering deterministic; blocks/density gate; mutual hi races produce one room |
| 7 | Push, contacts, local backup, remaining Live/Board/Wrap wiring | Denied permissions work; background message alert; local alias fallback; same-account restore without tokens or old action replay |

Dependency exception: file upload/download basics belong in slice 3 before declaring voice/image/video chat complete; slice 4 finishes durable album features. Place/map basics can ship with slice 2; discovery completes in slice 6. An unfinished slice remains explicitly marked as such.

## Coordination slice (after shared sync and chat)

Ship pins, polls, one-time places and the Live projection together, before calling plan coordination complete. Add Ripple audience/reply/conversion next. These are core flows, not optional polish deferred to the last screen-wiring pass.

Acceptance: pin once from Chat and observe the same artifact on Live and a second device; edit/unpin propagates; expired chat still leaves saved decisions; new devices receive current cards. Race a vote against deadline and verify one immutable result; ties/no votes stay unresolved. Change the meeting point and require a new explicit acknowledgement. Withdraw/expire a personal point and confirm coordinates disappear from both screens and never enter backups. Test forbidden cross-plan references, duplicate promotion, permission removal, offline rejection and cancellation. Ripple tests cover duplicate recipients, multi-slot replies, deadline boundaries, private projections, conversion-vs-reply races and repeated conversion creating only one plan with unconfirmed invitations.

## Local settings and data minimization

Remove the proposed server preferences table/events from v2; no migration or API should be added for display preferences. Implement a local resolver for device defaults and explicit overrides alongside the client storage slice. Keep only minimal per-device push delivery policy on the server. Do not remove shared scheduling timezones, access controls or bounded recovery records.

Verify: a fresh install follows device language/units/time format; changing device settings updates only non-overridden choices; local overrides work offline and survive restart and server resync; resetting restores dynamic device defaults. Two devices may display the same plan differently without changing its stored time or distance. Inspect auth/profile/sync/outbox payloads for absence of display preferences, and check push opt-out/category changes still affect server delivery after acknowledgement. Archive restore preserves overrides while re-reading the new device’s defaults and permissions.

## Simplified storage acceptance

Do not create the removed room-membership, Live, Wrap, server-bookmark, duplicate-ledger, Ripple-slot, device-sync or message-status tables. Use the replacements in the schema. Keep `plan_circles` for circle reach and invitations for direct invitees, without copying either into a second audience list.

Verify parent-based room access and immediate revocation; editing the meeting point changes the plan version; Wrap reflects corrected/removed source records; local Scrapbook pins cause no server writes and cannot bypass album access. Validate bounded Ripple slot IDs, and race replies against conversion. Confirm money corrections and reversal/reallocation races preserve totals without a duplicate ledger. Confirm final message status survives payload/target cleanup in its existing acceptance receipt, then becomes unknown after receipt expiry. Sync cursor updates use the device row. Candidate changes recompute ranking/reasons and reject stale ineligible responses.

Measure the affected queries with realistic small-plan data before introducing materialized totals or caches. Fewer tables alone is not evidence of lower latency; the benefit here is fewer duplicate writes and synchronization paths.

## Existing source changes

- Retain FastAPI, Pydantic contracts, SQLModel, Alembic and current transaction/deduplication patterns. Use PostgreSQL for deployed shared state and test it, rather than assuming SQLite tests prove PostgreSQL behavior.
- Add v2 WS auth first; keep documented v1 clients working until the new client is verified. Do not silently reinterpret the existing v1 frame format.
- Migrate profile phones and device sessions; existing invite-only users require explicit account association, not invented phone numbers.
- Add plan visibility, route stops, full participant/access controls, albums/media, money and discovery tables with reversible schema migrations where feasible.
- Replace permanent message writes/history queries in v2 with expiring delivery storage. Legacy body deletion is an intentional migration after preserving any explicitly requested local export. Purge old server backups according to retention policy.
- Reuse `AppState` as the UI-facing facade while replacing fixture-backed business actions with local repository subscriptions. Do not rewrite screen layout to introduce networking.
- Keep protocol payloads independently versioned and contract-tested on both sides. Shared JSON examples/schema can avoid manually drifting Python/TypeScript definitions.

## Required meaningful verification

1. Contract tests: every catalog event validates payload, rejects unknown fields, checks access and returns matching errors. Only auth allowlist works before login.
2. Integration tests: transaction commit/rollback, concurrent duplicate actions, restart/reconnect, snapshot boundary, feed retention reset, session/device revocation.
3. Delivery tests: sender's second device, two recipient devices with one offline, reconnect duplicate, removed member, reaction-before-message, file-ack loss, expired attachment and payload deletion.
4. Money tests: smallest-unit rounding, corrections, over-allocation, concurrent confirmations and currency-separated totals.
5. Media tests: unauthorized read, MIME/size mismatch, abandoned upload, storage failure, hidden asset and album promotion racing expiry.
6. Client tests: process restart with pending actions, lower-version replay, permission denial, account isolation, staging failure, corrupt/cross-account restore and restored drafts not submitted automatically.
7. Matching tests: no profile interests required, distance/time boundaries, full/cancelled plans, blocked pairs, density gate, expired Open, canonical overlap and concurrent mutual hi.
8. Device checks: real iOS and Android development builds for Google map provider, foreground/background notification behavior, voice/media capture and backup file access.

Run backend tests/lint/migration checks and mobile lint/typecheck for relevant implementation slices. In this design-only change, check documents and links; runtime behavior has not changed.

## Choices kept visible

The architecture covers the agreed features, but these defaults remain configurable: delivery TTL, active-device window, notification grace period, media limits, backup inclusion and local history retention. Public-plan publishing/join approval is newly specified as host-approved by default. The proposed room deadlines in the architecture resolve older guest/archive inconsistencies and must be enforced by shared server policy constants. Real payment/refund processing, OTP, cloud backup, device-to-device chat transfer and ML matching are outside this build.

## Small first deployment

One app instance and one worker, managed PostgreSQL, private object bucket, APNs/FCM credentials and restricted Google keys. TLS proxy and health/readiness checks, migrations as a release step, schema-compatible rolling releases. Alerts for queue age, cleanup failure, invalid push credentials and provider error spikes. Verify backup/restore excludes temporary chat schema and chat-only object prefixes. Add Redis/pub-sub or extra workers only after measuring latency/load.

## Implementation progress — 7 October 2026

Implemented: strict v2 account contracts, canonical phone sign-in behind an explicit prototype setting, device-bound sessions, encrypted idempotent refresh, profile read/update with versions, device list/revocation, bounded retries with server-enforced intent age, local account storage, persistent profile outbox, foreground reconnect and an isolated connected Account screen. Native tokens use SecureStore; browser simulation keeps tokens in memory and account data in IndexedDB. Native SQLite holds account data separately from credentials.

Not yet implemented: full metadata snapshots/cursors, circles/plans/stops in v2, temporary chat, media/albums, money, discovery, pins/polls/bring claims/Ripple, contacts/push and archive export/import. Existing plan screens retain explicit preview state. Slice 1 is underway, with the account/profile path verified; the full feature set is not complete.


## Server core implementation — 7 October 2026

The v2 server now implements the named event catalog across accounts, circles/plans/stops, metadata sync, temporary delivery/attachments, albums/media, expenses/settlements, coordination, Ripple, discovery/Hello, safety, sharing, places and push adapters. [Runtime status and concrete limits](../../backend/docs/v2-status.md) distinguish tested code from deployment work. The mobile account integration remains implemented; product screens are still previews and do not yet consume the new product sync/delivery APIs. This does not mark the complete application or production deployment finished.
