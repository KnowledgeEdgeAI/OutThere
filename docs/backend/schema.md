# Relational schema — target v2

Logical schema, not an applied migration. [Architecture](design.md) · [Protocol](protocol.md)

UUID primary keys unless a composite key is listed. Mutable shared rows have `version`, `created_at`, `updated_at`; UTC instants plus IANA venue timezone for plan scheduling. Phone is unique and canonical. FKs, check constraints and uniqueness enforce product invariants; JSON is for small typed bounded payloads, including Ripple’s two suggested slots; membership, votes and money remain relational.

## Store only what the server must know

Keep shared product facts, access rules, delivery state and recovery records on the server. Presentation choices and device conveniences belong on the device. There is no server `preferences` table and no preference sync feed.

| Data | Owner / rule |
| --- | --- |
| Language, distance units, temperature units, 12/24-hour format | Device-local overrides; default to device settings or locale conventions; never uploaded |
| Theme, screen filters/sort, dismissed tips, drafts, download/cache choices | Device-local; no server rows or sync events |
| Device timezone for display | Read locally; do not store on the user profile |
| Plan venue timezone and Ripple slot timezone | Shared scheduling data; retain with the event so all participants agree on the instant |
| Contacts and OS permission state | Device-local; server receives neither the address book nor a permission-history record |
| Push token and enabled push categories | Minimal per-device delivery policy, needed to suppress unwanted background pushes; no language/units/display preferences |
| Blocks, membership, RSVP, approvals, money, shared decisions | Server-owned; these affect other people or enforce access |
| Receipts, sync cursors and jobs | Bounded operational state for reliable retries and delivery; not user preferences |

Distances/radii use metres, timestamps use UTC instants with event timezones, and money uses integer minor units plus currency. If temperature data is added, exchange a documented canonical unit and convert on the client. Never persist a second formatted value for each locale or unit system.

## Simplifications for the first build

| Remove / combine | Keep instead |
| --- | --- |
| `room_members` | Derive access from current plan participants or the mutual Hello pair; one authorization function used on every read/write/delivery |
| `plan_live` | `plans.meeting_artifact_id`; Live is a projection of the plan, artifacts and responses |
| `wraps` | Build a read-only summary from authorized plan/arrival/decision/album records on demand; no persisted summary or generation job |
| `scrapbook_entries` | Personal bookmarks on each device; albums/media stay on the server; no bookmark sync |
| `ledger_entries` | Derive balances from expenses, shares and confirmed settlement allocations; retain immutable correction/reversal facts and permanent operation IDs |
| `ripple_slots`, `ripple_response_slots` | At most two typed slots on the Ripple and at most two selected IDs on each response; validate under the Ripple lock |
| `device_sync` | Cursor and sync epoch on the existing device row |
| `message_status` | While pending, aggregate delivery targets; when deleting them, save one body-free final summary on the existing acceptance receipt |
| Direct-user `plan_audiences` rows | Direct invitations already identify invitees; keep only `plan_circles` for circle join routes |
| Stored overlap duration, distance band and reason tags | Compute from the current Opens when returning candidates; persist only the pair and decisions needed for mutual hi |
| Stored counts, labels and relative times | Compute RSVP/arrival totals, open poll tallies, balances, “ends in…” and formatted labels from source records |

Closed poll tallies remain saved decision facts, not a live counter cache. Albums and their independent grants remain shared; expiry of a chat must not accidentally revoke album access. Keep consistent sync snapshots and bounded delivery/retry records: they protect against lost changes and duplicate actions, rather than duplicate product facts. Do not add derived-value caches until measurement shows a slow query.

## Persistent product schema (included in server backups)

