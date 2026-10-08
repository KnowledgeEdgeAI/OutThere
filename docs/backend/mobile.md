# Mobile data layer — target design

Expo SDK 57 / React Native, with screens kept separate from storage and networking. [Architecture](design.md) · [Protocol](protocol.md)

## Source layout

```text
mobile/src/
  app/                  existing Expo Router screens
  domain/               product types and pure rules; no network/UI imports
  backend/
    contracts.ts        typed v2 frames and feature inputs/results
    client.ts           one WS connection, correlation, timeouts, heartbeat
    session.ts          login, renewal, logout, device identity
    sync.ts             snapshot staging, replay, purge, cursor transactions
    outbox.ts           durable intent queue, retry and dependencies
    delivery.ts         local chat, reactions, device/file acknowledgements
    repositories/       people, circles, plans, money, albums, discovery
    storage/            SQLite migrations, transactions, queries
    device/             contacts, push, local backup, media cache adapters
  state/                view subscriptions and UI-only state
  data/fixtures.ts      explicit demo mode only
```

This is the planned source layout; do not create empty abstraction folders or wrap every SQL call in another class. One local database, one connection manager and feature repositories are enough. Repositories expose local queries/subscriptions and user intents. Screens never open sockets or perform direct server writes.

## Local storage

| Local data | Purpose |
| --- | --- |
| Authorized entity tables | Profiles, circles, members, plans/stops/participants, artifacts, expenses/shares/settlements, albums/media references, Opens/overlaps |
| `messages`, `reactions` | Device chat history with message ID, room sequence, content, timestamps and delivery status |
| `delivery_inbox` | Received event IDs and pending reactions/hydration; deduplication across reconnects |
| `outbox` | Stable action ID, typed payload, hash, expected version, dependencies, attempt state, retry expiry |
| `sync_state`, snapshot staging | Per-account/device cursor, visibility epoch, schema version and atomically staged metadata |
| `local_favourites` | Account-local album-media bookmarks for Scrapbook; never uploaded; current album access still required |
| `local_settings` | Per-account, per-installation overrides for language, distance units, temperature units, time format and other UI choices; absent/`system` means follow device; never sent through outbox or sync |
| `contact_aliases` | Local normalized phone → contact label; never uploaded |
| `media_cache` | File paths, checksum, purpose, size and cache/download status |
| `backup_manifest` | Archive schema, account identity and included files |

Use Expo SQLite for transactional persisted records; secure platform storage for session secrets. Separate DB/file namespaces by account. Display optimistic intent as an overlay, not a mutation of acknowledged server records. Server entity versions and pending local state remain distinguishable.

Chat-only attachment downloads live in durable app-owned history storage; album thumbnails/originals are evictable cache unless explicitly kept offline. Do not acknowledge a file saved only to an evictable cache. Disk-full/download failures retain pending status and explain retry. Location/voice/image capture permissions are requested only when that feature is used.

## Device defaults and local overrides

Resolve each display choice as **explicit local override → current device preference → locale convention → documented app fallback**. Start with “Use device default” for language, distance units, temperature units and 12/24-hour time. Use the device language list to select a supported translation; fall back to English if none is supported. If a platform does not expose a unit/format preference, infer it from the current device locale; final app fallbacks are metric distance, Celsius and 24-hour time.

Do not save a resolved default as an override. Re-resolve defaults on foreground/device-settings changes; preserve explicit overrides. Setting changes work offline and update visible formatting immediately, without socket traffic. Resetting one choice removes only that override. Account-local settings are isolated between accounts, stay outside server snapshot replacement and do not automatically follow the user to another device.

Convert canonical metres and any future canonical temperature values for display; convert user-entered search radii back to metres for requests. Time format changes labels only, never schedule instants. Render times using the relevant event timezone or clearly labelled local time; device timezone changes cannot move the plan.

Theme, screen filters/sort, drafts and cache/download choices follow the same local ownership rule. Push-category toggles are different: save intent locally and queue only the minimal device delivery-policy update so the server can suppress background pushes. OS permission remains authoritative on that device; do not back up permission grants or treat a restore as permission.

## Login and first setup

