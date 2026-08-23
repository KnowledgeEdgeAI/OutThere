# OutThere — Product Base Doc

**Intimate plans first. Strangers only through mutual consent.**
The single source of truth for what we're building. Everything lives here;
decisions get recorded, not debated twice.

---

## 1. Principles

1. **Plans belong to small groups.** The unit is 3–15 people with shared
   context (flatmates, colleagues, friends). A plan never requires a circle,
   but circles are where rhythm comes from.
2. **No browsing of strangers. Ever.** No public profiles, no search, no feed.
3. **Both-way or nothing.** Any stranger contact requires simultaneous,
   symmetric opt-in. Passing is silent and invisible.
4. **Chat has a job title.** Messaging exists inside plans/warm rooms only,
   and every meaningful message becomes an artifact (see §9).
5. **Presence without surveillance.** Coarse time windows and distance bands;
   live location off by default, per-plan, self-expiring.
6. **Every plan ends settled** — money netted, photos consented, next one seeded.

## 2. The decision ladder (core mental model)

| You know… | Primitive | Direction |
|---|---|---|
| what + when + who | **Plan** | outbound, committed |
| a feeling + rough slot, your people | **Ripple** | outbound, converging |
| free but aimless, open to anyone nearby | **Open** (was Window) | inbound, strangers via mutual hi |

Everything else (Overlaps, Hello rooms, Wraps, Scrapbook, Splits) is machinery attached
to these three.

## 3. Core objects

- **Person** — phone-verified account (verification is the floor, not a
  filter — see §11). Optional selfie-verified badge. Vibe tags, home area
  (coarse), free Opens.
- **Circle** — invite-only group, 3–15 members ("small stays warm"). Members
  can all create plans. Roles: owner + co-hosts for settings only.
- **Plan** — scoped to any mix of: circles, direct people, or link-only
  invites (host approves). Time, fuzzy place, RSVPs, pinned meeting point,
  artifacts (§9), splits, wrap.
- **Ripple** — the soft ask: a feeling + rough slots tossed to your people.
  Converges into a plan or fades (§6).
- **Open** (was Window) — availability signal: "Sat 5–8 PM · badminton/chai ·
  within 2 km". Never displayed as content; only matched. Quietly visible to
  your own social circles as ambient availability ("Sara kept Sat evening free").
- **Overlap** — two compatible Opens meeting. Anonymous card lands in both
  Inboxes; mutual hi opens a Hello room (§7–8).
- **Wrap** (was Recap) — post-plan container: auto-drafted timeline, sorted
  album, settled money, vibe checks, next-plan seed (§5).
- **Scrapbook** — cross-plan media shelf: every plan attended, auto-filled
  from Albums; filter by circle/person/month; pin favourites; shareable as
  one signed, expiring link.
- **Settlement** — expenses scoped to a plan, netted per person across all
  plans (§10).

## 4. Circles

- Invite-only, always. Growth via share links (WhatsApp-first), table QRs,
  or when an overlap becomes a friendship.
