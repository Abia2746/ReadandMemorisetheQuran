# Al-Mu'allim Supabase Auth — connected project

The existing Supabase project **Al Mua’llim** is connected using its **public Project URL and publishable key** in `supabase_auth.py`. These values are intended for client access, unlike private database/Stripe credentials. You do not need to paste the public keys into Streamlit Secrets.

## What has been implemented
- An optional **Account & sign-in** section in Streamlit (free Qur'an reading needs no login).
- Supabase email-code sign-in flow and server-side token revalidation during app renders.
- Secure `public.learner_profiles` and `public.hifdh_progress` tables with owner-only RLS.
- Read-only-to-learners `public.billing_subscriptions` table, reserved for future verified Stripe webhook writes.
- Signed-in users can save their cloud profile name. A successful recitation review attempts to save a **reviewing** marker, not a claim that the verse is memorised.
- No paid entitlement is granted simply by logging in or returning from Stripe checkout.

## Testing sign-in with the default Supabase email service

A custom SMTP provider is **not necessary for this initial test**. The Streamlit preview now supports the default **Magic Link** email. In the app's **Account & sign-in** panel:

1. Enter your email and click **Email me a sign-in link**.
2. Open your inbox, **copy the link address without opening the link**, and paste it into the app's masked **Paste your private sign-in link** field.
3. Click **Sign in securely**. The backend validates the link against this exact Supabase project's Auth endpoint and checks the resulting account with Supabase.
4. If you already clicked the original link, it may have been consumed; request another.

Why this temporary step? Supabase's default magic-link flow redirects with tokens in the browser URL fragment, which the Streamlit Python backend cannot safely read. Pasting an unclicked, single-use link into a masked Streamlit input is a temporary **test-only** workaround. Before releasing the app to the public, implement a conventional client-side magic-link callback or a PKCE flow; do not ask real customers to paste authentication links.

Default Supabase email sending has limits and may restrict recipient addresses. For production, configure an approved email sender, callback URLs, and email templates.

## Production work still needed
- Auth session refresh and durable session management.
- Google and Apple OAuth providers, configured redirects, and security review.
- Authenticated Stripe checkout creation with a mapped user ID.
- Verified webhook and durable payment state, subscription management portal.
- Server-side subscription entitlements; family-member policies and invitations.
- Actual full Hifdh history synchronisation (only revision markers currently sync).
- Mobile app store payment rules before releasing native apps.

Do not put any database password, Supabase secret/service-role key or Stripe secret key in GitHub.
