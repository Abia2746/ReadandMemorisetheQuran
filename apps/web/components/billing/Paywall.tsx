"use client";

/**
 * Al-Mu'allim paywall. Never rendered automatically: the parent opens it only
 * after a user taps a contextual premium action or hits a metered limit.
 * Prices must come from verified Stripe catalog or RevenueCat Store offerings.
 * This view does not process money, collect cards, or use advertising SDKs.
 */
import { useEffect, useMemo, useRef, useState, type KeyboardEvent } from "react";

export type PlanTier = "pro_monthly" | "pro_annual" | "family_annual";
export type PaywallReason =
  | { kind: "manual" }
  | { kind: "verse_limit" }
  | { kind: "recitation_preview"; count: number; verseReference: string }
  | { kind: "sanctuary_preview"; theme: string };

export type StorePrice = {
  tier: PlanTier;
  currency: string;        // ISO 4217
  amount_minor: number;    // Stripe / native smallest currency unit
  interval: "month" | "year";
  trial_available: boolean; // from authenticated eligibility check, not static catalog
};

type Props = {
  open: boolean;
  reason: PaywallReason;
  prices: StorePrice[]; // do not invent a fallback price if a region is unavailable
  platform: "web" | "ios" | "android";
  trialReminderEnabled?: boolean; // true ONLY after a verified reminder service exists
  onClose: () => void;
  onCheckout: (tier: PlanTier) => Promise<void>;
  onRestorePurchases?: () => Promise<void>;
  onScholarship: () => void;
};

const zeroDecimal = new Set([
  "BIF", "CLP", "DJF", "GNF", "JPY", "KMF", "KRW",
  "MGA", "PYG", "RWF", "UGX", "VND", "VUV",
  "XAF", "XOF", "XPF",
]);

const amountMajor = (minor: number, currency: string) =>
  minor / (zeroDecimal.has(currency.toUpperCase()) ? 1 : 100);

const formatPrice = (minor: number, currency: string) => {
  const major = amountMajor(minor, currency);
  try {
    return new Intl.NumberFormat(undefined, {
      style: "currency",
      currency: currency.toUpperCase(),
      maximumFractionDigits: zeroDecimal.has(currency.toUpperCase()) ? 0 : 2,
    }).format(major);
  } catch {
    return `${currency.toUpperCase()} ${major.toFixed(2)}`;
  }
};

const labels: Record<PlanTier, string> = {
  pro_monthly: "Monthly",
  pro_annual: "Annual",
  family_annual: "Family",
};

function contextLine(reason: PaywallReason): string {
  switch (reason.kind) {
    case "verse_limit":
      return "You've completed your 3 free deep-study lessons today. Your free lessons renew tomorrow.";
    case "recitation_preview":
      return reason.count > 0
        ? `You have ${reason.count} words to review in ${reason.verseReference}. Precision practice is available with Pro.`
        : "Review individual words and practise difficult phrases with Pro.";
    case "sanctuary_preview":
      return `You can preview ${reason.theme} before choosing a Pro plan.`;
    default:
      return "Continue learning with additional study tools, at your own pace.";
  }
}

