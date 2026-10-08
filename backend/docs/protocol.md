# Client protocol · v1

This documents the running prototype. See the [target v2 protocol](../../docs/backend/protocol.md) for the newly agreed all-WS login and application events, per-device temporary chat delivery, and metadata-only sync. Do not send v2 events to this v1 server yet.

HTTP handles sessions. One authenticated WebSocket handles app commands, queries, chat, and changes. Use HTTPS/WSS outside local development.

## Sign in

`POST /v1/auth/exchange`

```json
{"invite_token":"<one-use invitation>","display_name":"Sara"}
```

Returns `user_id`, `access_token`, `refresh_token`, `token_type`, and both expiry times as Unix seconds. Access lasts 15 minutes; the session lasts 30 days by default.

`POST /v1/auth/refresh` with `{"refresh_token":"…"}` rotates both tokens. Reconnect the socket using the new access token and saved cursor. The old refresh token stops working immediately; a lost refresh response currently requires signing in again.

`POST /v1/auth/logout` with `Authorization: Bearer <access_token>` revokes the session and returns 204. Connected sockets detect revocation on their next feed check.

## Open the socket

Connect to `/v1/ws`. Send this first, within 10 seconds:

```json
{"type":"auth","access_token":"<access token>","cursor":0}
```

The server replies `{"type":"ready","user_id":"…"}`. Tokens never go in URLs. Browser origins must match `OUTTHERE_ALLOWED_ORIGINS`; native clients can omit Origin.

## Send an action

```json
{
  "id":"bde5cf7c-7450-4966-8887-774b37c41a32",
  "type":"command",
  "name":"circle.create",
  "action_id":"dc87fd50-4388-46b4-98aa-6c8ebfca3e36",
  "payload":{"name":"Sunday crew","kind":"social"}
}
```

`id` correlates a reply. `action_id` identifies the durable user action: keep it and its payload unchanged when retrying, even after reconnecting. A successful retry returns the original result. Reusing it for different content returns `action_conflict`.

| Command | Payload |
|---|---|
| `circle.create` | `name`, optional `kind`: `social` / `work` |
| `circle.invite` | `circle_id`, registered `user_id`; owner only |
| `circle.join` | `circle_id`; requires invitation, maximum 15 members |
| `plan.create` | `title`, `starts_at`, `ends_at`, optional `circle_id`, `venue_timezone`, `place_label`, `latitude` + `longitude` |
| `plan.rsvp` | `plan_id`, `rsvp`: `in` / `maybe` / `out`, own participant `version` |
| `message.send` | `plan_id`, `body` (1–2,000 characters) |

Plan times are ISO 8601 with timezone offsets. The venue timezone is an IANA name, default `Asia/Kolkata`. A plan snapshots current circle members; later joiners do not automatically gain access. Without a circle, the plan is visible only to its host. Plan and participant versions are separate; RSVP conflict checks use the participant version.

Queries use `type: "query"` and omit `action_id`:

| Query | Payload |
|---|---|
| `me` | `{}` |
| `circle.list`, `plan.list`, `invitation.list` | optional `offset`, `limit` (1–100) |
| `plan.get` | `plan_id` |
| `message.history` | `plan_id`, optional `before_seq`, `limit` (1–100) |
| `places.search` | `query`; disabled unless configured |

Lists return `items` and `next_offset`. Chat history returns chronological `items` and `next_before_seq` for older messages. List offsets are not a stable sync cursor; use changes for synchronization.

## Receive and persist

Replies and change batches can interleave:

```json
{"type":"result","id":"<request id>","data":{"id":"<entity id>"}}
```

```json
{"type":"error","id":"<request id>","error":{"code":"version_conflict","message":"Fetch the plan and review your RSVP"}}
```

```json
{
  "type":"changes",
  "events":[{"seq":12,"kind":"message.created","data":{"id":"…","plan_id":"…","sender_id":"…","seq":3,"body":"See you there!","created_at":"2026-10-01T10:00:00+00:00"}}],
  "cursor":12,
  "has_more":false
}
```

Event kinds: `circle.changed`, `circle.invited`, `plan.changed`, `message.created`. Change sequence numbers are per account; message sequence numbers are per plan. Changes hydrate current authorized data, not historical snapshots. Multiple references may resolve to the same current entity.

Apply a batch and save its cursor in one local transaction. Upsert by entity ID; preserve feed order. Keep cursors per account/device and restart at zero if the local cache is erased. Even an empty batch can advance the cursor when access-filtered entries are skipped. `has_more` means the server will send more automatically.

On `version_conflict`, fetch the plan and let the user review the RSVP before sending a new action. On reconnect, resume the saved cursor and retry unacknowledged actions. Never treat socket delivery as proof of a database commit; `result` is the command acknowledgement.

Frames are limited to 16 KiB and 60 valid requests per 10 seconds per connection. Limits are local guards, not account-wide abuse prevention. Feed retention/reset and client cache purge events will be added before membership removal ships.
