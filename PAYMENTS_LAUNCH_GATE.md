# Al-Mu'allim — Product & Payment Launch Gate

**Status: SANDBOX DEVELOPMENT. Do not accept real charges yet.**

## Product principles
1. The Qur'an itself remains free to read and listen to.
2. Sell only capabilities that exist, work reliably, and are accurately described.
3. Every paid action requires a verified user account and a durable billing record.
4. Access comes from Stripe signature-verified subscription state — never redirect parameters, display names, or payment UI success text.
5. Subscription cancellation and recovery must work before accepting live payments.
6. Protect learner and family data with Row Level Security and explicit permission tests.
7. Mobile experiences should be accessible, fast and responsive; never promise AI Tajweed certainty the implementation cannot deliver.
8. Build for family privacy and child safeguarding before enabling shared membership.

## Implemented in this repository
- Four visible tiers: Free, Pro Monthly (£5.99), Pro Annual (£39.99), Family Annual (£69.99).
- Pricing page explicitly explains that premium features are under development and checkout is Sandbox-only.
- Sandbox Checkout requires an authenticated Supabase account; user identity is independently verified against Supabase Auth.
- Checkout sends an authenticated Supabase UUID in Stripe client reference and subscription metadata.
- Supabase Edge Function `stripe-sandbox-webhook` is deployed but FAILS CLOSED until its private secrets are configured.
- Webhook checks Stripe signature, request freshness, Sandbox-only mode, then fetches latest subscription data directly from Stripe before writing.
- Only signed-in owners may read their subscription rows; only the server/service role can write them.
- Test-only membership display and billing-portal helper are implemented. No paid features are unlocked yet.

## Sandbox webhook configuration (required before testing)
In **Supabase → Edge Functions → Secrets**, configure:

- `STRIPE_API_KEY`: new private Stripe **Sandbox** secret key (`sk_test_...`)
- `STRIPE_WEBHOOK_SIGNING_SECRET`: the **Sandbox** webhook signing secret (`whsec_...`)
- `SUPABASE_SERVICE_ROLE_KEY`: Supabase's secret service-role key, available privately to server-side functions (usually provided by Supabase; verify in function secrets)
- `SUPABASE_URL`: the project URL (usually provided by Supabase)

Never place private keys in GitHub, browser code, or chat. The Stripe secret previously shared in conversation should be rotated before any launch or wider testing.

In **Stripe Sandbox → Developers → Webhooks** add the webhook receiver:
```
https://edkqwqepnlidenxyveoj.supabase.co/functions/v1/stripe-sandbox-webhook
```
Events: `checkout.session.completed`, `customer.subscription.created`, `customer.subscription.updated`, `customer.subscription.deleted`.

The function intentionally returns HTTP 503 until the private Sandbox secrets exist. Only after signature verification may it update billing records. Configure and test the Stripe **Customer portal** in the same Sandbox.

## Mandatory acceptance tests before even considering live mode
- [ ] Confirm sign-up and returning email-link login work from Safari, Chrome and an email app.
- [ ] Returning login persists securely using appropriate browser/session handling.
- [ ] Free users have no access to paid-only capabilities.
- [ ] Each new checkout links to exactly one verified Supabase account.
- [ ] Success URLs cannot grant membership themselves.
- [ ] Verified webhook activates the corresponding Sandbox membership.
- [ ] Failed payment, cancellation, expiration and renewal correctly change membership.
- [ ] Duplicate and out-of-order webhook events never grant incorrect access.
- [ ] Stripe portal allows customers to review, cancel and update payment details.
- [ ] No learner can read, change, or create another learner's billing status.
- [ ] Family memberships enforce actual household seat limits and privacy.
- [ ] Users can export/delete their learning data, subject to retention obligations.
- [ ] Terms, Privacy Notice, refund/cancellation policies, and support contacts are published.
- [ ] Accessibility, performance, login recovery, and data-backup tests pass.
- [ ] All listed paid features are actually available and demonstrably functional.
- [ ] Mobile app payment compliance is assessed separately for iOS/Android.

## Live merchant payouts: separate, adult-verified Stripe process
Stripe's UK support states that users under 18 need a legal guardian to assume account ownership **before accepting charges or receiving transfers**. The guardian must use genuine information and complete any Stripe verification required. Do not bypass age or identity rules.

When the account is eligible:
1. Complete Stripe's **live account activation**, real business/owner identification and bank account verification **inside the Stripe Dashboard**.
2. Set up live products/prices (Sandbox IDs are not live Price IDs), eligible tax categories, tax handling, refund support, and any necessary consumer disclosures.
3. Configure a separately verified live webhook and credentials. Do **not** reuse the test-only Edge Function for live money.
4. Complete an independent end-to-end live-billing security review. Never turn on live Checkout solely because a test payment succeeded.
5. Check Apple App Store and Google Play billing requirements before selling digital subscriptions inside native apps.

## Current unresolved limitations
- Supabase account has not yet demonstrated an email-confirmed sign-in in end-to-end testing.
- Supabase's built-in SMTP reached rate limits; a suitable email service is required for reliable public signup.
- Session persistence across browser restarts is not yet production grade.
- No end-to-end verified webhook ingestion has been tested because signing credentials aren't configured.
- No live financial processing, premium feature gating, family seats, or real automatic payouts are enabled.
- Managed Payments / merchant-of-record terms in the Stripe account must be reviewed before choosing live billing architecture.