| Table | Essential fields / constraints |
| --- | --- |
| users | id, phone unique, registered_name, dp_media_id, phone_verified_at nullable, paused_at, deleted_at |
| devices | id, user_id, installation_id, platform, provider, push_token, push_categories (delivery policy only), last_seen_at, revoked_at, acknowledged_cursor, sync_epoch; unique user/installation |
| sessions | id, user_id, device_id, access_hash, refresh_hash, access_expires_at, expires_at, revoked_at |
| auth_operations | renewal_id, session_id, request_hash, encrypted_retry_result, expires_at; short-lived |
| circles | id, owner_id, name, icon, kind, sleeping_at |
| circle_members | circle_id + user_id PK, role, joined_at |
| invitations | id, circle_id OR plan_id, inviter_id, invitee_id optional, token_hash optional, expires_at, status; exactly one parent |
| plans | id, host_id, visibility, status, title, starts_at, ends_at, venue_timezone, currency, capacity, tags, meeting_artifact_id optional, version; meeting artifact must belong to this plan |
| plan_stops | id, plan_id, position, place_id optional, custom_label, custom_latitude/longitude, arrival_at; unique plan/position |
| place_cache | provider, place_id, allowed_fields, fetched_at, expires_at; ephemeral provider cache, not indefinite licensed content |
| plan_circles | plan_id + circle_id PK; circle discovery/join routes only; direct people use invitations |
| plan_participants | plan_id + user_id PK, source, approval_state, rsvp, role, arrival_state, access_until, version |
| rooms | id, plan_id OR overlap_id, kind, next_seq, expires_at, read_only_at, archived_at; unique parent |
| artifacts | id, plan_id FK, creator_id, kind (note/poll/location/bring), typed_data, source_message_id optional (no FK to temporary delivery), pinned_at, closes_at, state, version; room derived from plan |
| artifact_responses | artifact_id + user_id PK, typed_value (option_id / acknowledged_artifact_version), version; poll options have stable IDs; lock parent on vote/close |
| bring_claims | artifact_id + item_id PK, user_id FK, version; one owner per item, one person may claim multiple items; lock the parent artifact for claim/release |
| ripples | id, sender_id, idea (240 chars), place_hint optional, slots (typed JSON array, 0–2 stable IDs/start/end/timezone/note), closes_at, state, converted_plan_id unique nullable, version |
| ripple_recipients | ripple_id + user_id PK, response nullable (up_for_it/another_time/cannot), selected_slot_ids (0–2 unique IDs), note (140 chars), version; frozen deduplicated audience |
| opens | id, user_id, coarse_area, private_search_point, radius_m, starts_at, ends_at, tags, expires_at, state |
| overlaps | id, open_a_id, open_b_id, decisions, deliver_after, state; canonical pair unique |
| albums | id, plan_id, creator_id, title, state |
| album_grants | album_id + user_id PK, role; explicit persistent permission |
| media | id, uploader_id, purpose, object_key unique, mime, byte_size, checksum, variants, state, expires_at nullable |
| album_media | album_id + media_id PK, added_by, position, hidden_at |
| share_links | id, owner_id, resource_type/id, token_hash, allowed_scope, expires_at, revoked_at |
| expenses | id, plan_id, payer_id, amount_minor, currency, description, operation_id unique, state, replaces_id |
| expense_shares | expense_id + user_id PK, amount_minor nonnegative |
| settlements | id, from_user_id, to_user_id, currency, amount_minor, state, confirmed_by, operation_id unique, reversal_of |
| settlement_allocations | settlement_id + expense_share reference, amount_minor; prevent over-allocation |
| blocks | blocker_id + blocked_id PK, created_at; forbid self-block |
| reports | id, reporter_id, resource_type/id, reason, status; no automatic chat-body copy |
| feed_heads | user_id PK, committed_seq, visibility_epoch, low_water_seq |
| user_changes | user_id + seq PK, entity_type/id, operation, version, created_at; no chat payload |
| sync_snapshots | id, user_id, device_id, cursor, epoch, expires_at; bounded staging data |
| snapshot_items | snapshot_id + ordinal PK, entity_type/id, authorized_projection |
| action_receipts | user_id + action_id PK, name, request_hash, minimal_result, expires_at; no chat content |
| jobs | id, kind, resource_id, safe_payload, run_at, attempts, lease_token/until, state, unique_key |

Album grants begin when a plan participant accepts attendance (RSVP in); create grants for current albums, and grant future albums to current RSVP-in participants. Host/co-host may explicitly add or remove a grant. Declining an invitation creates no grant. RSVP out alone preserves previously granted memories; explicit leave, removal or blocking revokes the affected grants. Cancellation and room archive preserve existing grants. Member removal revokes applicable grants explicitly; plan room archive alone does not. Media access is the union of current profile/album grants or a valid temporary attachment grant. No indefinite retention of Google-derived coordinates/details without policy permission: stops resolve provider references through the expiring cache; independently entered coordinates can persist.

## Derived views and compact records

Room queries derive plan participants and their current access deadlines, or the mutually accepted Hello pair. Revocation still increments the visibility epoch, purges client access and cancels delivery targets. Do not maintain a parallel membership list. Room archive is independent of plan participation and album grants.

Direct invitees come from plan invitations; circle reach comes from `plan_circles`; accepted attendance comes from participants. Public/link routes are checked separately. Queries combine these sources without copying users into an audience table. Removing an invitation or circle route does not implicitly delete accepted membership.

Ripple slots are immutable after sending. Each slot has a stable ID, start/end, timezone and an optional 80-character note. Validate unique IDs, chronological intervals, at most two entries and that every response selection belongs to the parent Ripple. A non-interested reply clears selected IDs. The chosen reply-window duration is creation input only; retain the resulting `closes_at` deadline, not two sources of expiry truth.