1. Open WS and submit phone login. Existing account returns its profile; new account collects registered name and optional picture. No OTP screen now; keep an explicit future verification state in session logic.
2. Bind the server-issued user/device, store session secrets securely, open that account's local DB.
3. If a same-account local archive is available, offer restore. Archive restores local chat/files; server sync remains authoritative for shared data.
4. Download paged server metadata into staging; show setup progress/retry. Publish the snapshot and cursor atomically after completion, then replay changes since its boundary.
5. Request contacts permission with a useful explanation; denial proceeds with registered names. Contact changes/permission revocation refresh or clear aliases. For hidden phone identities, use registered/anonymous names rather than revealing contact matches.
6. Request notifications permission and register the device token when granted. Denial proceeds; token/category changes synchronize when connected; unregister on opt-out. OS permission state stays local. A pending opt-out is applied on reconnect; the UI must not claim server suppression before acknowledgement.
7. Pull this device's pending deliveries and drain queued actions. First setup is complete when the authorized metadata projection is ready; large media is never downloaded wholesale.

The server does not need the whole address book. For circle invitations, use registered relationships or share invitations; do not silently upload contact lists to discover accounts.

## Connection and action state

Connection: `signed_out → connecting → authenticating → syncing → ready`, with `offline`, `reconnecting`, `reauth_required` and `resetting` branches. Session expiry renews through WS or moves to login; revoked sessions stop retries immediately.

Action: `queued → sending → accepted`, or `waiting_for_dependency`, `needs_review`, `expired`, `rejected`. Timeout/disconnect means unknown outcome: resend the same intent. A result atomically records acceptance and applies returned entity projections if supplied; the sync feed eventually reconciles all shared records. Mark an action accepted even if the result arrived before its sync event. Never lose an outbox row because the socket closed.

Different entities can proceed concurrently; order actions within each entity/dependency chain. A version conflict fetches current state and requests review rather than silently overwriting. Offline album uploads wait for connectivity and then upload bytes before completing/linking. Money confirmation stays pending until the server accepts it.

Retry with jittered backoff, bounded inflight requests and reconnect triggers from foreground/network recovery. App screens share one connection. Background operation is best effort; push alerts cannot guarantee silent background sync. On foreground always reconcile, even if no push arrived.

## Sync, chat and multiple devices

Apply metadata batches and cursor together in SQLite. Stage snapshots separately from visible tables; never expose half of a replacement. Preserve local chats/outbox across metadata refresh, but reconcile their permissions against the new snapshot. Access loss purges protected projections/files and rejects forbidden pending intents. Offline revocation cannot erase copies immediately.

Message receipt: transactionally save event ID, message/reaction and any file-download task → acknowledge event → download required chat-only files → acknowledge each durable file. Duplicate receipt is harmless; an ack lost in transit is resent. Room IDs may hydrate after a message arrives; keep bounded pending rows. Message previews in the Inbox derive locally, not from a server chat-history query.

Sender UX distinguishes queued, server accepted, delivered to target account and expired. Internal per-device bookkeeping can be aggregated; do not show read receipts. Reactions on missing messages remain bounded pending updates or are discarded after expiry. Typing timers disappear automatically after TTL.

Each device has its own outbox/cursor/history. The sender's other existing eligible devices receive the event too. Newly added devices get server metadata and future chat only. V1 has no device-to-device history transfer. Explicit local archive import is the restoration path; do not imply chat magically synchronizes across installations.

## Local projections instead of extra server entities

Live uses the plan’s meeting-artifact reference, artifacts and responses; no separate Live record. Member labels and counts come from authorized participants. Wrap is a read-only summary of current shared records (or `wrap.get`), cached as a view with a stale/offline label; it is not independently edited or synced. Invalidate it when its plan, decisions or album references change.

Scrapbook bookmarks are account-local media IDs. Toggling a favourite writes only local storage, works offline and produces no outbox action. Another device starts with its own favourites unless the user explicitly restores a local archive. Album sync still supplies shared photos; removing access hides the asset and purges its bookmark/cache. A restored bookmark cannot restore revoked access. Shared plan pins use server artifacts and are unrelated to these personal favourites.

Money screens may cache calculated balances but always submit financial mutations against the underlying obligations and versions. Never add a second local/server ledger as an authority. Ripple forms use bounded slot arrays and selected IDs rather than separate client slot joins.

## One plan across Chat and Live

