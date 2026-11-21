# Al-Mu'allim — ethical billing integration and launch runbook

**Status:** source-code foundation implemented; payment provider accounts, price catalog,
production secrets, live purchase tests, store review, cache load tests, and security audit
are **not** configured or certified. The Streamlit production app is not replaced by this
module. No actual subscription charges are enabled by these files alone.

## 1. Guarantees

- Zero advertising SDKs, banner slots, tracking pixels or ad monetization.
- Uthmani Qur'an text, translations, Qari audio, basic word following,
  one active Hifz plan, calendar export and base Window Lounge are free.
- Paid purchases unlock optional advanced AI study, corrections and sanctuaries.
- Never revoke separate legitimate subscriptions because one provider expires.
- No timer, coercion, guilt, fabricated scarcity, or fake 'limited availability'.
- A free user may open **3 distinct Verse Studio lessons per local day**;
  opening the same verse's Tafsir/drills repeatedly counts only once that day.
- A free user may send **5 AI teacher questions per local day**. Failed provider
  responses refund the quota. A verified IANA timezone is set before first usage.
- Pro AI access is unlimited for ordinary learning, with anti-bot burst protection;
  do not advertise an undisclosed daily paid cap.

## 2. Repository files

- `apps/api/schema.sql`: tables for users, subscriptions, families, invite codes,
  Stripe/RevenueCat price catalog, daily quotas, grants, paid sponsorship ledger,
  AI cache, webhook deduplication and queued reconciliation.
- `apps/api/app/services/billing.py`: feature matrix, `@require_entitlement`,
  paid family verification, atomic quota counters and refunds.
- `apps/api/app/services/verse_cache.py`: read-through Redis lock and
  PostgreSQL JSONB cache with versioned source hashes.
- `apps/api/app/routers/billing.py`: auth, access status, prices, region,
  Stripe Checkout, family links and paid scholarship allocations.
- `apps/api/app/routers/billing_webhooks.py`: Stripe signatures, RevenueCat HMAC,
  original transaction IDs, event idempotency, Stripe API authoritative status.
- `apps/api/app/routers/verse.py`: separate metered Verse Studio endpoints and
  optional AI teacher/approved FAQ routing.
- `apps/api/app/services/verse_generation.py`: authenticated Quran Foundation
  text/translation access, allowlisted Tafsir sources and schema-checked model JSON.
- `apps/web/components/billing/Paywall.tsx`: bottom sheet with annual selected,
  regional prices, close/free path, optional trial reminder and scholarship link.
- `apps/web/components/billing/ScholarshipRequest.tsx`: sponsored access requests.
- `apps/web/lib/nativeBilling.ts`: RevenueCat Capacitor bridge for store IAP.
- `apps/web/lib/billingApi.ts`: authenticated web checkout client.

## 3. Running the API

```bash
# In a secured PostgreSQL 15+ database (never run schema scripts in the browser):
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f apps/api/schema.sql

# Use a virtualenv, from the project root:
pip install -r apps/api/requirements.txt

# Set environment secrets in deployment host, not GitHub commits:
# copy apps/api/.env.example into your secret manager and supply real values.
PYTHONPATH=apps/api uvicorn app.main:app --host 127.0.0.1 --port 8000
PYTHONPATH=apps/api pytest -q apps/api/tests
```

API health: `GET /health`.

Authentication: configure a real OIDC issuer, audience, HTTPS JWKS and
short-lived bearer tokens. The backend derives user IDs from verified token
claims. Do not ship a client-supplied `user_id` bypass.

## 4. Stripe Web / PWA

Create separate Price IDs for each plan and locale. Price IDs in
`billing_price_catalog` must be from your own account and `enabled=TRUE`
only after verifying real amount/currency/recurrence and tax handling. Never
use prices supplied by a browser request as the charged product. Checkout
returns a Stripe-hosted HTTPS URL.

Proposed prices — planning only, not configured:

| Region | Monthly | Annual | Family annual |
| --- | --- | --- | --- |
| United Kingdom | £5.99 | £39.99 | £69.99 |
| United States | $6.99 | $44.99 | $79.99 |
| Euro markets | €6.99 | €44.99 | €79.99 |

Example price insert **after** creating a matching Stripe Price in test mode
(replace every placeholder, confirm amount and currency, and keep disabled
until reviewed):

