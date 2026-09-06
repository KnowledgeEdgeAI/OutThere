# OutThere Product Roadmap

## Goal

Validate whether OutThere helps close groups turn “we should hang out” into a real plan. Start with a fast private prototype, make production choices only after the core journey is proven, then launch and grow deliberately.

## Roadmap at a glance

| Phase | Timing | Primary outcome |
| --- | --- | --- |
| 1. Prototype app | 4–8 weeks | Fast, instrumented private beta for up to 50 users. |
| 2. Production build and app-store launch | After beta | Freeze v1, build a scalable backend, and publish to Google Play and the Apple App Store. |
| 3. Growth and business | After launch | Improve reliability, market the product, test the business model, and scale. |

---

## Phase 1 — Prototype app

**Duration:** 4–8 weeks  
**Audience:** Up to 50 trusted testers

**Purpose:** Learn quickly with real groups and identify the smallest experience that consistently creates successful plans.

### Build principles

- Use over-the-air updates whenever possible, so testers receive improvements without manually installing a new build.
- Keep sign-up light: no OTP or phone-number verification during this private test. Accept the phone number a tester enters without validating it; use invitation-based access instead.
- Optimise for speed and low cost, not long-term scale. An in-memory or lightweight development database is acceptable at this stage.
- Make feature flags and design changes easy, so flows, copy, features, and interaction patterns can be tested without major rebuilds.
- Design for a 50-user cohort only. Do not spend beta time on global-scale infrastructure.

### Observe the core journey

Track behaviour, not just opinions:

- Invitation accepted and onboarding completed
- Circle created or joined
- Ripple sent and response rate
- Time from idea to confirmed plan
- Plan completion and repeat usage
- Drop-off points, errors, and common support questions

### Weekly rhythm

Review behaviour and feedback every week. Choose the one or two biggest problems in the core flow, ship a small update, and speak to a handful of active and inactive testers. Do not add a feature unless it solves a repeated problem.

---

## Phase 2 — Production build and app-store launch

**Starts after Phase 1 proves the core user journey.**

**Purpose:** Turn the validated prototype into a dependable product that can support users worldwide, then launch it on Google Play and the Apple App Store.

### Freeze v1 before building

At the end of the beta, freeze the v1 feature set, primary user journey, and design direction. “Freeze” means no more experimental scope in the launch build; new ideas go into a ranked post-launch backlog.

### Production-grade foundations

- Replace the temporary data layer with a durable, secure production database and reliable backups.
- Design the backend, APIs, and data model for worldwide users, multiple time zones, and growth in activity.
- Add proper authentication, account recovery, consent and privacy controls, and secure data handling.
- Set up reliable notifications, error monitoring, analytics, performance monitoring, and a basic support workflow.
- Test reliability, accessibility, mobile performance, and failure cases before app-store submission.

### Launch readiness

Confirm that the key flow works end to end: a person can join a group, create or respond to a plan, coordinate it, and return. Prepare store listings, screenshots, a privacy policy, terms, support contact, and a simple release plan.

---

## Phase 3 — Growth and business

**Begins with the app-store launch and continues as the operating phase.**

**Purpose:** Grow a repeatable user base while keeping the product reliable and learning what business model fits naturally.

### Marketing

- Start with the audience that showed the strongest repeat use in the private beta, such as flatmates, office friends, sports groups, or college communities.
- Use a simple message: *OutThere helps close groups make plans happen, without endless group-chat back-and-forth.*
- Use early testimonials and real group stories; improve invites and referrals only after the product consistently delivers a successful first plan.

### Business plan

Do not force monetisation before people repeatedly use the product. Once the core journey is working, test business options that help planning instead of interrupting it: premium group tools, relevant activity or venue partnerships, and referral revenue where it benefits users.

### Scale and reliability

- Prioritise high-impact bugs, failed notifications, and support issues immediately after launch.
- Track activation, retention, successful plans, repeat plans, referral rate, and cost to acquire an active user.
- Scale infrastructure in response to real demand. Keep the post-launch roadmap in this order: reliability, retention, growth, then new features.

## Decision rule

Move forward only when groups are successfully making plans and choosing OutThere again. Downloads are useful, but repeat planning behaviour is the real proof that the product works.
