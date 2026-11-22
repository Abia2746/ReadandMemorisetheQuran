# Al-Mu'allim Supabase Auth — connected project

The existing Supabase project **Al Mua’llim** is connected using its **public Project URL and publishable key** in `supabase_auth.py`. These values are intended for client access, unlike private database/Stripe credentials. You do not need to paste the public keys into Streamlit Secrets.

## What has been implemented
- An optional **Account & sign-in** section in Streamlit (free Qur'an reading needs no login).
- Supabase email-code sign-in flow and server-side token revalidation during app renders.
- Secure `public.learner_profiles` and `public.hifdh_progress` tables with owner-only RLS.
- Read-only-to-learners `public.billing_subscriptions` table, reserved for future verified Stripe webhook writes.
- Signed-in users can save their cloud profile name. A successful recitation review attempts to save a **reviewing** marker, not a claim that the verse is memorised.
- No paid entitlement is granted simply by logging in or returning from Stripe checkout.

## Required email setup in Supabase
Open project **Authentication → Providers → Email**, enable email sign-in. Under **Authentication → Email Templates → Magic Link**, ensure the email displays the confirmation token with `{{ .Token }}` so learners can type the code requested by the app. The default template may send only a link.

Test using an inbox you control. Default Supabase email sending has restrictions and rate limits; set up approved custom SMTP before a public rollout.

## Production work still needed
- Auth session refresh and durable session management.
- Google and Apple OAuth providers, configured redirects, and security review.
- Authenticated Stripe checkout creation with a mapped user ID.
- Verified webhook and durable payment state, subscription management portal.
- Server-side subscription entitlements; family-member policies and invitations.
- Actual full Hifdh history synchronisation (only revision markers currently sync).
- Mobile app store payment rules before releasing native apps.

Do not put any database password, Supabase secret/service-role key or Stripe secret key in GitHub.