```sql
INSERT INTO billing_price_catalog
  (provider,provider_price_or_product_id,country_code,currency,
   amount_minor,tier,trial_days,enabled)
VALUES
  ('stripe','REPLACE_WITH_YOUR_STRIPE_PRICE_ID','GB','GBP',
   3999,'pro_annual',7,FALSE);
```

Required webhook events:

- `checkout.session.completed`
- `checkout.session.async_payment_succeeded`
- `customer.subscription.created`, `updated`, `deleted`
- `invoice.paid`, `invoice.payment_failed`

Webhook destination: `POST https://YOUR_API/api/webhooks/stripe`.
Set endpoint-specific `STRIPE_WEBHOOK_SECRET`.
Use Stripe test clock, late events, trial cancellations, failed payments,
refunds, duplicate events, and prod-vs-test mode checks before launch.

**Trial eligibility:** Only first-time eligible Pro Annual users. A one-hour
trial reservation prevents parallel sessions, and the Checkout Session has the
same expiry. The database records redeemed trials from verified Stripe/RC
events. Trial claims from stores remain subject to native store eligibility.

## 5. RevenueCat / native App Store and Google Play

Create products and entitlement mappings in App Store Connect and Play Console.
In RevenueCat, configure per-store Offerings and package identifiers for
`pro_monthly`, `pro_annual`, `family_annual`. Set the
`@revenuecat/purchases-capacitor` public SDK keys in the native frontend.
Login with the verified account UUID as the RevenueCat App User ID. Display
the actual store-provided local prices and restore purchases.

Do not place a Stripe Checkout button inside the standard native IAP flow;
alternative-payment rules depend on storefront, terms and eligibility.

Webhook: `POST https://YOUR_API/api/webhooks/revenuecat`. Enable **HMAC
signing** in RevenueCat and save the secret. The handler checks the
`X-RevenueCat-Webhook-Signature: t=...,v1=...` signature over
`timestamp + '.' + raw HTTP body` and rejects timestamps more than five
minutes old. Optional Authorization token adds defence in depth.

The handler currently processes native `APP_STORE`/`PLAY_STORE` purchases.
It deliberately ignores RevenueCat `STRIPE`/`RC_BILLING` web purchases
because direct Stripe is the authoritative web billing channel in this design.

**Open launch blocker:** a RevenueCat transfer needs reconciliation with
the RevenueCat Subscribers API for both former and new owners. Transfer
events are placed in `billing_reconciliation_queue`; do not promise instant
cross-account transfers until that worker and tests are operational.

## 6. Regional purchasing power (PPP)

App Store / Play store product price tiers are configured in their own consoles.
RevenueCat reflects those prices; it cannot remotely enroll you in Apple's Small
Business Program or programmatically guarantee a 15% fee. Apple requires
application/approval; Google Play subscription fees depend on current terms.

For web Stripe, add real country-scoped `billing_price_catalog` entries and
verify the purchaser's billing country before applying a discount. Country
codes, VPNs and UI currencies alone are not sufficient proof. **Do not set
PPP prices from a spoofable client-provided country.** The example region file
`apps/api/config/market-pricing.json` is planning metadata only.

Proposed PPP review markets: ID, MY, PK, EG, IN, NG, TR. Price proposals
equivalent to ~£2.49/month and ~£16.99/year require actual local store price
points, supported currencies and regional tax checks; they are NOT automatic
in the current module. RevenueCat Billing lists India-specific limitations,
and direct Stripe eligibility is country-dependent.

## 7. Free scholarships and gifts

A user can request 3 or 6 months of access without income evidence. A web
gift checkout records a £39.99 payment only after signed Stripe confirmation.
One paid gift funds no more than 12 months in allocated 3- or 6-month grants.

A separately authorised billing administrator approves a pending request via
`POST /api/billing/admin/scholarships/approve` using an allowlist of verified
OIDC subjects configured in `BILLING_ADMIN_SUBJECTS`. Gifts are not automatically
matched and don't create tax-deductible charitable donations unless an eligible
registered organisation explicitly provides that status.

`request_status='approved'` activates `pro_annual` entitlement for its own
expiry window. Sponsored access never reveals the student's financial situation
to donors. Review refunds and withdrawals of paid gifts before refunding
associated scholarships.

