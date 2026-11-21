/**
 * Authenticated billing API client. No card fields, ad tracking, or credentials
 * are stored in the browser. An OIDC session supplies a short-lived bearer
 * token; purchases are authorized only after signed server-side reconciliation.
 */
import type { PlanTier, StorePrice } from "../components/billing/Paywall";

export type GetAccessToken = () => Promise<string>;
export type BillingStatus = {
  user_id: string;
  tier: "free" | PlanTier;
  access_via: string;
  features: string[];
  expires_at: string | null;
  daily_usage: {
    date: string;
    timezone: string;
    verse_studio: { used: number; limit: number };
    teacher_qna: { used: number; limit: number };
  };
};

async function requestJSON<T>(
  apiOrigin: string,
  tokenProvider: GetAccessToken,
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const token = await tokenProvider();
  const response = await fetch(new URL(path, apiOrigin).toString(), {
    ...init,
    headers: {
      "Content-Type": "application/json",
      "Authorization": "Bearer " + token,
      ...init.headers,
    },
    credentials: "omit",
    cache: "no-store",
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    const error = new Error(
      payload?.detail?.message ?? payload?.detail ??
      "The request could not be completed",
    ) as Error & { status?: number; code?: string };
    error.status = response.status;
    error.code = payload?.detail?.code;
    throw error;
  }
  return response.json() as Promise<T>;
}

export function makeBillingApi(apiOrigin: string, getAccessToken: GetAccessToken) {
  return {
    me: () =>
      requestJSON<BillingStatus>(apiOrigin, getAccessToken, "/api/billing/me"),
    prices: () =>
      requestJSON<{ country: string; plans: StorePrice[] }>(
        apiOrigin, getAccessToken, "/api/billing/prices"
      ),
    subscribe: async (tier: PlanTier) => {
      const data = await requestJSON<{
        checkout_url: string; trial_available: boolean;
      }>(apiOrigin, getAccessToken, "/api/billing/checkout", {
        method: "POST",
        body: JSON.stringify({ tier, request_id: crypto.randomUUID() }),
      });
      const url = new URL(data.checkout_url);
      if (url.protocol !== "https:" ||
          !["checkout.stripe.com", "billing.stripe.com"].includes(url.hostname)) {
        throw new Error("Checkout returned an unexpected destination");
      }
      window.location.assign(url.toString());
    },
    requestScholarship: (months: 3 | 6, note: string | null) =>
      requestJSON<{ status: string; message: string }>(
        apiOrigin, getAccessToken, "/api/billing/scholarships/requests", {
          method: "POST", body: JSON.stringify({ months, note }),
        },
      ),
    sponsorYear: async () => {
      const data = await requestJSON<{ checkout_url: string }>(
        apiOrigin, getAccessToken, "/api/billing/scholarships/gift-checkout",
        { method: "POST", body: "{}" },
      );
      const url = new URL(data.checkout_url);
      if (url.protocol !== "https:" || url.hostname !== "checkout.stripe.com") {
        throw new Error("Sponsorship checkout returned an unexpected destination");
      }
      window.location.assign(url.toString());
    },
    setTimezoneOnce: (iana_timezone: string) =>
      requestJSON<{ timezone: string; daily_reset: string }>(
        apiOrigin, getAccessToken, "/api/billing/timezone", {
          method: "POST", body: JSON.stringify({ iana_timezone }),
        },
      ),
    setTrialReminderPreference: (email_reminders: boolean) =>
      requestJSON<{ email_reminders: boolean }>(
        apiOrigin, getAccessToken, "/api/billing/trial-reminders", {
          method: "POST", body: JSON.stringify({ email_reminders }),
        },
      ),
  };
}

export function isQuotaPaywallError(error: unknown, type: "verse" | "teacher"): boolean {
  if (!error || typeof error !== "object") return false;
  const e = error as { status?: number; code?: string };
  return e.status === 403 && e.code === (
    type === "verse" ? "verse_limit_reached" : "teacher_daily_limit_reached"
  );
}