export function AlMuallimPaywall({
  open, reason, prices, platform, trialReminderEnabled = false,
  onClose, onCheckout, onRestorePurchases, onScholarship,
}: Props) {
  const [selected, setSelected] = useState<PlanTier>("pro_annual");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const closeRef = useRef<HTMLButtonElement>(null);
  const sheetRef = useRef<HTMLDivElement>(null);
  const lastFocused = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!open) return;
    lastFocused.current = document.activeElement as HTMLElement;
    setSelected("pro_annual");
    setError("");
    requestAnimationFrame(() => closeRef.current?.focus());
    const escape = (event: globalThis.KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", escape);
    const oldOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", escape);
      document.body.style.overflow = oldOverflow;
      lastFocused.current?.focus();
    };
  }, [open, onClose]);

  const offered = useMemo(
    () => Object.fromEntries(prices.map((p) => [p.tier, p])) as Partial<Record<PlanTier, StorePrice>>,
    [prices],
  );
  const monthly = offered.pro_monthly;
  const annual = offered.pro_annual;
  const savings = monthly && annual && monthly.currency === annual.currency
    ? Math.max(0, Math.round((1 - annual.amount_minor / (monthly.amount_minor * 12)) * 100))
    : null;

  if (!open) return null;
  const active = offered[selected];
  const freeRemains = "Full Qur'an, translations, Qari audio, basic follow-along and one Noor plan stay free forever.";

  const buy = async () => {
    if (!active || busy) return;
    setBusy(true);
    setError("");
    try {
      await onCheckout(selected);
      // Let the host navigate to verified checkout / store receipt.
    } catch {
      setError("The purchase couldn't start. No subscription has been changed.");
    } finally {
      setBusy(false);
    }
  };
  const restore = async () => {
    if (!onRestorePurchases) return;
    setError("");
    try {
      await onRestorePurchases();
    } catch {
      setError("We couldn't check purchases right now. Please try again later.");
    }
  };
  const trapFocus = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key !== "Tab") return;
    const elements = sheetRef.current?.querySelectorAll<HTMLElement>(
      'button:not([disabled]),a[href],input:not([disabled]),[tabindex="0"]'
    );
    if (!elements?.length) return;
    const first = elements[0];
    const last = elements[elements.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault(); last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault(); first.focus();
    }
  };

  return (
    <div
      className="fixed inset-0 z-[120] flex items-end justify-center bg-black/75 p-0 backdrop-blur-sm sm:items-center sm:p-5"
      onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}
    >
      <div
        ref={sheetRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="am-paywall-title"
        aria-describedby="am-paywall-desc"
        onKeyDown={trapFocus}
        className="max-h-[94dvh] w-full overflow-y-auto rounded-t-[28px] border border-[#4A3828] bg-[#1A120D] p-5 text-[#F5EBE0] shadow-2xl sm:max-w-[540px] sm:rounded-[28px] sm:p-7"
      >
        <div className="mb-5 flex items-start justify-between gap-4">
          <div>
            <div className="mb-2 text-xs font-semibold tracking-[0.2em] text-[#C8A96E] uppercase">
              Al-Mu'allim Pro
            </div>
            <h2 id="am-paywall-title" className="font-editorial text-2xl leading-tight text-[#F5EBE0] sm:text-3xl">
              More ways to learn, at your own pace
            </h2>
          </div>
          <button
            ref={closeRef}
            type="button"
            onClick={onClose}
            className="min-h-11 min-w-11 rounded-full border border-[#4A3828] bg-[#2A1F18] text-xl text-[#E6D5B8] focus-visible:outline-2 focus-visible:outline-[#D4AF37]"
            aria-label="Close subscription options"
          >
            ×
          </button>
        </div>

        <p id="am-paywall-desc" className="mb-4 text-sm leading-relaxed text-[#E6D5B8]">
          {contextLine(reason)}
        </p>
        <div className="mb-5 rounded-xl border border-[#C8A96E]/30 bg-[#2A1F18] p-3 text-xs leading-relaxed text-[#E6D5B8]">
          {freeRemains}
        </div>

        <div aria-label="Choose subscription" role="group" className="grid grid-cols-3 gap-2">
          {(["pro_monthly", "pro_annual", "family_annual"] as PlanTier[]).map((tier) => {
            const plan = offered[tier];
            const isSelected = selected === tier;
            return (
              <button
                key={tier}
                type="button"
                disabled={!plan || busy}
                aria-pressed={isSelected}
                onClick={() => setSelected(tier)}
                className={
                  "min-h-[106px] rounded-xl border p-2.5 text-center transition-colors focus-visible:outline-2 focus-visible:outline-[#D4AF37] " +
                  (isSelected ? "border-[#D4AF37] bg-[#4A3828]" : "border-[#4A3828] bg-[#241913]") +
                  (!plan ? " cursor-not-allowed opacity-50" : "")
                }
              >
                <span className="block text-xs font-semibold text-[#E6D5B8]">{labels[tier]}</span>
                <span className="mt-2 block text-lg font-semibold text-[#F5EBE0]">
                  {plan ? formatPrice(plan.amount_minor, plan.currency) : "Unavailable"}
                </span>
                <span className="block text-[11px] text-[#C0AB90]">
                  {tier === "pro_monthly" ? "per month" : "per year"}
                </span>
                {tier === "pro_annual" && savings !== null && savings > 0 && (
                  <span className="mt-1 inline-block text-[11px] font-semibold text-[#E7C678]">
                    Save {savings}%
                  </span>
                )}
              </button>
            );
          })}
        </div>

        {active && (
          <div className="mt-4 space-y-2 text-sm leading-relaxed text-[#E6D5B8]">
            <p>
              {selected === "family_annual"
                ? "Five independent learning profiles, each with personal study plans and progress."
                : "Advanced word review, Memorise with Meaning, complete Verse Studio, and AI teacher access."}
            </p>
            {selected === "pro_annual" && (
              <p>
                Equivalent to {formatPrice(active.amount_minor / 12, active.currency)} per month,
                billed annually.
              </p>
            )}
            {selected === "family_annual" && (
              <p>
                {formatPrice(active.amount_minor / 60, active.currency)} per person per month
                when all five profiles are used.
              </p>
            )}
            {selected === "pro_annual" && active.trial_available && (
              <div className="rounded-xl border border-[#C8A96E]/30 p-3">
                <strong>7-day free trial.</strong> You won't be charged today.
                The subscription renews at the displayed yearly price after the trial unless cancelled.
                {trialReminderEnabled && (
                  <> We'll remind you two days before your trial ends.</>
                )}
                {!trialReminderEnabled && (
                  <> Check your store's trial reminder settings and cancel any time before renewal.</>
                )}
              </div>
            )}
          </div>
        )}

        <button
          type="button"
          disabled={!active || busy}
          onClick={buy}
          className="mt-5 min-h-[48px] w-full rounded-full bg-gradient-to-r from-[#E7CA82] to-[#C8A96E] px-5 py-3 font-semibold text-[#1A120D] disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#D4AF37]"
        >
          {busy ? "Opening secure checkout…" :
            active?.trial_available && selected === "pro_annual" ? "Start 7-day free trial" :
            active ? `Continue with ${labels[selected]}` : "Not available in your region"}
        </button>

        <div className="mt-4 flex flex-wrap items-center justify-center gap-x-5 gap-y-3 text-xs">
          {platform !== "web" && onRestorePurchases && (
            <button type="button" className="underline underline-offset-4" onClick={restore}>
              Restore purchases
            </button>
          )}
          <button type="button" className="text-[#E6D5B8] underline underline-offset-4" onClick={onScholarship}>
            Cannot afford Pro? Request sponsored access
          </button>
          <button type="button" className="text-[#E6D5B8] underline underline-offset-4" onClick={onClose}>
            Keep learning for free
          </button>
        </div>
        {error && <p role="alert" className="mt-4 text-center text-sm text-[#FFADAB]">{error}</p>}
        <p className="mt-5 text-center text-[11px] leading-relaxed text-[#C0AB90]">
          No advertisements. No pressure to upgrade. Prices and eligibility are
          confirmed by your store before purchase.
        </p>
      </div>
    </div>
  );
}
