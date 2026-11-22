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

## Test the proper one-tap magic-link sign-in

1. Open Al-Mu'allim and select **Account & sign-in**.
2. Enter your email and press **Email me a sign-in link**.
3. Open the Supabase email and **tap the sign-in link normally**.
4. Supabase verifies the link and redirects back to the app. A small Streamlit Components v2 callback reads the URL fragment, removes sensitive tokens from the browser URL, and sends them to the backend.
5. The backend calls Supabase Auth to verify the identity before treating the user as signed in.

No copying or pasting of sign-in links is required. The link is one-time use. Older links sent before the redirect configuration was changed may point to the wrong URL; request a fresh one.

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