- Inside a circle: no approvals for plans — just RSVP. Trust is structural.
- Plus-ones: host toggle per plan; guests pass through mini flow (§5 guests).
- **Anti-sprawl:** circles auto-sleep after 60 days dormant (archived, one-tap
  wake). Merge suggestions when member overlap > 80% ("Flat 402 looks like
  Sunday cyclists +2"). Cross-circle duplicate plans deduped in views.
- Work circles: colleagues see RSVPs, **never** your Open/availability (§11).

## 5. Plans

### Creation
Natural-language input ("casual badminton, then filter coffee") → audience
(circles / direct people / any mix / none) → when + fuzzy where. With zero
audience selected it becomes a **link-only invite**: anyone with the link asks
to join, host approves.

### RSVP culture
Inside circles and direct invites there are no approval queues — yes / maybe /
no, changeable until lock. Approvals exist only for link-guests.

### Guests (people in plans but not circles)
- Get plan-room access scoped to that plan.
- Access goes read-only 24h before start, archived at plan end + 7 days.
- Guests appear in wraps/splits for that plan only.

### Edge states (specified, not improvised)
- **Nobody RSVPs by T-3h:** host gets one nudge with options (cancel, bump
  time, toss a ripple instead). No auto-cancel embarrassment.
- **Time change after lock:** becomes a mini poll; passes automatically if
  nobody objects within 2h and ≥2 confirm.
- **Rain check / cancel:** one tap, reason optional, splits auto-refund to
   zero, plan converts to a wrap stub ("we'll get you next time") with a
  one-tap reschedule seed.
- **Paid pins cancelled:** refund status shown inline per attendee.

### Live day
Arrival mode (here/en-route), quick updates ("5 min late"), polls, pinned
point, check-in prompt for post-9PM ends (§11).

### Wrap (was Recap) — the handoff, not a memento
1. **Auto-drafted timeline** — pinned spot, poll outcomes, arrival stats
   ("crew arrived within 12 min"), expenses — exists before anyone uploads.
2. **Dump-first album** — everything uploaded lands in the plan's Album,
   visible to the plan's audience (attendees; the whole circle when the plan
   is circle-scoped). Consent is a quiet exit: anyone taps hide on a photo of
   themselves — instant, silent, no notifications. No tagging, ever.
   Auto-dedupe merges duplicate copies and folds bursts to the best shot;
   videos ride the same pipeline. "Send pics to [person]" shares originals
   via signed, expiring links; nothing leaves the app without an explicit
   share.
3. **Highlights float to Scrapbook** — your picks + most-loved land in each
   attendee's Scrapbook automatically; pin favourites to keep them.
4. **Vibe check** — each attendee privately taps how it was (3 options);
   aggregate powers the profile community score. Never public per-event.
5. **Handoff block** — splits status, "next: Sat Aug 30 ✓" recurrence seed,
   and "3 of you are free next weekend — toss a ripple?" bridge.

## 6. Ripple (the soft ask)

Most plans begin as *"ey, anything happening this weekend?"* — currently that
leaks to WhatsApp calls/group texts. Ripples own that moment.

```
COMPOSE ──► DELIVER ──► RESPOND ──► AGGREGATE ──► CONVERGE ──► RESOLVE
feeling     Today home  one tap    tally +      "Turn into    plan locked,
+ slots     banner +    + optional ranked       plan" with    fades, or
+ audience  Board       quip        slots       respondents   widens into
            (no push)               feed        pre-invited   an Open
```

- **Compose (10s):** feeling in NL, ≤2 rough slots, audience = circles +
  direct people mix, optional one voice note. Nothing locked.
- **Respond:** card, not message — `[ I'm in ]` `[ Another time ]`
  `[ Can't ]` + optional ≤140-char quip. Social proof visible. Quips are
  moderated content (profanity/harassment filters + report-on-quip at launch).
- **Aggregate:** sender sees tally + ranked slots. Sender-only milestones:
  first yes, "≥2 in — ready to lock?", expiring soon.
- **Converge:** ≥2 yes → one tap creates the plan with respondents
   pre-invited and best slot pre-filled. Or widen: spawn sender's Open with
   the same vibes.
- **Resolve:** locked → ripple closes; expiry → silent fade; zero yes →
   gentle "try an Open?" offer.

Rules: TTL 24–72h (default 48); max 2 active; audience ≤30; responses are
taps not chat; never per-response notifications (digest + milestones only);
quips visible to whole audience (social proof is the engine).

## 7. Opens & Overlaps

**Open:** personal, ephemeral signal. Shown as content to no one; matched
by engine; visible as ambient status to own non-work circles.

**Overlap state machine:**

```
Open live ──► engine match (anonymous card in BOTH Inboxes)
                    │
        you tap "say hi"      other passes ──► nothing happens, ever
                    │
        both tapped hi ──► Warm Room (§8)
```

Rules:
- Cards reveal only: shared vibes, overlapping slot, distance band.
- No text exists before the Warm Room → zero cold messages.
- Comfort filter: women-only matching (requires selfie-verified tier to be
  meaningful — see §11), applied symmetrically.
- Rate limits: max 2 active Opens, max 8 cards/day, max 3 Hello rooms;
  half limits for accounts younger than 2 weeks.