## 8. Two-day trial reminder

Annual trial copy shows a guaranteed two-day reminder **only when**
the reminder service is actually operating and `trialReminderEnabled=true`.
The scheduler is opt-in and uses verified email:
`POST /api/billing/trial-reminders` with
`{"email_reminders":true}`.

Worker: `PYTHONPATH=apps/api python -m app.jobs.trial_reminders`.
Configure a secure SMTP provider, `TRIAL_REMINDER_JOB_ENABLED=true` and
run it on a monitored 15-minute cron. The worker searches upcoming trial
expiries, sends a factual email, and writes idempotent delivery records.

**Until email delivery and cron are verified, keep**
`trialReminderEnabled=false`; do not claim reminders have been sent.
Native store renewal notices are also under app-store policies.

## 9. Cache and unit economics

Each verse is generated independently by
`GET /api/verse/{surah}/{ayah}/tafsir` and
`GET /api/verse/{surah}/{ayah}/study-drills`.
Source digest + model + schema/prompt version + translation edition + language
form the cache version. Redis locking prevents simultaneous model calls for
the same uncached entry, and PostgreSQL JSONB stores validated results.

**Important:** a first miss still incurs AI cost; subsequent published
cache hits incur **zero new language-model inference** but not zero hosting,
database or bandwidth costs. Cache response times below 50ms are a *target*,
not a tested guarantee. CDN placement, regional DB latency and instrumentation
will determine reality. `automated_pass` means schema/audit checks passed,
NOT independent scholarly verification. `scholar_reviewed` is separate.

At 15% App Store commission and ignoring taxes, £39.99/year leaves
about £33.99 after platform fees. On a monthly equivalent this is about
£2.83 *before all other costs*. Therefore an 85% margin on gross consumer
price is not credible for a 15%-fee transaction with any operating costs.
Instead target **85% contribution margin on net receipts** and monitor:

```text
contribution_margin = (net_receipts - ai_inference - database - hosting
                       - app_licensing - support - refunds) / net_receipts
```

Set alerts on paid Q&A cost/member, cache miss ratio, first-request latency,
p95/p99 API response time, spending per LLM model and refunds. No user-funded
premium promise may rely on an undisclosed hard quota.

## 10. Production gates

1. Verify ownership/age requirements: Stripe and developer programme
   accounts must belong to someone legally eligible to enter merchant
   agreements. If the builder is under 18, a legally eligible adult must
   manage contracts where the provider requires it. Do not bypass ID checks.
2. Configure legal entities, privacy notice, cancellation, tax/VAT,
   subscription terms, app-store disclosures and refund policy.
3. Test Stripe signed webhooks and RevenueCat HMAC in sandbox and production
   isolation; replay out-of-order events. Never allow test receipts to
   provide production Pro access.
4. Complete the RevenueCat transfer/reconciliation worker and refunds.
5. Connect real Next.js and Capacitor app shells; test focus, keyboard,
   screen reader, UK VAT, multiple currencies and failed checkout.
6. Verify the trial reminder sender and monitoring before displaying the promise.
7. Prewarm and academically review frequently requested verse content;
   reject unsupported attributions, verify Arabic roots and translations.
8. Configure rate limits, abuse logs without message contents, retention,
   backups, support workflows, observability, and on-call alerts.
9. Publish the free Qur'an routes even when billing services are unavailable.
10. Receive a security, compliance and scholarly review before launch.

### Primary documentation checked 21 November 2026

- RevenueCat webhook HMAC: https://www.revenuecat.com/docs/integrations/webhooks
- RevenueCat event types: https://www.revenuecat.com/docs/integrations/webhooks/event-types-and-fields
- RevenueCat Capacitor: https://www.revenuecat.com/docs/getting-started/installation/capacitor
- Apple Small Business Program: https://developer.apple.com/app-store/small-business-program/
- Google Play fees: https://support.google.com/googleplay/android-developer/answer/112622
- Stripe subscription-period API update:
  https://docs.stripe.com/changelog/basil/2025-03-31/deprecate-subscription-current-period-start-and-end
- Quran Foundation API:
  https://api-docs.quran.com/docs/content_apis_versioned/4.0.0/verses-by-verse-key/
