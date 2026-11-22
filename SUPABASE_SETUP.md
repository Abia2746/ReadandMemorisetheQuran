# Al-Mu'allim Supabase Auth — setup

The Streamlit reader now includes an optional **Account & sign-in** section. It does **not** unlock paid features. The email-code UI only appears after Supabase credentials are supplied.

1. Create a Supabase project at https://supabase.com/dashboard.
2. Open **Project Settings → API** (or the project's Connect/API keys screen). Copy the **Project URL** and the **anon/publishable key**. Never use a service-role or secret key in this client-facing integration.
3. In Supabase **Authentication → Providers → Email**, enable email OTP/sign-in.
4. In **Authentication → Email Templates → Magic Link**, configure the email to show the six-digit OTP using `{{ .Token }}` rather than only a confirmation URL. Without this template change, the UI asking for a code will not work.
5. In **Streamlit Community Cloud → app → Settings → Secrets**, append:

```toml
SUPABASE_URL = "https://YOUR_PROJECT.supabase.co"
SUPABASE_ANON_KEY = "YOUR_SUPABASE_PUBLISHABLE_OR_ANON_KEY"
```

6. Restart Streamlit and test sign-in using an inbox you control. Configure Supabase email sending limits / custom SMTP before inviting users.

**Security and limitations**

- This is an initial Streamlit session-based email OTP preview. A browser refresh or session reset may require signing in again.
- Do not store the Supabase service-role key in the app. Never commit any credentials.
- Google and Apple OAuth are not yet implemented; they require provider configuration and secure callback handling.
- Stripe Checkout is currently test-mode only. Its success redirect is not proof of payment, and no premium entitlements are granted.
- Production needs a durable backend and database, authenticated checkout creation tied to Supabase user ID, verified Stripe webhooks, customer portal, server-side access checks, subscription cancellation handling, and family membership enforcement.
- For native iOS and Android digital subscriptions, review App Store and Google Play billing requirements.
