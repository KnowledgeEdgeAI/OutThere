# V2 server implementation and verification

The server implements the complete named v2 event catalog, plus explicit plan-share resolution/join and personal-point hydration. Authentication advertises the supported names; `v2-contracts.json` is generated from the actual strict input models. This is a prototype server implementation, not a verified production deployment or a completed mobile integration.

## Implemented

- Device-bound phone sessions, encrypted refresh retries, profile/name/photo changes, authorized related profiles, pause/resume and account redaction.
- Circle invitations, membership removal, admin roles, ownership transfer and sleep/wake.
- Versioned private/public/link plans, direct invitations, host-approved join requests, RSVP, arrival, cancellation, circle routes and ordered stops. Provider places remain references rather than copied licensed coordinates.
- Stable materialized metadata snapshots, replay, device acknowledgements, tombstones, visibility epochs, live socket batches and stale-cursor reset after feed retention. Polling retains the pending receive task across timeouts, so arriving requests are not consumed and lost by cancellation.
- Temporary text/link/location/image/video/voice messages, reactions, transient typing, independent device acknowledgement and attachment acknowledgement. Plan location sharing uses artifacts; one-time direct location messages belong to Hello. Finished message receipts keep body-free status summaries.
- Private albums with attendance grants, expiring uploads, size/checksum/signature verification, full image decoding and pixel limits, thumbnails, promotion and revocable file links. RSVP out preserves an existing album grant; explicit removal revokes it. File links recheck current authorization on every download.
- Integer minor-unit expenses, deterministic equal splits, custom shares, corrections/voids, allocated settlements, recipient confirmation/rejection/reversal and derived balances. Removed participants retain their own obligations. Permanent operation IDs survive generic receipt cleanup.
- Notes, immutable poll options, own-vote projections, fixed closing tallies, bring claims, meeting acknowledgement/version changes, expiring personal points and derived Wrap. Artifact reference delivery is a transactional job; personal coordinates never enter metadata snapshots or change feeds.
- Frozen Ripple audiences and slots, private replies, deadline enforcement and single transactional conversion with unconfirmed plan invitations.
- Anonymous Open matching with a three-person eligible-candidate gate, symmetric block checks, current eligibility checks, deterministic ranking, mutual Hello, one extension and plan conversion. Public-plan search returns safe summaries.
- Google Autocomplete and Details with shared session tokens and explicit field masks; no stored provider response cache.
- Per-device push registration/categories, delayed jobs, acknowledgement suppression, APNs/FCM adapters and invalid-token handling. Push bodies contain a generic update notice rather than chat contents.

## Verification

Local verification passes: 43 backend tests, backend lint, migration upgrade/rollback/reapply and schema drift checks, and PostgreSQL migration SQL generation. Mobile typecheck, lint and all 14 tests also pass. PostgreSQL SQL generation does not establish runtime compatibility.

The test suite covers legacy and v2 account behavior, concurrent retries, snapshot/replay boundaries, access revocation, multi-device delivery, TTL cleanup, independent attachment downloads, money races and reversals, uploads/album revocation, polls/claims/meeting acknowledgement, Ripple conversion, matching privacy/blocking, personal-point expiry, push suppression and live socket sync/chat/typing. Migrations are tested against populated legacy accounts, planning records and devices, including rollback/reapply and schema drift. Mobile account tests, typecheck and lint are also run; the existing product screens still use preview data.

## Actual deployment limits

- Runtime verification currently uses SQLite. Docker is installed but its daemon is not running, and no PostgreSQL server is configured. PostgreSQL runtime concurrency must be checked before deployment. V2 transactions use a PostgreSQL advisory lock to serialize shared changes/snapshots in the initial small deployment; this prioritizes correctness over write throughput.
- Maps and APNs/FCM need real credentials. Provider shapes and failure handling can be mocked locally; actual delivery/billing/provider acceptance and physical iOS/Android behavior have not been verified.
- Files currently use a private local directory, suitable for one host. A shared object-bucket adapter, cloud backup/restore, operational monitoring and workload testing remain deployment work.
- Temporary tables are `deliveryevent`, `deliverytarget`, `attachmenttarget` and `personalpoint`; chat-only files must be excluded from durable backups. They currently share the database schema. Logical exclusions and physical snapshot/WAL retention must be configured and tested before claiming deletion from backup copies. Legacy `/v1` messages remain stored and are not silently deleted by this migration.
- Voice/video upload validation checks bounded size, checksum and container signatures; it does not perform full media transcoding or moderation. Images are fully decoded and checked. Reaction operations require an available temporary source; after content expiry there is no historical server chat API. Active reaction state is body-free operational data on the existing message acceptance; it does not create a historical reaction table.
- Keyset queries use UUID `after` values and snapshots use `snapshot_id`/`after`; these are the implemented wire shapes, rather than the target's opaque signed page tokens. Snapshots are bounded by TTL, not yet by an account-size quota. Large accounts and outbound frame sizing still need load validation.
- Unverified phone mode intentionally proves no ownership. OTP, payments, calling, server display preferences and cloud chat-history restoration remain outside the agreed prototype scope.

## Provider references

[Google Autocomplete](https://developers.google.com/maps/documentation/places/web-service/place-autocomplete), [Google Details](https://developers.google.com/maps/documentation/places/web-service/place-details), [FCM HTTP v1](https://firebase.google.com/docs/cloud-messaging/send/v1-api), [APNs requests](https://developer.apple.com/documentation/usernotifications/sending-notification-requests-to-apns).
