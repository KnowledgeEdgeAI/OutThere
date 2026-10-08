# OutThere mobile

The [mobile data-layer design](../docs/backend/mobile.md) and [server/client architecture](../docs/backend/design.md) specify how this preview will connect through one shared WebSocket, local SQLite, a durable outbox, metadata sync, temporary chat delivery and device-only backup. This README describes the current preview, not those future capabilities.

One React Native + Expo app for Android and iPhone. Plan screens use sample data. The Account screen connects to the v2 server when `EXPO_PUBLIC_API_WS_URL` is configured. It follows the current material system and layouts in the root `index.html` prototype: DM Sans typography, page-specific color washes, compact agenda and group rows, floating navigation, and plan tabs above the content.

## What works in the preview

- Plans, Circles, Inbox and You with a central New action.
- Create and edit plans with linked places and arrival times, add/remove stops, search six sample Bengaluru places or name a custom map pin, and review a numbered route preview. Native date/time pickers and quick day/time choices work on phones; editable date/time fields work in the browser.
- View each saved stop and arrival in the plan room; agenda cards use the first stop.
- Create circles from sample people; wake sleeping circles.
- Plan rooms with Live, Chat, Album and Money tabs.
- Local RSVPs, arrival check-ins, a coffee poll, ripple replies, chat messages and sample settlement state.
- Scrapbook, plan balances, privacy overview and System/Light/Dark appearance in Appearance & device.

Changes are in memory and reset on reload. Photos are illustrated placeholders. Payments, real invitations, notifications, Open matching and product synchronization are not implemented. Accounts, profile editing and device sessions use the real server when configured. Android and iPhone use the same screens and state.

## Run

Use Node.js 22.13 or newer. From this directory:

```sh
npm ci
npm run web
```

The browser preview is useful for reviewing layout and sample interactions. Route date/time picking uses native controls on phones; web provides editable date/time fields. Route maps are illustrative and place search uses local samples, matching the root prototype.

For a local native development build:

```sh
npm run ios
npm run android
```

The iPhone command requires Xcode and an installed iOS simulator runtime. Install a runtime from Xcode Settings → Components (or Platforms on older Xcode versions). Android local builds require Android Studio and an emulator or connected device. Expo generates the `ios/` and `android/` projects when building; these generated directories are ignored. Native configuration belongs in `app.json` and Expo config plugins.

To run on a connected iPhone:

```sh
npx expo run:ios --device
```

Select your device, configure Apple signing when prompted, and enable Developer Mode on the phone. A local personal-device build can use a personal Apple Account, subject to Apple's development signing limits.

## Cloud builds for both platforms

The `eas.json` profiles support:

| Profile | Purpose |
| --- | --- |
| `development` | A development client for Android or a registered iPhone |
| `simulator` | An iOS simulator development client |
| `preview` | An Android APK or signed internal iPhone preview |
| `production` | Store-ready build configuration |

Log in if needed and link the project to the intended Expo account or organization before the first cloud build:

```sh
npx eas-cli@latest login
npx eas-cli@latest init
npm run build:android
npm run build:ios
```

`build:android` uses the preview profile; `build:ios` uses the development profile. EAS iPhone device builds need Apple Developer Program signing and device registration. Android builds can be generated in the cloud without installing Android Studio locally. Do not submit or publish until the app is ready.

The design refresh uses a bundled, tintable background image and bundled DM Sans fonts. Both work with the existing development client after reloading; no additional native background module is required.

After installing a development client, start its server:

```sh
npm start
```

Keep your computer and phone on the same Wi-Fi. Expo CLI shows the connection URL/QR. This project uses SDK 57: the App Store Expo Go currently remains on SDK 54, so use a compatible development client rather than assuming the store's Expo Go will open it. See [Expo Go compatibility](https://docs.expo.dev/troubleshooting/expo-go-version-mismatch/) and [development builds](https://docs.expo.dev/develop/development-builds/introduction/).