Balances are read-time aggregates over posted expense shares and confirmed settlement allocations. Corrections/reversals remain explicit records; exclude superseded/voided/reversed effects exactly once. Lock the relevant obligations when confirming, reversing or correcting, and reject a correction that would leave allocations above the revised obligation until dependent settlements are reversed. All projections use the same calculation, per plan and currency; clients may cache the result, never treat it as another authority.

An acceptance receipt outlives delivery content (30-day body-free retention by default). Once all targets complete or expire, cleanup records aggregate delivered/expired/cancelled counts and final time before pruning target rows. `delivery.status` reads targets or that terminal summary; after receipt expiry return `unknown`, never fabricate delivery success. No new message-status table is needed.

## Coordination integrity

Artifact data uses a validated shape per kind. Poll data contains question, stable option IDs, deadline mode, closed tally and result state; no duplicated votes in JSON. Note data contains only explicitly saved content. Location data stores a meeting place or a reference to an expiring personal point. Unique source-message pin per plan prevents duplicate promotion; pin-again reuses it. A poll is its own pinned result, with one close transition. Bring-item ownership uses a dedicated `bring_claims` row per artifact/item. A user may claim several distinct items. Claiming an occupied item returns `version_conflict`; releasing requires the current owner or host/co-host and the claim version. Removed participants lose their claims. No bring claims are stored in `artifact_responses`. Acknowledgements include the acknowledged artifact version.

Pin promotion locks and validates a still-available message in the same database transaction as artifact creation; expiry cannot race the copy. No FK requires temporary messages to survive. Durable sync/job records contain artifact IDs, not source chat bodies or personal coordinates. Personal-location reads enforce expiry even before worker cleanup. Ripple conversion locks its row and commits the plan, invitations and converted link together; a retry returns the existing plan before checking closed state.

## Temporary delivery schema (excluded from routine server backups)

Same PostgreSQL cluster, separate schema and retention policy. Schema exclusion applies to logical backups; physical snapshots and WAL recovery may still contain temporary bytes. Deployment must document their retention and verify it before promising deletion from all backup copies. Chat acceptance is one transaction here after current authorization is checked; delivery rechecks it. Use consistent parent/authorization locks where removal races acceptance.

| Table | Essential fields / constraints |
| --- | --- |
| personal_location_points | artifact_id PK, latitude/longitude, captured_at, expires_at; excluded from durable backup, no coordinates in persistent artifact data |
| delivery_events | id, room_id, room_seq, message_id, sender_id, kind, payload, created_at, expires_at; unique room/sequence |
| delivery_targets | event_id + device_id PK, delivered_at, acknowledged_at, cancelled_at |
| attachment_targets | event_id + media_id + device_id PK, downloaded_at, expires_at |
| message_acceptances | user_id + action_id PK, message_id unique, request_hash, minimal_result, final_delivery_summary nullable, expires_at; no body |

No permanent `messages` or `reactions` table. Reaction changes are temporary delivery events and local history. Typing has no database table. Media metadata may persist until cleanup, but chat-only objects are lifecycle-expiring and excluded from durable-object backup.

## Integrity, indexes and cleanup

- Unique canonical phone; membership/participant composite keys; one room per parent; one overlap per canonical pair; unique durable operation IDs. Derived financial positions balance to zero per operation/currency; there is no second ledger to reconcile.
- Check end > start, radius/capacity > 0, coordinate ranges, nonnegative file sizes and positive money amounts. Validate share totals and settlement allocations in locked transactions.
- Serialize feed sequence allocation in commit order; acquire affected user/parent locks in a consistent order. Room sequence allocation is transactional. Generated IDs alone are not committed cursors.
- Index memberships/participants by user; plans by visibility/status/start; Opens by coarse area/time; target deliveries by device/ack/expiry; changes by user/seq; jobs by state/run_at; media by state/expiry; obligations by user/currency.
- Separate retention: expire snapshots, generic receipts, references and delivery content; keep permanent money operation IDs. Prune feed only behind the low-water mark and force stale devices to snapshot.
- Media cleanup leases candidates and locks/rechecks durable references and pending attachment grants before marking deleting. Idempotent object deletion retries safely; promotion rejects deleting objects or copies them into durable storage before committing a reference.
- Account deletion revokes sessions/devices and visibility, purges deliveries and personal media references, and redacts profile fields. Shared financial rows retain only the minimum pseudonymous references needed for other participants' balances; final legal retention policy is a rollout decision.

Migration warning: existing runtime tables store permanent message bodies. New migrations must disable that write path, migrate shared entities, assign legacy room IDs, and remove old bodies/backup copies deliberately. Do not describe v2 retention as active until cleanup and backup configuration are verified.