- **k-anonymity gate:** a card is only delivered if ≥3 coarse candidates
  match the query; otherwise show an aggregate hint ("several people near you
  kept Saturday evening free"). Delivery times jittered ±20 min. This kills
  re-identification in low-density areas.
- Cold start: sparse regions show aggregate demand hints so the feature never
  reads as broken-empty.

## 8. Hello (was Warm Room)

- Opens only on mutual hi. 24h TTL, **one 48h extension** allowed (locking
  plans with strangers takes a day of logistics; the extension removes the
  pressure without reopening DM risk).
- First names only until a plan locks; full profiles unlock on lock.
- Single purpose: propose → agree → lock. Proposal card supports tentative
  date polling.
- Report / Block / Pause reachable in one tap throughout.
- No lock by TTL → silent close, mutual invisibility restored.

## 9. Comms — the plan room: LIVE · CHAT · ALBUM · MONEY

Positioning: **we don't replace WhatsApp; we replace the six apps you open
because of WhatsApp.** Every plan gets one room with four bottom tabs
(was NOW / WIRE / SPLITS, plus Album). Chat is glue; artifacts are the product.

| Tab | Job | Not allowed |
|---|---|---|
| LIVE | glanceable state: arrivals, next-up, live artifacts | human chatter |
| CHAT | light planning talk | raw forwards (converted instead) |
| ALBUM | photos & videos — dump-first, auto-sorted (§5) | tagging chores |
| MONEY | netted balances, gentle nudges | — |

Artifacts — any message can become one, and artifacts render on LIVE:

- **Pin** — paste maps link or pick place → meeting-point card; recipients tap
  **"Got it"** (agency receipts, no blue ticks). Time changes work the same.
- **Ticket** — forward/upload booking → card with QR, entry name, gate time;
  auto calendar entry; price → one-tap split into SPLITS.
- **Poll** — chips in CHAT + LIVE; auto-closes at plan start; result pins as a
  decision.
- **Bring list** — claim items ("racquets — Aarav").

Acting on Live posts quiet system lines back into Chat (latecomer catch-up).
Rooms archive into the Wrap 24h after plan end.

Guardrails:
- No DMs, no open groups, ever. Circles get a **Board** of open loops
  (proposals, polls, ripples — all with TTLs), not a chat.
- No typing indicators, read receipts, or online dots. Presence = arrival.
- Bridges, not walls: every plan renders a **view-only web card** — shareable
  into any WhatsApp group; guests RSVP, see the pin, get directions, no app
  required. Signed, expiring URLs.

## 10. Money — Splits

- Expenses attach to plans; balances are **netted per person across all
  plans** ("you owe Aarav ₹120 net"), never two directional fragments.
- Views: net balance card, by-plan ledger, by-person ledger; settle via UPI
  intent links.
- Reminders: private, rate-limited (max 1 per person per 7 days), framed as
  gentle nudges. Settle-all sweeps available.
- Principle: **money never blocks a plan.** Settling is async forever.

## 11. Trust, Privacy & Safety

### Identity tiers
1. **Phone-verified** — mandatory floor for having an account (hence not a
   filter; it differentiates nothing).
2. **Selfie-verified badge** — optional; the only public trust mark. Required
   to use women-only matching (makes the filter honest).
3. Reputation = community score from private vibe checks (aggregate only).

### Visibility matrix

| Data | Social circles | Work circles | Warm-room match | Nearby (pre-match) |
|---|---|---|---|---|
| Photo & full name | ● | ● | ◐ first name | ○ |
| Open window / ambient status | ● | ○ never | ◐ overlap part only | ○ |
| Neighbourhood | ● | ◐ city | ◐ distance band | ◐ distance band |
| Interests/vibes | ● | ◐ limited set | ◐ shared only | ○ counts only |
| Past plans/wraps | ● attendees only | ○ | ○ | ○ |
| Live location | ◐ per-plan opt-in | ○ | ○ | ○ |

### Structural guarantees
- No search, no public profiles, no follower anything.
- Phone numbers shared only inside confirmed plans, never in warm rooms.
- Wraps attendee-scoped. Nothing discoverable.

### Boundaries
- **Block:** instant, silent, mutual invisibility across Opens, overlaps,
  boards, wraps; pending matches auto-cancel both ways. Shared unavoidable
  plans switch to **household mode**: mutual mute, minimized rows, admins see
  nothing.
- **Pause (ghost mode):** freezes presence everywhere; plans persist.
- **Check-ins:** plans ending after 9 PM prompt a safe-home tap; no reply
  pings the pre-chosen contact.
- **Reports:** 2 taps anywhere; human review; serious flags suspend active
  matches involving that account immediately.
- **Content moderation:** quips, room messages, and photo captions run
  filters from day one; report-on-any-artifact.

## 12. App architecture & design system

### Navigation (v3 — shipped in demo)
Bottom-anchored only, thumb-first; nothing floats to the top.
**TONIGHT · CIRCLES · [＋] · INBOX · YOU** — [＋] opens the action sheet
(Plan / Ripple / Open / New circle); INBOX holds everything waiting on you
(RSVP deadlines, ripples, overlap cards, nudges, settlements). CREATE is gone
as a tab; OVERLAPS live in INBOX as cards; every circle keeps a Board of open
loops. Plan rooms swap the main bar for four tabs — **LIVE · CHAT · ALBUM ·
MONEY** — and Wrap closes the loop, saving highlights to Scrapbook.

### V3 naming (same engine, simpler words)
Open (was Window) · Hello (was Warm Room) · Wrap (was Recap) ·
In/Maybe/Out (was Yes/Maybe/No) · plan-room tabs (was NOW/WIRE/SPLITS) ·
Album: dump-first, hide-if-you-want, auto-deduped · Scrapbook: cross-plan
media shelf. Artifacts: `outthere-v3-design.svg` (design sheet) ·
`outthere-v3-demo.html` (interactive demo).

### TODAY triage order (anti-clutter contract)
1. Live plan now (if any) — pinned
2. Waiting on you (≤3 items, expandable)
3. Rest of today/tomorrow — collapsed rows
Nothing else on the home screen. Digest handles the rest.

### Color roles (locked)
| Token | Meaning |
|---|---|
| coral | act now (primary CTA) |
| lilac | information |
| sun | time / expiring |
| peach | soft / personal |
| lime | success / settled |
Avatars use initials in prototypes; real avatars ship with moderation.

### Theming
System-following light/dark with manual override; all surfaces tokenized.

## 13. Notifications

Hard budget: daily digest ≤6 items, priority order — plan-day changes >
RSVP deadlines > ripple milestones > settlement events > ambient.
Realtime only for: plan-day logistics, arrivals (if opted in), check-ins,
safety flags. Zero engagement spam; no streaks, no FOMO mechanics.

## 14. Growth & cold start

- Activation without a circle: solo value first (go Open, browse-free
   planning, link invites), circle-building prompted gently after first plan.
- Web plan cards are the WhatsApp distribution channel (§9).
- Density bootstrapping: college/office circles first; aggregate demand hints
  keep overlaps alive in thin areas (§7).
- Launch geography: Bengaluru urban cores; distance bands tuned per density.

## 15. Roadmap

- **P0 — believable loop:** auth, circles + invites, plans + RSVP (circle /
  direct / link-only), ripples basic (compose → tap → tally), live mode,
   splits with netting (manual IOU ok), Opens + overlaps engine, block /
  report / pause, web plan cards.
- **P1 — depth:** ripple→plan conversion polish (slot ranking), hello-room
   extension flow, wrap v2 (auto-draft, dump-first album + dedupe,
   scrapbook, vibe checks), check-ins, selfie-verification tier, edge-state flows.
- **P2 — texture:** colleague templates (lunch roulette), recurring/standing
  plans, quiet hours, city expansion tooling, highlights-only albums.

## 16. Metrics

- North star: **plans-that-happened per active user per week.**
- Guardrails: overlap→plan ≥25%; ripple→plan ≥40%; block rate <1%; users with
  ≥1 circle of ≥3 members by week 4 ≥60%; digest opt-out <5%.

## 17. Open questions

- Plus-one guests: does the host's approval suffice, or a lightweight
  host-vouches flow? (Guest access expiry decided: plan end + 7d.)
- Women-only matching: jurisdictional/legal review of selfie-tier storage.
- Distance band granularity vs density tuning per city.
- Under-18 policy: proposal is strict 18+; needs final call.
- Standing/recurring plans: how do instances, wraps, and splits nest?