## Structure and checks

The source folders have distinct responsibilities:

- `src/app/`: Expo Router screens and layouts; screen-specific presentation stays here.
- `src/ui/components/`: shared controls, typography, page layouts, lists and plan cards. Import components directly from their modules.
- `src/ui/plan-room/`: Live, Chat, Album and Money presentation, plus the shared pinned-place card. The chat composer keeps its draft when switching sections.
- `src/ui/theme/`: colors and appearance providers. `useTheme()` reads presentation settings independently of demo interactions.
- `src/ui/navigation.tsx`, `src/ui/useReducedMotion.ts`, `src/ui/format.ts`: navigation presentation, accessibility preferences and display formatting.
- `src/domain/`: plain TypeScript models and plan creation/ordering rules, with no React Native or routing dependencies.
- `src/state/`: the in-memory demo context and actions, accessed with `useAppState()`.
- `src/data/`: sample fixtures, isolated from UI and domain rules.
- `tests/`: regression checks for plan creation, local-day agenda selection and circle filtering.

Keep business rules in `domain/`, state changes in `state/`, and rendered elements in `app/` or `ui/`. Avoid compatibility barrels and forwarding wrappers when a direct import works.

```sh
npm test
npm run typecheck
npm run lint
npx expo export --platform all
npx expo-doctor
```

Verified: TypeScript and lint, Android/iOS/web bundling, and browser interactions for navigation, plan creation, RSVP and chat. The iOS development build also compiles successfully and installs on the iPhone 17 Pro simulator after applying the path-with-spaces workarounds. Physical-device and Android native execution are still to be verified. Expo Doctor's online config-schema check timed out against the Expo API; the other 20 checks passed.

### iOS checkouts in folders with spaces

Expo Constants 57.0.20 has unquoted paths in its iOS config generation phase. `scripts/fix-expo-constants-paths.cjs` applies a narrow, idempotent workaround through `postinstall`, before CocoaPods generates build phases. It quotes the script path and project-directory lookup and escapes an optional `PROJECT_ROOT`. Review/remove this workaround when upgrading Expo Constants. Existing Pods need to be regenerated once after applying the fix. The `plugins/with-ios-path-spaces.cjs` config plugin also quotes the template’s React Native bundle-script invocation when Expo generates the iOS project.

## Connected account slice

Copy `.env.example` to `.env`, configure the backend's explicit phone mode/retry key/allowed origins, migrate it and start the server and worker. Restart Expo after changing the environment. Open **You → Account** to sign in, edit a name, inspect sessions and sign out another device. Existing plan screens remain labelled sample data and never send fixture records to the server.

Native credentials use SecureStore with device-only keychain accessibility; account projections and the profile outbox use SQLite. A new installation marker prevents surviving iOS keychain credentials from silently restoring the old installation session. Browser credentials remain in memory; IndexedDB preserves account projections and pending edits across reloads, with fresh sign-in required. Never put credentials in public environment variables or browser local storage.

Pending profile edits keep their original action ID, timestamp and expected version across disconnect/restart. Confirmation updates the projection and removes the outbox item in one local write. Version conflicts and expiry require review; the Account screen offers discard before a fresh edit. Logout only claims server revocation after acknowledgement. Backgrounding closes the socket; foreground resumes the session and drains the outbox.

`src/data/account/` contains strict response types, the shared socket, account store, native/web storage and session controller. `src/state/AccountState.tsx` subscribes React and app lifecycle to that controller; `src/app/account.tsx` owns presentation only.

Added native modules require rebuilding the development client. Android, iOS and web bundles pass. Browser login, profile save and recovery of a pending edit after reload were exercised with synthetic data; native execution and PostgreSQL remain unverified. Dependencies follow the [SDK 57 SQLite](https://docs.expo.dev/versions/v57.0.0/sdk/sqlite/) and [SecureStore](https://docs.expo.dev/versions/v57.0.0/sdk/securestore/) APIs.
