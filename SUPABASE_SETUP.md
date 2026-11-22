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

Streamlit keeps the verified session in memory for the current app session, refreshes short-lived tokens during normal app use, and calls Supabase logout on sign-out. **A complete browser reload, opening another browser, or clearing the Streamlit session may require signing in again.** For production add durable secure session management, ideally through an application authentication backend using secure HttpOnly cookies. Before public launch, test Safari, Gmail in-app browsers, and cross-device redirects.

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
