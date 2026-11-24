# Al-Mu'allim server-backed account foundation (Next.js website)

Status: implemented and configured in Vercel, **not yet confirmed by successful real email signup**.

## What changed
- Next.js website is now built in server mode rather than `output: export`.
- `POST /api/account` sends or verifies a Supabase email OTP; signout revokes the session best-effort.
- `GET /api/account` verifies the encrypted cookie with Supabase and renews expired tokens.
- `GET /auth/confirm?token_hash=...&type=email` verifies email links server-side.
- `/account/` displays email sign-in, a code-entry form, account status, and signout.
- Account tokens live in an AES-256-GCM encrypted, HttpOnly, SameSite=Lax cookie; no access or refresh tokens are deliberately exposed to client JavaScript. Auth endpoints are no-store, and browser mutation requests must have a same-origin Origin header.
- All pages that read Qur'an remain available to guests.

## Vercel configuration
Project: `al-muallim-safari-preview`. The following variable **names** are configured server-side (do not disclose their values):
- `SUPABASE_URL`: project API URL.
- `SUPABASE_PUBLISHABLE_KEY`: public client identifier.
- `AUTH_COOKIE_SECRET`: private 32+-character random secret; rotate deliberately because rotation signs everyone out.

## Supabase configuration required
- Set SMTP for reliable public email sending. Built-in email limits previously blocked confirmation.
- Update the Magic Link / Confirm Signup templates to show `{{ .Token }}` and optionally use a server-issued link:
  `<a href="https://YOUR_NEXTJS_DOMAIN/auth/confirm?token_hash={{ .TokenHash }}&type=email">Confirm your email</a>`
- Add the **exact Next.js production URL** to Authentication → URL Configuration. The previous Streamlit URL is a separate app; configuring one does not configure the other.
- Test a registered and confirmed learner, a returning login, an expired link, signout and revoked refresh token.

## Important deployment architecture limitations
- The existing Streamlit website has its own preview localStorage session. This new system **does not** replace or upgrade Streamlit authentication automatically.
- The separate FastAPI billing/learning endpoints still verify an existing OIDC provider's JWT, **not** the Next.js encrypted session cookie. Do not claim that new Next.js login automatically grants cloud study or paid API access. Their identity models must be unified and tested before production.
- This server-rendered Next.js site is not a Capacitor static export; native iOS/Android packaging requires a separate supported mobile build strategy.
- Do not publish or sell paid subscriptions until owner verification, entitlements, family seat boundaries, CSRF/session revocation tests and reliable transactional email are complete.

## Acceptance tests
- [ ] Vercel Next.js build succeeds with the server route handlers.
- [ ] On the deployed Next.js domain, `/api/account` returns signedOut over HTTPS without leaking secrets.
- [ ] Real email with a verification code arrives; code succeeds once and rejects replay.
- [ ] `am_secure_session` appears as Secure, HttpOnly, SameSite=Lax on HTTPS.
- [ ] Refresh and reopening the browser preserves the verified account on that same browser.
- [ ] Logout clears the cookie and invalidates the Supabase session where possible.
- [ ] Cross-origin POSTs are rejected and unauthenticated GETs disclose no private learner data.
- [ ] Login cannot activate Stripe Sandbox or live premium without separate, server-verified billing status.
- [ ] Migrate authenticated FastAPI learner APIs and native app sessions to one identity system before broad launch.