# Al-Mu'allim — Email verification code setup

The Streamlit account dialog now supports a numeric code alongside the existing link. **The code feature will not work until the Supabase template actually emails the OTP.** Keep all credentials inside Supabase, and do not disable confirmation.

## Step 1 — Email provider
Configure and verify a transactional SMTP provider in Supabase Dashboard → Authentication → SMTP Settings. The built-in limited mail service is unsuitable for public signups. Do not paste SMTP credentials into GitHub or chat.

## Step 2 — Approved app URL
In Authentication → URL Configuration, configure the Site URL as:

https://readandmemorisethequran-9uvtv8lpn9ozytdqtk6ceh.streamlit.app/

Include the same URL in allowed redirects. Check that localhost:3000 is not used as the main redirect.

## Step 3 — Email templates
In Authentication → Email Templates, **retain the confirmation link** and add the six-digit code to both **Magic Link** and **Confirm signup** templates. Example HTML body (edit brand/design before launch):

```html
<!doctype html>
<html>
  <body style="margin:0;padding:24px;background:#f5f1e8;color:#163b2e;font-family:Arial,sans-serif">
    <main style="max-width:480px;margin:auto;padding:32px;border:1px solid #dcc99e;border-radius:16px;background:#fffdf9">
      <p style="letter-spacing:2px;font-size:12px;color:#9e7842">AL-MU'ALLIM</p>
      <h1 style="font-size:26px;margin-bottom:10px">Your Qur'an journey awaits</h1>
      <p>Enter this one-time code in Al-Mu'allim to confirm your email:</p>
      <p style="font-size:34px;font-weight:bold;letter-spacing:8px">{{ .Token }}</p>
      <p>Or use the secure confirmation link:</p>
      <p><a href="{{ .ConfirmationURL }}" style="color:#1a6047">Confirm email or sign in</a></p>
      <p style="font-size:12px;color:#555">Didn't request this? You can safely ignore this email. Never share the code.</p>
    </main>
  </body>
</html>
```

Supabase docs: https://supabase.com/docs/guides/auth/auth-email-templates and https://supabase.com/docs/guides/auth/auth-email-passwordless

**Safety:** An email code must be entered into Al-Mu'allim (not sent to anyone else). Codes expire, are one-use, and Supabase enforces their validity. The local Streamlit preview also limits code attempts; this is not a substitute for server-side anti-abuse protections.

## Step 4 — End-to-end verification
1. Request a single fresh email link using the correct account mode.
2. Check that the email displays the code and link. Use one of them, not both.
3. If using the code, enter it in the app. The app validates it through Supabase and separately checks the returned user identity.
4. Confirm the correct account appears, then refresh and reopen Safari.
5. Sign out and confirm the saved session is cleared.
6. Test a second account, expired code, changed email and Supabase outage.
7. Verify cloud profile, Hifdh plan and Prayer Room isolation after sign-in.

**Do not enable live payments until the secure-cookie production auth migration and these checks have passed.** The existing Streamlit browser localStorage is still only a preview mechanism.
