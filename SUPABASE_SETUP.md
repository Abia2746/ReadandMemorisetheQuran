# Al-Mu'allim Supabase Auth — connected project

The existing Supabase project **Al Mua’llim** is connected using its **public Project URL and publishable key** in `supabase_auth.py`. These values are intended for client access, unlike private database/Stripe credentials. You do not need to paste the public keys into Streamlit Secrets.

## What has been implemented
- An optional **Account & sign-in** section in Streamlit (free Qur'an reading needs no login).
- Supabase one-tap email magic-link sign-in with a browser-side callback, server-side token verification, and session refresh during app renders.
- Secure `public.learner_profiles` and `public.hifdh_progress` tables with owner-only RLS.
- Read-only-to-learners `public.billing_subscriptions` table, reserved for future verified Stripe webhook writes.
- Signed-in users can save their cloud profile name. A successful recitation review attempts to save a **reviewing** marker, not a claim that the verse is memorised.
- No paid entitlement is granted simply by logging in or returning from Stripe checkout.

## Required Supabase redirect configuration

In the Supabase project dashboard, open **Authentication → URL Configuration**.
Set the **Site URL** to:

```
https://readandmemorisethequran-9uvtv8lpn9ozytdqtk6ceh.streamlit.app/
```

Save. Also add that exact URL to **Redirect URLs** if it is not already listed.
This step is required because Supabase otherwise sends users to the current default Site URL.

## Account experience (November 2026)

Al-Mu'allim now offers a dedicated **Sign in / Create account** button in the top navigation. This opens a branded dialog rather than the old collapsed expander.

The dialog provides **Sign in** for returning learners and **Create account** for first-time learners. Both use one-tap Supabase email links. Returning sign-in uses `create_user=false`, while registration explicitly allows account creation. Supabase may send a **Confirm your email address** message for first-time registrations; that is expected, and the secure confirmation must complete before the account is signed in.

## Test the proper one-tap magic-link sign-in

1. Open Al-Mu'allim and press **Sign in / Create account**.
2. If the account was already created, select **Sign in**. For new emails, select **Create account**.
3. Enter the address and request a **new** sign-in email.
4. Tap the emailed link normally **once**. Old or previously consumed links produce `otp_expired` / invalid-token errors and cannot be reused.
5. When redirected to the app, the Streamlit Components v2 callback reads and immediately removes URL-fragment tokens. Its server code verifies the account with Supabase Auth.
6. On success, the app shows a welcome confirmation, restores a stored learner profile name if one exists, and offers **My account** in the top navigation.

If a link returns to the homepage without a successful welcome message, it does **not** mean the email was confirmed. Check the account status in **Supabase → Authentication → Users**, and request another link if unconfirmed.

Sign-up confirmation email templates and sender branding still use Supabase defaults until custom SMTP is configured.

### Current preview limitations

Streamlit keeps the verified session in memory for the current app session, refreshes short-lived tokens during normal app use, and calls Supabase logout on sign-out. **The preview now attempts restoration across same-browser reloads; a different browser or cleared storage requires a new sign-in.** For production add durable secure session management, ideally through an application authentication backend using secure HttpOnly cookies. Before public launch, test Safari, Gmail in-app browsers, and cross-device redirects.

The built-in Supabase email sender has rate limits and may restrict recipients; configure a custom SMTP service before opening registration publicly.

## Production work still needed
- Durable, secure browser sessions (current preview refreshes active tokens but does not persist across full Streamlit resets).
- Google and Apple OAuth providers, configured redirects, and security review.
- Authenticated Stripe checkout creation with a mapped user ID.
- Verified webhook and durable payment state, subscription management portal.
- Server-side subscription entitlements; family-member policies and invitations.
- Actual full Hifdh history synchronisation (only revision markers currently sync).
- Mobile app store payment rules before releasing native apps.

Do not put any database password, Supabase secret/service-role key or Stripe secret key in GitHub.

## November 2026 account restoration update

The Streamlit preview now attempts to restore its Supabase session on browser refresh using a first-party Streamlit Components v2 browser-storage bridge. Expired access tokens are refreshed against Supabase Auth; identity is verified through /auth/v1/user on the server before access to private rows. Signing out clears the saved browser credentials and learner-specific Streamlit state.

**This is NOT production-grade persistent authentication.** Browser localStorage is accessible to same-origin JavaScript and does not provide HttpOnly/Secure cookie protections. Before public rollout, migrate to a dedicated secure authentication backend with properly configured cookies, CSRF defenses, session rotation and revocation. Shared devices need careful testing. No sign-in promise is absolute: users may need to authenticate again on expired/revoked sessions, incognito browsing or a different device.

For authenticated users, cloud restoration loads the saved nickname and up to 1,000 revision-status rows through the user's Supabase JWT and RLS. Unverified guest history is not silently moved into a different account. Audio recording files and full AI review results are *not* yet cloud synchronised; revision markers are not a teacher-certified memorisation record.

### Verification checklist
- [ ] Use a new valid email sign-in link and confirm login with real Supabase email.
- [ ] Reload the tab, close and reopen the browser, and verify the same account reappears.
- [ ] Verify learner's nickname and revision rows restore from Supabase correctly.
- [ ] Sign out, refresh, and verify no private account data returns.
- [ ] Sign into another account and verify the previous user's nickname/progress is absent.
- [ ] Expire/revoke refresh token and verify the app requires a fresh sign-in.
- [ ] Verify Safari private mode and mobile in-app email browser behavior.
- [ ] Replace localStorage with HttpOnly cookie-backed sessions before public release.

## November 2026: Cloud study data and Hifdh milestone

Account-owned Supabase tables added (RLS enabled, restricted to the verified owner):

- learner_settings: Quran language, passage, reciter, teacher options, sensitivity and clue mode. Saved automatically after changes.
- learner_hifdh_plans: adaptive plan, self-reported completed ayahs and daily sessions. Saved after planner actions and restored into an isolated local cache on sign-in.
- learner_recitation_reviews: up to 50 most recent text-only reviews restored on sign-in; the latest review per passage is retained. Raw microphone recordings are not uploaded.

Local planner and Prayer Room data for signed-in learners use the Supabase account ID, not the nickname. Guest sessions receive a distinct random local identity. Old nickname-only SQLite records are not automatically imported because names are not unique.

**Limits**: Prayer Room coins/equipment and XP/streak are still local. Full chat, recordings, all historic reviews and native notifications are not synced. Browser persistence currently uses localStorage in the Streamlit preview; migrate to secure HttpOnly cookie-backed auth before public launch. No money or premium status is inferred from these new tables.

### Cross-device acceptance tests still required
- [ ] Complete verified email signup, sign in and test same-browser persistence.
- [ ] Change language, reciter, teacher and ayah; verify cloud restoration in another browser.
- [ ] Save/edit a Hifdh plan; finish today's study and verify completion/session history on another device.
- [ ] Save text-only review feedback and verify it restores without an audio file.
- [ ] Sign in as another account and check that previous learner data is absent.
- [ ] Simulate unavailable network and confirm sync failures remain visible.
- [ ] Run GitHub Actions syntax and Hifdh planner snapshot tests.

The last Supabase check still had no email-confirmed learner, so end-to-end login and cloud sync cannot yet be claimed as passing.

## 24 November 2026 — Prayer Room cosmetic cloud backup

Added `learner_room_backups` with per-user RLS policies and a bounded JSON snapshot.
Signed-in accounts now attempt to save room XP, coins, purchased decorations, equipped items, reward ledger and streak state after eligible in-app actions. The next login can restore the snapshot into an account-specific local cache. Restore validates item names, caps, duplicate IDs and relationships before applying changes in a SQLite transaction.

The backup only covers **cosmetic in-app rewards**. It is user-writable and MUST NOT be used as proof of payment, premium entitlement, real money or authoritative competition standings.

Known limitations: Local guest rooms are not synced. A cloud save may fail while a local action succeeds; the UI reports that backup is pending rather than claiming successful sync. Repeated failed actions do not create new cloud rewards. Existing local rewards from name-only profiles are not automatically imported.

Verification performed: database RLS and all four owner-only policies confirmed through Supabase; test source and CI workflow committed. A real cross-device signed-in run and green CI evidence remain outstanding because the project has no confirmed login yet.

Next launch blocker: configure reliable email delivery and test signup verification on the actual deployed Streamlit site. Move session storage out of JavaScript-accessible browser storage before accepting live payments.
