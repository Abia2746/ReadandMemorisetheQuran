/**
 * RevenueCat Capacitor adapter (iOS/Android ONLY).
 * Web checkout uses the authenticated FastAPI/Stripe endpoint instead.
 * Never trust a client-side SDK status alone for server-side AI entitlements.
 */
import type { PlanTier, StorePrice } from "../components/billing/Paywall";

type StoreKind = "ios" | "android";
type TierPackages = Record<PlanTier, string>;

const ZERO_DECIMAL = new Set([
  "BIF", "CLP", "DJF", "GNF", "JPY", "KMF", "KRW",
  "MGA", "PYG", "RWF", "UGX", "VND", "VUV", "XAF", "XOF", "XPF",
]);

let configuredUser: string | null = null;

export async function initNativePurchases(
  userUuid: string,
  platform: StoreKind,
  publicApiKeys: { ios: string; android: string },
) {
  const key = publicApiKeys[platform]; // public SDK key, NEVER a secret API key
  if (!key || !/^[a-f0-9-]{36}$/i.test(userUuid)) {
    throw new Error("Sign in before using native subscriptions");
  }
  const { Purchases } = await import("@revenuecat/purchases-capacitor");
  if (configuredUser === null) {
    await Purchases.configure({ apiKey: key, appUserID: userUuid });
  } else if (configuredUser !== userUuid) {
    await Purchases.logIn({ appUserID: userUuid });
  }
  configuredUser = userUuid;
}

export async function getNativePlans(
  packageIdentifiers: TierPackages,
): Promise<StorePrice[]> {
  const { Purchases } = await import("@revenuecat/purchases-capacitor");
  const result = await Purchases.getOfferings();
  const packages = result.current?.availablePackages ?? [];
  const tiers: PlanTier[] = ["pro_monthly", "pro_annual", "family_annual"];

  return tiers.flatMap((tier) => {
    const found = packages.find((pkg) => pkg.identifier === packageIdentifiers[tier]);
    if (!found) return [];
    const currency = found.product.currencyCode;
    return [{
      tier,
      currency,
      amount_minor: Math.round(
        found.product.price * (ZERO_DECIMAL.has(currency.toUpperCase()) ? 1 : 100),
      ),
      interval: tier === "pro_monthly" ? "month" as const : "year" as const,
      // Introductory offer eligibility must be independently checked by the
      // store; do not promise a 7-day free trial to ineligible accounts.
      trial_available: false,
    }];
  });
}

export async function purchaseNativePlan(
  tier: PlanTier,
  packageIdentifiers: TierPackages,
  refreshServerEntitlements: () => Promise<unknown>,
) {
  const { Purchases } = await import("@revenuecat/purchases-capacitor");
  const offerings = await Purchases.getOfferings();
  const selected = offerings.current?.availablePackages.find(
    (pkg) => pkg.identifier === packageIdentifiers[tier],
  );
  if (!selected) throw new Error("That plan is not available in this app store.");
  await Purchases.purchasePackage({ aPackage: selected });
  // Store completion alone is not the authorization check for server AI.
  await refreshServerEntitlements();
}

export async function restoreNativePurchases(
  refreshServerEntitlements: () => Promise<unknown>,
) {
  const { Purchases } = await import("@revenuecat/purchases-capacitor");
  await Purchases.restorePurchases();
  await refreshServerEntitlements();
}