Both screens subscribe to the same local artifact/response tables keyed by plan and artifact ID. Pinning previews exactly what will become a saved plan note. A pending pin or vote is an optimistic overlay in both views; rejection rolls it back in both. Chat references open the shared detail, not an independent copy. Current cards are available on a new device even when their original chat messages are gone.

Poll totals come from server-projected aggregate counts plus the viewer’s own response; “Got it” belongs to a specific meeting-point version. A location card provides directions and capture time, never an implied moving dot. Personal points use an expiring local cache excluded from archives; clear at expiry, withdrawal, access loss or cancellation. Offline screens label shared state as potentially stale and disable votes locally after known deadlines; server time remains final authority. Expired-source pinning offers a reviewed standalone note.

Ripple forms preserve multiple selected slots and editable replies. Conversion opens the plan form for review, with suggested invitees rather than confirmed members. Keep the conversion intent stable across retry and navigate to the returned plan ID once accepted.

## Backup and restore

Define device-only as an app-created local archive in device storage, with user-selected local export/import; no scheduled cloud upload. A user may move an exported file themselves. Do not claim OS cloud backup is disabled unless native backup configuration is verified separately.

Proposed v1 archive includes local chat/reactions, downloaded chat media, optional kept-offline album files, drafts, local Scrapbook favourites and explicit local setting overrides (not resolved device defaults or OS permissions). Shared server metadata can be cached for startup but must be replaced/revalidated. Missing files are listed in a manifest, not silently treated as complete. Display backup timestamp and included/excluded media counts.

Use a consistent SQLite snapshot, checksums, archive schema version and passphrase encryption via a reviewed library. Never include access/refresh tokens, push tokens, device ID, contact book/aliases or signed URLs. A forgotten passphrase cannot be recovered by the server. Scope contents to one account; reject another account's import.

After restore, authenticate again and register a new device, migrate archive schema, stage imported data, revalidate room/media grants, and bootstrap server metadata with a fresh cursor. Restore chat IDs for deduplication but never replay old delivery acknowledgements as another device. Inflight/submitted actions are excluded from backup; unsent drafts restore as drafts for explicit resubmission, avoiding old payment/message replay. Keep the original archive until import succeeds. Corrupt or newer archives fail without altering the current database.

Logout clears secrets, disconnects and locks the account namespace. Offer keep-on-device or erase-local-data; switching accounts never shows previous data. Keep/erase applies to app-controlled files, not user-exported archives.

## Screen wiring

| Screen / action | Repository and behavior |
| --- | --- |
| Login / profile | Session + people; contacts resolve names at render time |
| Today / plans / create / route | Plans; local agenda; WS mutations; real geographic stops and Places search |
| Circles / circle detail | People; members/invites/Board; sleep/wake mutations |
| Inbox / Go Open | Discovery + invitations + local chat summaries |
| Plan Live | Plans/artifacts; arrival, pin acknowledgements, polls, bring claims |
| Plan Chat | Delivery + shared artifacts; local messages, pin action, poll/place cards linked to Live, outbox, attachments, typing and reactions |
| Plan Album / Scrapbook | Shared album metadata and downloads; local favourites filter Scrapbook |
| Plan Money / overall splits | Money; integer balances by currency and settlement confirmation |
| Privacy / device | Local settings and OS permissions; server commands only for blocks, sessions, device management and push delivery policy; local backup and logout |
| Ripple / Wrap | Shared Ripple responses/conversion; Wrap derived from current records |

Replace name arrays in current models with user IDs and profile projections. Extend `PlanStop` with geographic coordinates/place ID. Keep UI appearance state independent from business sync. Production mode never mixes fixtures with real accounts; preview mode uses an explicit repository adapter.

## SDK choices to verify during implementation

Use SDK-57-compatible Expo modules for SQLite, contacts, notifications, secure storage, file storage, audio and media picking, installed using Expo's version resolver. Use `react-native-maps` with Google provider on iOS and Android, restricted platform keys and development builds. Do not use the Apple-only map implementation for Google Places results.

References: [SQLite](https://docs.expo.dev/versions/v57.0.0/sdk/sqlite/), [Contacts](https://docs.expo.dev/versions/v57.0.0/sdk/contacts/), [Notifications](https://docs.expo.dev/versions/v57.0.0/sdk/notifications/), [Maps](https://docs.expo.dev/versions/v57.0.0/sdk/map-view/). This is API selection guidance; no native package installation or runtime integration is claimed here.
