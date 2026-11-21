# Al-Mu'allim Stripe integration: sandbox setup

## Security first
The Stripe test secret was pasted into a chat. Rotate/revoke that test secret in Stripe Dashboard > Developers > API keys. Never commit or paste replacement secrets into code or chats.

## Streamlit Community Cloud
Open the deployed app > Manage app > Settings > Secrets. Enter the *new* test secret and three recurring Stripe test-mode Price IDs (create Products and recurring Prices in Stripe Dashboard while **Test mode** is enabled):

```toml
STRIPE_SECRET_KEY = "sk_test_REPLACE_IN_STREAMLIT_SECRETS"
STRIPE_PRICE_PRO_MONTHLY = "price_REPLACE_WITH_MONTHLY_TEST_PRICE"
STRIPE_PRICE_PRO_ANNUAL = "price_REPLACE_WITH_ANNUAL_TEST_PRICE"
STRIPE_PRICE_FAMILY_ANNUAL = "price_REPLACE_WITH_FAMILY_TEST_PRICE"
```

Prices: £5.99/month, £39.99/year, £69.99/year. The Free plan does not use Stripe Checkout.

## What is currently implemented
`stripe_checkout.py` creates Stripe-hosted **test-mode** subscription Checkout sessions, using configured recurring Price IDs. `streamlit_pricing.py` shows test checkout buttons only when all four secrets exist. Checkout return URLs do **not** imply payment verification or grant access. The current app is still a pricing preview and should not claim real subscriptions are active.

## Required before production
1. Establish secure user accounts with persistent, verified identities; a typed profile name is not authentication.
2. Deploy a public HTTPS webhook receiver on a suitable backend (e.g. FastAPI service), not a Streamlit page. Verify the Stripe-Signature with a separate webhook signing secret.
3. Handle `checkout.session.completed`, `customer.subscription.created`, `customer.subscription.updated`, `customer.subscription.deleted`, and `invoice.payment_failed`. Use durable, idempotent storage for customer/subscription/user mappings and entitlements.
4. Check entitlements on the server for premium features. Never grant access based on URL query parameters, local session state, or an unverified webhook.
5. Add a Stripe Billing Portal flow for managing/cancelling subscriptions, linked to authenticated customers.
6. Publish clear terms, privacy policy, cancellation/refund information, contact details and accurate feature availability; review UK and international VAT obligations and merchant-of-record choices.
7. Confirm Stripe eligibility and an appropriate adult account representative/guardian involvement for the under-18 founder.
8. Test renewals, failures, cancellation, duplicate/out-of-order webhooks, cross-device access, and family account permissions before live mode.
9. If launching native iOS/Android apps, assess Apple/Google digital-content billing rules separately.

The Stripe CLI and `stripe agent setup` must be run on a developer machine with the necessary environment; no Stripe implementation-planner MCP tool was available in this session.
